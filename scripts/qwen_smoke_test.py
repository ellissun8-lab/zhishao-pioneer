"""Qwen3.8-Max 真实 API smoke test（需要合法 DASHSCOPE_API_KEY）。

四项逐项 PASS/FAIL，全部走真实生产代码路径（QwenProvider / run_qwen_agent /
vision_analyze），不做任何 mock：
  1. Text API          —— provider.chat 真实调用
  2. Function Calling  —— run_qwen_agent("训练模型认为未来10分钟风险多少？")
                          必须真实调用 ml_predict_risk(horizon_minutes=10)
  3. Multi-Tool        —— run_qwen_agent("现在模型建议采取什么措施？")
                          必须真实调用 ml_recommend_strategy（+ What-if 验证）
  4. Vision            —— POST /api/llm/vision/analyze 真实发送合成图给 qwen3.8-max

Key 只从环境变量或本地 .env 读取（绝不写死在本脚本/仓库）。未配置 Key 时
如实输出 NOT RUN 并以退出码 2 结束——不伪造任何 PASS。

用法：
  python scripts/qwen_smoke_test.py            # 读取环境变量 + 本地 .env
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_local_env() -> None:
    """读取本地 .env（KEY=VALUE），不覆盖已有环境变量；这是 Key 的唯一合法入口。"""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    _load_local_env()
    # 迟导入：先加载 .env 再构造 provider
    from backend.app.api.llm import vision_analyze
    from backend.app.api.llm import VisionAnalyzeRequest
    from backend.app.data.seed import create_demo_state
    from backend.app.llm.providers.qwen import get_qwen_provider, reset_qwen_provider
    from backend.app.llm.qwen_agent import run_qwen_agent

    reset_qwen_provider()
    provider = get_qwen_provider()
    if not provider.configured:
        print("DASHSCOPE_API_KEY 未配置（仅允许本地 .env / 环境变量）——四项均 NOT RUN，不伪造 PASS。")
        print("NOT RUN: 0/4（配置合法 Key 后重跑本脚本）")
        return 2

    print(f"provider={provider.base_url} model={provider.model}")
    results: list[tuple[str, bool, str]] = []

    # ---- 1. Text API ----
    try:
        response = provider.chat(
            [{"role": "user", "content": "回复两个字：在线"}],
            max_tokens=16,
            timeout=30,
        )
        ok = bool((response.get("content") or "").strip())
        detail = f"content={response.get('content')!r} request_id={response.get('request_id')}"
        results.append(("Text API", ok, detail))
    except Exception as error:  # noqa: BLE001
        results.append(("Text API", False, f"{type(error).__name__}: {error}"))

    state = create_demo_state(80)

    # ---- 2. Function Calling（单工具，验收问题 1）----
    try:
        outcome = run_qwen_agent("训练模型认为未来10分钟风险多少？", state)
        ok = "ml_predict_risk" in outcome["tools_used"] and not outcome["fallback"]
        detail = (
            f"tools_used={outcome['tools_used']} rounds={outcome['tool_rounds']} "
            f"answer={outcome['answer'][:120]!r}"
        )
        results.append(("Function Calling (ml_predict_risk)", ok, detail))
    except Exception as error:  # noqa: BLE001
        results.append(("Function Calling (ml_predict_risk)", False, f"{type(error).__name__}: {error}"))

    # ---- 3. Multi-Tool（策略推荐 + What-if，验收问题 2）----
    try:
        outcome = run_qwen_agent("现在模型建议采取什么措施？请说明模型概率与各策略的 What-if 仿真对比。", state)
        ok = (
            "ml_recommend_strategy" in outcome["tools_used"]
            and len(outcome["tools_used"]) >= 1
            and not outcome["fallback"]
        )
        detail = (
            f"tools_used={outcome['tools_used']} rounds={outcome['tool_rounds']} "
            f"answer={outcome['answer'][:120]!r}"
        )
        results.append(("Multi-Tool (ml_recommend_strategy)", ok, detail))
    except Exception as error:  # noqa: BLE001
        results.append(("Multi-Tool (ml_recommend_strategy)", False, f"{type(error).__name__}: {error}"))

    # ---- 4. Vision（真实发送合成图给 qwen3.8-max）----
    try:
        outcome = vision_analyze(VisionAnalyzeRequest(demo_scene_id="demo_high_risk"))
        ok = (not outcome.get("fallback")) and outcome.get("structured") is not None
        detail = f"structured={outcome.get('structured')} request_id={outcome.get('request_id')}"
        results.append(("Vision (qwen3.8-max multimodal)", ok, detail))
    except Exception as error:  # noqa: BLE001
        results.append(("Vision (qwen3.8-max multimodal)", False, f"{type(error).__name__}: {error}"))

    print()
    passed = 0
    for index, (name, ok, detail) in enumerate(results, start=1):
        status = "PASS" if ok else "FAIL"
        passed += int(ok)
        print(f"[{index}/4] {name:<42} {status}")
        print(f"      {detail}")
    print(f"\nSMOKE RESULT: {passed}/4 PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
