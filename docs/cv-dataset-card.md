# Synthetic CV Dataset Card（合成视觉数据集说明）

> 100% Synthetic Visual Data · 程序化渲染 · 无任何真实人脸/监控画面/警务图像数据

## 概览

| 项目 | 值 |
| --- | --- |
| 图片数 | 50,000（train 35,000 / val 7,500 / test 7,500，70/15/15） |
| bbox 实例数 | 149,751（≥ 100,000 要求满足） |
| 类别 | `0 person` / `1 risk_object` / `2 vehicle`（仅 3 类） |
| 图片尺寸 | 640×480 JPEG（quality 92） |
| 生成 seed | 42（完全确定性，同 seed 重建得到同一 `dataset_hash`） |
| dataset hash | `e780807538d213731313ed672769cdd909599c3ad6e03ea3ffcd5bd219c1b1d4` |
| 生成耗时 | 1461.4s（本机，含逐标注质量校验） |
| 负样本 | 3,588 张（7.18%，空标注 txt，训练负例防误检） |
| 生成脚本 | `scripts/generate_cv_dataset.py` |

数据文件本身不入库（`.gitignore` 忽略 `images/` 与 `labels/`）；fresh clone 后用下方命令可确定性重建（同 seed → 同字节级图像与标注 → 同 dataset hash）。

## 数据来源声明

- **100% Synthetic**：全部图像由 Pillow 程序化渲染（`ImageDraw` 几何绘制 + alpha 合成天气/夜景 + 高斯模糊 + numpy 噪声 + 对比度扰动），生成脚本不 import 任何网络/数据集/视频采集库（`backend/tests/test_cv_pipeline.py::test_cv_no_real_person_data` 强制校验）。
- **No real faces**：person 为 anonymous synthetic silhouette（头部椭圆 + 躯干多边形 + 摆动腿剪影，无任何真实人脸特征）。
- **No real surveillance footage / No real residents / No police image data**。
- **risk_object 为抽象风险物品**：bag-like（提手矩形袋）/ dark box / synthetic prop 三种抽象形态，非写实武器；对外文案一律为「疑似风险物品」，绝不出现「确认刀具/武器」类措辞。
- **vehicle 为合成形状**：car / van / delivery 抽象车身 + 车轮。

## 场景与变化维度

6 种场景均匀分布：urban_gate 8,309 / school_entrance 8,457 / street 8,382 / parking 8,326 / plaza 8,311 / station_entrance 8,215。

每张图随机采样：

- 时段 day 27,193 / dusk 12,646 / night 10,161（夜间含灯光晕与暗色覆盖）
- 天气 clear 37,480 / fog 6,524 / rain 5,996（alpha 合成雾梯度 / 雨丝）
- 相机角度（地平线高度 0.32–0.52）与透视尺度模型 `scale(y)=t^1.35`
- 物体尺度 small 35,741 / medium 72,479 / large 41,531（按像素面积 32²/96² 分档）
- 数量（每类 0–8）、遮挡 none 102,370 / partial 12,399 / heavy 34,982、模糊、噪声、对比度、镜像翻转（bbox 同步变换）

## 类别分布（无严重不平衡）

| 类别 | 实例数 | 占比 |
| --- | --- | --- |
| person | 89,685 | 59.9% |
| risk_object | 30,015 | 20.0% |
| vehicle | 30,051 | 20.1% |

每图平均 2.995 个实例。

**crowd 不是训练类别**：CrowdDetected 由感知层聚合规则（≥3 个 person detection 且成对中心距 ≤ 0.30）产生；CrowdGathered 由 World Behavior / Spatial Model 行为规则层确认，CV 模型永不输出二者。

## 标注质量与校验

- YOLO 格式：`labels/{split}/imNNNNNN.txt`，每行 `class cx cy w h`（归一化）。
- 生成时逐行校验（`_validate_label_line`）：`0 < w,h ≤ 1`、`0 ≤ cx,cy ≤ 1`、bbox 四边不越画面、无零面积/负值。
- 独立测试 `test_cv_dataset_bbox_valid` 重新解析全部标注文件复核；`test_cv_dataset_generation_deterministic` 验证两次生成的字节级一致；`test_cv_split_isolation` 验证 train/val/test 无任何文件重叠。

## OOD 评估集（独立，seed=2026）

| 项目 | 值 |
| --- | --- |
| 图片 / 实例 | 5,000 / 19,400（person 11,488 / risk_object 3,902 / vehicle 4,010） |
| dataset hash | `15ae99da0b2a5318b10310f39af725f548e7bcb5a238ea6a74233d7958703e57` |
| 分布偏移 | 夜间占比 49.8%（训练集 20.3%）、雾 42.2%（训练集 13.0%）、雨 25.7%、地平线偏移 [0.25–0.28, 0.52–0.58]、尺度/遮挡权重偏移 |

OOD 集不参与训练与早停，仅用于 `scripts/evaluate_cv_model.py` 的 OOD 泛化评估。

## 重建命令

```bash
# 主数据集（50k，seed 42）
python scripts/generate_cv_dataset.py --images 50000 --seed 42

# OOD 评估集（5k，seed 2026）
python scripts/generate_cv_dataset.py --images 5000 --seed 2026 --ood --out data/cv_synthetic_ood

# Dashboard Trained CV 模式使用的独立 demo 图（入库 data/cv_demo/）
python scripts/generate_cv_dataset.py --demo
```

## 已知限制（诚实声明）

- **synthetic-to-real domain gap**：本数据集上的所有指标（含 OOD）均为 *Synthetic-domain CV accuracy*，不代表真实监控场景准确率；即便 mAP50 > 0.95 也不得对外表述为「真实场景准确率 95%」。
- 抽象 risk_object 的类内多样性低于真实遗留物品。
- Demo 测试图（`data/cv_demo/`）由同一 generator 以隔离 seed 生成，仅作 UI 演示输入。
