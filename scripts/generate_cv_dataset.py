"""Synthetic CV Dataset Generator（100% 程序化合成，禁用任何真实监控/人脸数据）。

生成 Ultralytics YOLO detection 格式数据集：

data/cv_synthetic/
├── images/{train,val,test}/   # JPEG 合成画面
├── labels/{train,val,test}/   # YOLO 归一化 bbox 标注
├── data.yaml
├── dataset_card.md
└── stats.json

类别（仅 3 类，crowd 属于 person 聚合规则，不进训练）：
    0 person / 1 risk_object / 2 vehicle

确定性：同 --seed 输出完全一致（含图片字节），manifest hash 稳定。
OOD 模式（--ood）：偏移 lighting / fog / camera angle / scale / occlusion 分布，
仅用于独立泛化评估，绝不参与训练。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
JPEG_QUALITY = 92
EDGE_MARGIN_PX = 4
MAX_OBJECT_WIDTH = IMAGE_WIDTH - 2 * EDGE_MARGIN_PX - 8

CLASS_IDS = {"person": 0, "risk_object": 1, "vehicle": 2}
SCENES = ["urban_gate", "school_entrance", "street", "parking", "plaza", "station_entrance"]
SPLITS = ("train", "val", "test")

# 每类基准像素高度（perspective s=1 处），用于 y->scale 透视模型
REFERENCE_HEIGHT = {"person": 250.0, "risk_object": 105.0, "vehicle": 250.0}
# 每类尺寸档（像素高度区间）：small / medium / large -- 覆盖远/中/近景尺度分布
SIZE_BANDS = {
    "person": {"small": (24, 48), "medium": (48, 110), "large": (110, 250)},
    "risk_object": {"small": (14, 30), "medium": (30, 62), "large": (62, 118)},
    "vehicle": {"small": (40, 82), "medium": (82, 150), "large": (150, 270)},
}
SIZE_WEIGHTS = {"small": 0.18, "medium": 0.54, "large": 0.28}

# 人物为 anonymous synthetic silhouette（纯程序化剪影，无任何真实人脸特征）
PERSON_COLORS = [(38, 44, 58), (52, 48, 66), (30, 36, 48), (62, 58, 76), (44, 52, 62)]
RISK_COLORS = [(112, 44, 38), (86, 62, 44), (70, 70, 76), (128, 52, 40)]
VEHICLE_COLORS = [(150, 156, 164), (96, 108, 128), (172, 168, 158), (110, 118, 110), (186, 178, 170)]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class SceneEnv:
    """单张图的采样环境（全部由传入 rng 派生，保证确定性）。"""

    def __init__(self, rng: random.Random, ood: bool) -> None:
        self.rng = rng
        self.ood = ood
        self.scene = rng.choice(SCENES)
        if ood:
            # OOD：夜间/黄昏占多数，雾更频繁，camera angle 更极端
            self.time_of_day = rng.choices(["day", "dusk", "night"], weights=[0.20, 0.30, 0.50])[0]
            self.fog = rng.random() < 0.55
            self.rain = rng.random() < 0.25
            self.horizon = rng.choice([0.25, 0.28, 0.52, 0.58])
            self.mirror = rng.random() < 0.5
        else:
            self.time_of_day = rng.choices(["day", "dusk", "night"], weights=[0.55, 0.25, 0.20])[0]
            self.fog = rng.random() < 0.15
            self.rain = rng.random() < 0.12
            self.horizon = rng.uniform(0.32, 0.52)
            self.mirror = rng.random() < 0.5
        self.blur_radius = rng.choice([0, 0, 0, 0, 0.6, 1.0, 1.6] if not ood else [0, 0.8, 1.2, 1.8, 2.4])
        self.noise_sigma = rng.uniform(0, 3.5) if not ood else rng.uniform(1.5, 8.0)
        self.contrast = rng.uniform(0.78, 1.25) if not ood else rng.uniform(0.62, 1.2)

    @property
    def lighting(self) -> str:
        if self.time_of_day == "night":
            return "dim"
        if self.time_of_day == "dusk":
            return "normal"
        return "bright" if not (self.fog or self.rain) else "normal"

    def scale_at(self, y_norm: float) -> float:
        """透视模型：地平线处 s=0，画面底部 s=1（camera angle 由 horizon 高度与 mirror 模拟）。"""
        span = max(0.08, 1.0 - self.horizon)
        t = max(0.0, min(1.0, (y_norm - self.horizon) / span))
        return t ** 1.35


def _sky_palette(env: SceneEnv) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if env.time_of_day == "day":
        return (146, 186, 224), (208, 226, 238)
    if env.time_of_day == "dusk":
        return (196, 148, 118), (232, 196, 158)
    return (24, 30, 48), (40, 48, 70)


def _ground_palette(env: SceneEnv) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if env.time_of_day == "night":
        return (30, 34, 44), (48, 54, 66)
    if env.time_of_day == "dusk":
        return (96, 90, 84), (128, 120, 108)
    return (108, 116, 108), (150, 156, 146)


def _composite_overlay(image: Image.Image, overlay: Image.Image) -> None:
    merged = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    image.paste(merged)


def _draw_background(image: Image.Image, env: SceneEnv) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    horizon_px = int(env.horizon * height)
    sky_top, sky_bottom = _sky_palette(env)
    ground_top, ground_bottom = _ground_palette(env)
    for y in range(height):
        if y <= horizon_px:
            t = y / max(1, horizon_px)
            color = tuple(int(_lerp(sky_top[i], sky_bottom[i], t)) for i in range(3))
        else:
            t = (y - horizon_px) / max(1, height - horizon_px)
            color = tuple(int(_lerp(ground_top[i], ground_bottom[i], t)) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    rng = env.rng
    # 远景建筑（制造城市纵深）
    if env.time_of_day == "night":
        building_fill = (34, 38, 54)
        window_fill = (214, 190, 110)
    else:
        building_fill = (120, 128, 140)
        window_fill = (168, 178, 190)
    x = 0
    while x < width:
        bw = rng.randint(40, 110)
        bh = rng.randint(max(12, int(horizon_px * 0.25)), max(16, int(horizon_px * 0.85)))
        top = horizon_px - bh
        draw.rectangle([x, top, x + bw, horizon_px], fill=building_fill)
        if env.time_of_day == "night":
            for wy in range(top + 6, horizon_px - 6, 10):
                for wx in range(x + 5, x + bw - 5, 12):
                    if rng.random() < 0.35:
                        draw.rectangle([wx, wy, wx + 4, wy + 5], fill=window_fill)
        x += bw + rng.randint(4, 18)

    # 场景结构
    ground_y = horizon_px
    if env.scene in ("urban_gate", "school_entrance"):
        pillar = (88, 92, 100) if env.time_of_day != "night" else (40, 44, 56)
        for px in (int(width * 0.16), int(width * 0.84)):
            draw.rectangle([px - 12, ground_y - int(height * 0.30), px + 12, ground_y + int(height * 0.10)], fill=pillar)
        draw.rectangle([int(width * 0.10), ground_y - int(height * 0.30), int(width * 0.90), ground_y - int(height * 0.30) + 14], fill=pillar)
        if env.scene == "school_entrance":
            sign = (196, 176, 92) if env.time_of_day != "night" else (120, 106, 56)
            draw.rectangle([int(width * 0.42), ground_y - int(height * 0.26), int(width * 0.58), ground_y - int(height * 0.18)], fill=sign)
    elif env.scene == "street":
        lane = (214, 210, 190) if env.time_of_day != "night" else (120, 118, 104)
        road_top = ground_y + int(height * 0.08)
        draw.rectangle([0, road_top, width, height], fill=(70, 72, 78) if env.time_of_day != "night" else (34, 36, 42))
        for ly in range(road_top + 8, height, 42):
            draw.rectangle([int(width * 0.47), ly, int(width * 0.53), ly + 20], fill=lane)
    elif env.scene == "parking":
        line = (198, 194, 170) if env.time_of_day != "night" else (110, 108, 96)
        draw.rectangle([0, ground_y, width, height], fill=(92, 96, 100) if env.time_of_day != "night" else (40, 42, 48))
        slot = int(width * 0.16)
        for lx in range(slot, width - 20, slot):
            draw.line([(lx, ground_y + 6), (lx - int(height * 0.12), height - 6)], fill=line, width=3)
    elif env.scene == "plaza":
        tile_a = (146, 140, 132) if env.time_of_day != "night" else (56, 54, 52)
        tile_b = (160, 154, 144) if env.time_of_day != "night" else (64, 62, 58)
        draw.rectangle([0, ground_y, width, height], fill=tile_a)
        for ty in range(ground_y, height, 28):
            draw.line([(0, ty), (width, ty)], fill=tile_b, width=2)
        for tx in range(0, width, 44):
            draw.line([(tx, ground_y), (tx, height)], fill=tile_b, width=2)
    else:  # station_entrance
        pillar = (96, 100, 110) if env.time_of_day != "night" else (44, 48, 58)
        draw.rectangle([0, ground_y - int(height * 0.22), width, ground_y - int(height * 0.22) + 12], fill=pillar)
        for px in range(int(width * 0.1), int(width * 0.95), int(width * 0.16)):
            draw.rectangle([px - 7, ground_y - int(height * 0.22), px + 7, ground_y + int(height * 0.06)], fill=pillar)

    # 天气：雨 / 雾 / 夜色
    if env.rain:
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for _ in range(rng.randint(60, 130)):
            rx = rng.uniform(0, width)
            ry = rng.uniform(0, height)
            length = rng.randint(10, 26)
            od.line([(rx, ry), (rx - 3, ry + length)], fill=(188, 200, 214, 90), width=1)
        _composite_overlay(image, overlay)
    if env.fog:
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        fog_alpha = 150 if env.ood else 110
        for y in range(height):
            t = y / max(1, height - 1)
            alpha = int(fog_alpha * (1.0 - 0.45 * t))
            od.line([(0, y), (width, y)], fill=(206, 212, 218, alpha))
        _composite_overlay(image, overlay)
    if env.time_of_day == "night":
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(height):
            t = y / max(1, height - 1)
            alpha = int(70 * (1.0 - 0.5 * t))
            od.line([(0, y), (width, y)], fill=(10, 14, 34, alpha))
        _composite_overlay(image, overlay)
        for lx in (int(width * 0.2), int(width * 0.8)):
            lamp_y = horizon_px - int(height * 0.16)
            draw.ellipse([lx - 46, lamp_y - 30, lx + 46, lamp_y + 62], fill=(240, 224, 160))


def _draw_person(draw: ImageDraw.ImageDraw, placement: dict[str, object], rng: random.Random) -> tuple[int, int, int, int]:
    """Anonymous synthetic silhouette：头 + 躯干 + 腿剪影，绝无真实人脸特征。返回 bbox (x, y, w, h)。"""
    cx: int = placement["cx"]
    height: int = placement["height"]
    feet_y: int = placement["feet_y"]
    body = rng.choice(PERSON_COLORS)
    shade = tuple(max(0, min(255, int(c * 0.78))) for c in body)
    head_r = max(2, int(height * 0.115))
    torso_h = int(height * 0.42)
    leg_h = height - torso_h - head_r * 2
    torso_w = max(3, placement["torso_w"])
    half_w = max(head_r, int(torso_w * 0.62))
    head_cy = feet_y - leg_h - torso_h - head_r
    draw.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], fill=body)
    shoulder_y = head_cy + head_r
    draw.polygon(
        [(cx - torso_w // 2, shoulder_y), (cx + torso_w // 2, shoulder_y), (cx + torso_w // 2 - 1, shoulder_y + torso_h), (cx - torso_w // 2 + 1, shoulder_y + torso_h)],
        fill=body,
    )
    swing = rng.uniform(0.1, 0.4)
    leg_w = max(2, torso_w // 3)
    hip_y = shoulder_y + torso_h
    draw.polygon([(cx - leg_w - 1, hip_y), (cx - 1, hip_y), (cx - int(leg_w * 0.5 + swing * leg_w), feet_y), (cx - leg_w - int(swing * leg_w), feet_y)], fill=shade)
    draw.polygon([(cx + 1, hip_y), (cx + leg_w + 1, hip_y), (cx + leg_w + int(swing * leg_w), feet_y), (cx + int(leg_w * 0.5 - swing * leg_w), feet_y)], fill=shade)
    top_y = head_cy - head_r
    return cx - half_w, top_y, half_w * 2, feet_y - top_y


def _draw_risk_object(draw: ImageDraw.ImageDraw, placement: dict[str, object], rng: random.Random) -> tuple[int, int, int, int]:
    """抽象风险物品（bag-like / dark elongated box / synthetic prop），非写实武器。"""
    cx: int = placement["cx"]
    height: int = placement["height"]
    base_y: int = placement["feet_y"]
    kind: str = placement["kind"]
    width: int = placement["width"]
    color = rng.choice(RISK_COLORS)
    if kind == "bag":
        draw.rounded_rectangle([cx - width // 2, base_y - height, cx + width // 2, base_y], radius=max(2, height // 6), fill=color)
        handle_w = max(4, width // 3)
        handle_h = max(3, height // 3)
        draw.arc([cx - handle_w, base_y - height - handle_h, cx + handle_w, base_y - height + 2], start=0, end=180, fill=color, width=max(2, height // 12))
        top = base_y - height - handle_h
        return cx - width // 2, top, width, base_y - top
    if kind == "box":
        draw.rounded_rectangle([cx - width // 2, base_y - height, cx + width // 2, base_y], radius=2, fill=color)
        return cx - width // 2, base_y - height, width, height
    # prop：竖直圆柱状合成道具
    draw.rectangle([cx - width // 2, base_y - height, cx + width // 2, base_y - 2], fill=color)
    draw.ellipse([cx - width // 2, base_y - height - width // 3, cx + width // 2, base_y - height + width // 3], fill=tuple(min(255, c + 26) for c in color))
    top = base_y - height - width // 3
    return cx - width // 2, top, width, base_y - top


def _draw_vehicle(draw: ImageDraw.ImageDraw, placement: dict[str, object], rng: random.Random) -> tuple[int, int, int, int]:
    """Synthetic vehicle shape：car / van / small delivery，统一 vehicle 类。"""
    cx: int = placement["cx"]
    height: int = placement["height"]
    base_y: int = placement["feet_y"]
    kind: str = placement["kind"]
    length: int = placement["width"]
    color = rng.choice(VEHICLE_COLORS)
    shade = tuple(max(0, min(255, int(c * 0.7))) for c in color)
    wheel_r = max(3, int(height * 0.16))
    if kind == "car":
        body_h = int(height * 0.62)
        cabin_h = int(height * 0.38)
        cabin_l = int(length * 0.5)
        body_top = base_y - wheel_r * 2 - body_h
        draw.rounded_rectangle([cx - length // 2, body_top, cx + length // 2, body_top + body_h], radius=max(3, height // 14), fill=color)
        cabin_top = body_top - cabin_h + max(3, height // 16)
        draw.rounded_rectangle([cx - cabin_l // 2, cabin_top, cx + cabin_l // 2, body_top + 4], radius=max(3, height // 18), fill=shade)
        top = cabin_top
    else:  # van / small delivery vehicle
        body_h = height
        body_top = base_y - wheel_r * 2 - body_h
        draw.rounded_rectangle([cx - length // 2, body_top, cx + length // 2, body_top + body_h], radius=max(2, height // 20), fill=color)
        window_l = int(length * 0.62)
        draw.rectangle([cx - window_l // 2, body_top + max(3, height // 16), cx + window_l // 2, body_top + int(body_h * 0.42)], fill=shade)
        top = body_top
    for wx in (cx - int(length * 0.32), cx + int(length * 0.32)):
        draw.ellipse([wx - wheel_r, base_y - wheel_r * 2, wx + wheel_r, base_y], fill=(28, 28, 30))
    return cx - length // 2, top, length, base_y - top


def _plan_object(env: SceneEnv, rng: random.Random, label: str) -> dict[str, object]:
    """采样单个目标的几何参数（位置在采样宽度之后约束，保证 bbox 完整在画面内）。"""
    size_key = rng.choices(list(SIZE_WEIGHTS), weights=list(SIZE_WEIGHTS.values()))[0]
    lo, hi = SIZE_BANDS[label][size_key]
    target_h = rng.uniform(lo, hi)
    ref = REFERENCE_HEIGHT[label] * rng.uniform(0.85, 1.2)
    s = (target_h / ref) ** (1 / 1.35)
    span = max(0.08, 1.0 - env.horizon)
    y_norm = max(env.horizon + 0.03, min(0.965, env.horizon + s * span))
    height_px = int(round(ref * env.scale_at(y_norm)))
    lo_px, hi_px = SIZE_BANDS[label][size_key]
    height_px = max(6, int(min(max(height_px, lo_px), hi_px * 1.15)))

    kind = ""
    width = height_px
    torso_w = 0
    if label == "person":
        torso_w = max(3, int(height_px * (0.16 + rng.uniform(0, 0.05))))
        width = max(head := max(2, int(height_px * 0.115)), int(torso_w * 1.3))
    elif label == "risk_object":
        kind = rng.choice(["bag", "box", "prop"])
        if kind == "bag":
            width = max(6, int(height_px * 1.25))
        elif kind == "box":
            width = max(8, int(height_px * rng.uniform(1.8, 2.6)))
        else:
            width = max(5, int(height_px * 0.85))
    else:
        kind = rng.choice(["car", "van"])
        factor = rng.uniform(1.9, 2.3) if kind == "car" else rng.uniform(1.5, 1.8)
        width = int(height_px * factor)

    if width > MAX_OBJECT_WIDTH:
        height_px = max(6, int(height_px * MAX_OBJECT_WIDTH / width))
        width = MAX_OBJECT_WIDTH
    half_margin = EDGE_MARGIN_PX + width / 2
    cx_px = int(rng.uniform(half_margin, IMAGE_WIDTH - half_margin))
    feet_y = int(y_norm * IMAGE_HEIGHT)
    # 保证 bbox 纵向也在画面内
    est_height_px = height_px * 2 if label == "risk_object" and kind == "bag" else height_px
    if feet_y - est_height_px < EDGE_MARGIN_PX:
        feet_y = EDGE_MARGIN_PX + est_height_px
    feet_y = min(feet_y, IMAGE_HEIGHT - EDGE_MARGIN_PX)
    return {
        "label": label,
        "size": size_key,
        "kind": kind,
        "width": width,
        "torso_w": torso_w,
        "cx": cx_px,
        "feet_y": feet_y,
        "height": height_px,
        "y_norm": y_norm,
    }


def _sample_placements(env: SceneEnv, rng: random.Random) -> list[dict[str, object]]:
    """采样一张图内全部目标实例，并按 y 排序（近处后画，形成遮挡）。"""
    ood = env.ood
    # 负样本：5%~10% 纯背景图（空 label txt），用于降低 false positive
    if rng.random() < (0.10 if ood else 0.07):
        return []
    if ood:
        person_weights = [0.10, 0.20, 0.22, 0.18, 0.16, 0.14]
        side_weights = [0.40, 0.34, 0.26]
    else:
        person_weights = [0.15, 0.30, 0.25, 0.15, 0.10, 0.05]
        side_weights = [0.50, 0.35, 0.15]
    person_count = rng.choices([0, 1, 2, 3, 4, 5], weights=person_weights)[0]
    risk_count = rng.choices([0, 1, 2], weights=side_weights)[0]
    vehicle_count = rng.choices([0, 1, 2], weights=side_weights)[0]
    if person_count + risk_count + vehicle_count == 0:
        person_count = 1

    placements: list[dict[str, object]] = []
    for label, count in (("vehicle", vehicle_count), ("risk_object", risk_count), ("person", person_count)):
        for _ in range(count):
            placements.append(_plan_object(env, rng, label))
    # >=3 人时以一定概率形成空间聚集（供 CrowdDetected 聚合规则演示）
    if person_count >= 3 and rng.random() < 0.55:
        center = rng.uniform(0.32, 0.68)
        for placement in placements:
            if placement["label"] == "person":
                half_margin = EDGE_MARGIN_PX + placement["width"] / 2
                cx = center + rng.uniform(-0.13, 0.13)
                placement["cx"] = int(min(IMAGE_WIDTH - half_margin, max(half_margin, cx * IMAGE_WIDTH)))
    placements.sort(key=lambda p: p["y_norm"])
    return placements


def render_image(
    env: SceneEnv, rng: random.Random, noise_rng: np.random.RandomState
) -> tuple[Image.Image, list[tuple[str, tuple[int, int, int, int]]]]:
    """渲染一张合成图，返回图片与 (label, bbox_px) 列表。"""
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT))
    _draw_background(image, env)
    draw = ImageDraw.Draw(image)
    placements = _sample_placements(env, rng)
    records: list[tuple[str, tuple[int, int, int, int]]] = []
    for placement in placements:
        label = placement["label"]
        if label == "person":
            bbox = _draw_person(draw, placement, rng)
        elif label == "risk_object":
            bbox = _draw_risk_object(draw, placement, rng)
        else:
            bbox = _draw_vehicle(draw, placement, rng)
        x, y, w, h = bbox
        if w < 3 or h < 3:
            continue
        records.append((label, (int(x), int(y), int(w), int(h))))

    if env.blur_radius > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=env.blur_radius))
    if env.noise_sigma > 0:
        array = np.asarray(image).astype(np.int16)
        noise = noise_rng.normal(0, env.noise_sigma, size=array.shape)
        array = np.clip(array + noise, 0, 255).astype(np.uint8)
        image = Image.fromarray(array)
    if env.contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(env.contrast)
    if env.mirror:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
        records = [(label, (IMAGE_WIDTH - x - w, y, w, h)) for label, (x, y, w, h) in records]
    return image, records


def _validate_label_line(cx: float, cy: float, w: float, h: float) -> None:
    """自动质量校验：归一化坐标合法、bbox 不越界、面积 > 0。违规立即失败。"""
    if not (0 < w <= 1):
        raise ValueError(f"label width out of range: {w}")
    if not (0 < h <= 1):
        raise ValueError(f"label height out of range: {h}")
    if not (0 <= cx <= 1) or not (0 <= cy <= 1):
        raise ValueError(f"label center out of range: cx={cx}, cy={cy}")
    if cx - w / 2 < 0 or cx + w / 2 > 1 or cy - h / 2 < 0 or cy + h / 2 > 1:
        raise ValueError(f"bbox exceeds frame: cx={cx}, cy={cy}, w={w}, h={h}")


def _occlusion_level(target: tuple[int, int, int, int], others: list[tuple[int, int, int, int]]) -> str:
    tx, ty, tw, th = target
    tarea = tw * th
    covered = 0
    for ox, oy, ow, oh in others:
        ix = max(0, min(tx + tw, ox + ow) - max(tx, ox))
        iy = max(0, min(ty + th, oy + oh) - max(ty, oy))
        covered += ix * iy
    fraction = covered / max(1, tarea)
    if fraction > 0.40:
        return "heavy"
    if fraction > 0.05:
        return "partial"
    return "none"


def generate_dataset(out_dir: Path, images: int, seed: int, ood: bool = False) -> dict[str, object]:
    rng = random.Random(seed)
    started = time.time()
    split_names = ["val"] if ood else list(SPLITS)
    for split in split_names:
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    if ood:
        split_map = {i: "val" for i in range(images)}
    else:
        indices = list(range(images))
        rng.shuffle(indices)
        val_count = round(images * 0.15)
        test_count = round(images * 0.15)
        split_map: dict[int, str] = {}
        for i in indices[:val_count]:
            split_map[i] = "val"
        for i in indices[val_count : val_count + test_count]:
            split_map[i] = "test"
        for i in indices[val_count + test_count :]:
            split_map[i] = "train"

    stats: dict[str, object] = {
        "per_class_instances": {name: 0 for name in CLASS_IDS},
        "objects_per_image_hist": {str(k): 0 for k in range(9)},
        "empty_images": 0,
        "occlusion_distribution": {"none": 0, "partial": 0, "heavy": 0},
        "size_distribution": {"small": 0, "medium": 0, "large": 0},
        "lighting_distribution": {"bright": 0, "normal": 0, "dim": 0},
        "weather_distribution": {"clear": 0, "fog": 0, "rain": 0},
        "scene_distribution": {scene: 0 for scene in SCENES},
        "time_of_day_distribution": {"day": 0, "dusk": 0, "night": 0},
        "split_distribution": {s: {"images": 0, "instances": 0} for s in split_names},
    }
    manifest: list[dict[str, object]] = []
    instance_total = 0

    for index in range(images):
        env = SceneEnv(rng, ood=ood)
        noise_rng = np.random.RandomState((seed * 1_000_003 + index) % (2**31 - 1))
        image, records = render_image(env, rng, noise_rng)
        split = split_map[index]
        stem = f"im{index:06d}"
        image_path = out_dir / "images" / split / f"{stem}.jpg"
        label_path = out_dir / "labels" / split / f"{stem}.txt"
        image.save(image_path, format="JPEG", quality=JPEG_QUALITY)

        lines: list[str] = []
        bboxes = [bbox for _, bbox in records]
        for label, (x, y, w, h) in records:
            cx = (x + w / 2) / IMAGE_WIDTH
            cy = (y + h / 2) / IMAGE_HEIGHT
            nw = w / IMAGE_WIDTH
            nh = h / IMAGE_HEIGHT
            _validate_label_line(cx, cy, nw, nh)
            lines.append(f"{CLASS_IDS[label]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
            stats["per_class_instances"][label] += 1
            instance_total += 1
            pixel_area = w * h
            stats["size_distribution"]["small" if pixel_area < 32 * 32 else "medium" if pixel_area < 96 * 96 else "large"] += 1
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        for i, (_, bbox_i) in enumerate(records):
            stats["occlusion_distribution"][_occlusion_level(bbox_i, bboxes[i + 1 :])] += 1
        stats["lighting_distribution"][env.lighting] += 1
        stats["weather_distribution"]["rain" if env.rain else "fog" if env.fog else "clear"] += 1
        stats["scene_distribution"][env.scene] += 1
        stats["time_of_day_distribution"][env.time_of_day] += 1
        stats["objects_per_image_hist"][str(min(len(records), 8))] += 1
        stats["split_distribution"][split]["images"] += 1
        stats["split_distribution"][split]["instances"] += len(records)
        if not records:
            stats["empty_images"] += 1

        image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
        manifest.append({"name": f"{split}/{stem}.jpg", "sha256": image_sha, "labels": lines})

        if (index + 1) % 2000 == 0:
            print(f"  [{index + 1}/{images}] {time.time() - started:.0f}s elapsed", flush=True)

    manifest_payload = json.dumps(
        {"seed": seed, "images": images, "ood": ood, "files": sorted(manifest, key=lambda item: item["name"])},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    dataset_hash = hashlib.sha256(manifest_payload).hexdigest()

    stats["image_count"] = images
    stats["instance_count"] = instance_total
    stats["empty_image_ratio"] = round(stats["empty_images"] / images, 4)
    stats["objects_per_image"] = round(instance_total / images, 3)
    stats["generation_seconds"] = round(time.time() - started, 1)
    stats["seed"] = seed
    stats["ood"] = ood
    stats["image_size"] = [IMAGE_WIDTH, IMAGE_HEIGHT]
    stats["jpeg_quality"] = JPEG_QUALITY
    stats["dataset_hash"] = dataset_hash
    return stats


def write_yaml(out_dir: Path, ood: bool) -> None:
    # OOD 集只做评估：train/val/test 全部指向唯一 split（val），绝不用于训练
    content = (
        f"# Ultralytics YOLO detection format ({'OOD evaluation-only' if ood else 'synthetic training dataset'})\n"
        f"path: {out_dir.as_posix()}\n"
        f"train: images/{'val' if ood else 'train'}\n"
        "val: images/val\n"
        f"test: images/{'val' if ood else 'test'}\n"
        "names:\n"
        "  0: person\n"
        "  1: risk_object\n"
        "  2: vehicle\n"
    )
    (out_dir / "data.yaml").write_text(content, encoding="utf-8")


def write_dataset_card(out_dir: Path, stats: dict[str, object], ood: bool) -> None:
    kind = "OOD（out-of-distribution）独立评估集" if ood else "训练数据集"
    lines = [
        "# Synthetic CV Dataset Card",
        "",
        f"- 类型：{kind}（100% Synthetic Visual Data，程序化渲染）",
        f"- 图片数：{stats['image_count']}",
        f"- 实例数：{stats['instance_count']}",
        f"- seed：{stats['seed']}",
        f"- dataset hash：{stats['dataset_hash']}",
        "- 类别：0 person / 1 risk_object / 2 vehicle",
        "",
        "## 数据来源声明",
        "",
        "- 100% Synthetic Visual Data（Pillow 程序化渲染）",
        "- No real faces（person 为 anonymous synthetic silhouette）",
        "- No real surveillance footage",
        "- No real Guangzhou residents",
        "- No real police image data",
        "- risk_object 为抽象风险物品（bag-like / dark box / synthetic prop），非写实武器",
        "",
        "## 已知限制",
        "",
        "- synthetic-to-real domain gap：本数据集指标仅代表 Synthetic-domain CV accuracy，",
        "  不代表真实监控场景准确率",
        "- crowd 不作为检测类别：CrowdDetected 由 >=3 person detection 的空间聚合规则产生",
        "",
        "## 重建命令",
        "",
        "```bash",
        f"python scripts/generate_cv_dataset.py --images {stats['image_count']} --seed {stats['seed']}" + (" --ood" if ood else ""),
        "```",
    ]
    (out_dir / "dataset_card.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


DEMO_SCENE_SEEDS = {"demo_normal": 1, "demo_crowd": 2, "demo_risk": 3, "demo_high_risk": 4}


def generate_demo_images(out_dir: Path, seed: int = 4242) -> None:
    """生成 Dashboard Trained CV 模式使用的独立 demo 图（确定性、可提交 Git 的小体积样张）。"""
    scenes = [
        ("demo_normal", 1, 0, 0),
        ("demo_crowd", 4, 0, 0),
        ("demo_risk", 1, 1, 0),
        ("demo_high_risk", 3, 1, 1),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    labels: dict[str, list[str]] = {}
    for name, persons, risks, vehicles in scenes:
        rng = random.Random(seed + DEMO_SCENE_SEEDS[name])
        env = SceneEnv(rng, ood=False)
        env.scene = "school_entrance"
        env.time_of_day = "day"
        env.fog = False
        env.rain = False
        env.blur_radius = 0
        env.noise_sigma = 1.0
        env.mirror = False
        placements = []
        for i in range(persons):
            # 紧凑排列（跨度 <= 0.24 < 0.30 聚合阈值），保证 Trained CV 能演示感知层 crowd 聚合
            placements.append(("person", 0.32 + 0.08 * i, 0.86))
        for i in range(risks):
            placements.append(("risk_object", 0.72, 0.90))
        for i in range(vehicles):
            placements.append(("vehicle", 0.68, 0.76))
        image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT))
        _draw_background(image, env)
        draw = ImageDraw.Draw(image)
        lines = []
        for label in ("vehicle", "risk_object", "person"):
            for lbl, cx_norm, feet_norm in [p for p in placements if p[0] == label]:
                height = int(REFERENCE_HEIGHT[lbl] * env.scale_at(feet_norm))
                feet_y = int(feet_norm * IMAGE_HEIGHT)
                plan: dict[str, object] = {"cx": 0, "feet_y": feet_y, "height": height, "kind": "", "torso_w": 0, "width": height}
                if label == "person":
                    plan["torso_w"] = max(3, int(height * 0.18))
                    plan["width"] = max(int(height * 0.115), int(plan["torso_w"] * 1.3))
                elif label == "risk_object":
                    plan["kind"] = "bag"
                    plan["width"] = max(6, int(height * 1.25))
                else:
                    plan["kind"] = "car"
                    plan["width"] = int(height * 2.1)
                # 与主路径 _plan_object 相同的边界钳制：bbox 永不越界
                half = int(plan["width"]) / 2
                cx = int(cx_norm * IMAGE_WIDTH)
                cx = max(EDGE_MARGIN_PX + half, min(IMAGE_WIDTH - EDGE_MARGIN_PX - half, cx))
                plan["cx"] = int(cx)
                if label == "person":
                    x, y, w, h = _draw_person(draw, plan, rng)
                elif label == "risk_object":
                    x, y, w, h = _draw_risk_object(draw, plan, rng)
                else:
                    x, y, w, h = _draw_vehicle(draw, plan, rng)
                ncx = (x + w / 2) / IMAGE_WIDTH
                ncy = (y + h / 2) / IMAGE_HEIGHT
                nw, nh = w / IMAGE_WIDTH, h / IMAGE_HEIGHT
                _validate_label_line(ncx, ncy, nw, nh)
                lines.append(f"{CLASS_IDS[lbl]} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}")
        image.save(out_dir / f"{name}.jpg", format="JPEG", quality=JPEG_QUALITY)
        labels[name] = lines
    (out_dir / "demo_labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"demo images -> {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic CV dataset (YOLO format)")
    parser.add_argument("--images", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--ood", action="store_true", help="生成 OOD 评估集（偏移分布，不参与训练）")
    parser.add_argument("--demo", action="store_true", help="生成 Dashboard Trained CV demo 图")
    args = parser.parse_args()

    if args.demo:
        generate_demo_images(PROJECT_ROOT / "data" / "cv_demo", seed=4242)
        return

    default_out = "data/cv_synthetic_ood" if args.ood else "data/cv_synthetic"
    out_dir = PROJECT_ROOT / (args.out or default_out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"generating {args.images} images (seed={args.seed}, ood={args.ood}) -> {out_dir}", flush=True)
    stats = generate_dataset(out_dir, args.images, args.seed, ood=args.ood)
    write_yaml(out_dir, ood=args.ood)
    write_dataset_card(out_dir, stats, ood=args.ood)
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {k: stats[k] for k in ("image_count", "instance_count", "per_class_instances", "empty_images", "dataset_hash", "generation_seconds")},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
