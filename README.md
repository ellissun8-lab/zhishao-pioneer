# 智哨先锋｜城市行为智能推演 Agent

可运行、可验证、可现场演示的黑客松 MVP：公开/演示城市设施 -> Ontology -> Synthetic Agents -> Event -> World State -> 透明风险模型 -> 未来预测 -> What-if -> Agent 解释 -> 高德地图 Dashboard。

演示场景为**广州**（地图中心 `113.2644, 23.1291`）：80 个 Synthetic Agents、敏感区 `school_zone_001`（500m 围栏）、设施与全部事件坐标均位于广州演示范围内（`backend/app/data/seed.py` 的 `GUANGZHOU_DEMO_BOUNDS` 提供自动测试校验）。

感知与行为分层：Mock CV 的 `crowd` 检测产生 **CrowdDetected**（感知事实，权重 10）；**CrowdGathered**（权重 20）仅由空间规则确认（SyntheticAgentRuntime 检测到敏感区内 >=3 主体）或显式事件产生，二者禁止混用。

实时 World State 保持在内存中以保证演示响应，所有输入事件同时写入 SQLite `event_records` 作为可追溯审计日志；可通过 `DATABASE_URL` 切换数据库。

> Demo 场景为广州演示场景；人员身份、关系、轨迹及风险事件均为模拟数据（Synthetic Data），仅用于模型验证；系统输出不是真实公安预测。城市环境（学校/医院/车站等设施）可来自合法公开数据，敏感区域 `school_zone_001` 为 500m 演示围栏。

## 快速启动

环境要求：Python 3.11+、Node.js 20+。

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

另开终端：

```powershell
Copy-Item frontend/.env.example frontend/.env.local
# 在 frontend/.env.local 中填写 VITE_AMAP_KEY 与 VITE_AMAP_SECURITY_JS_CODE
Set-Location frontend
npm install
npm run dev
```

打开 `http://localhost:5173`；API 文档位于 `http://localhost:8000/docs`。高德 Key 与安全密钥均配置成功时加载高德地图 JS API 2.0；缺少配置、鉴权失败、网络失败或初始化超时时会自动显示空间关系演示底图，其他完整交互仍可使用。

也可运行 `docker compose up`（高德 Key 仍需传入前端环境）。

## 验收

```powershell
pytest -q
python scripts/run_demo_test.py
Set-Location frontend
npm run build
```

## 核心 API

- `GET /api/world/state`：当前完整世界状态
- `POST /api/world/tick`：推进事件驱动 Synthetic Agent 仿真（主体移动 -> 空间检测 -> ZoneEntered/CrowdGathered 等事件 -> 风险更新）
- `POST /api/world/advance`：推进一条预设 Demo 事件
- `POST /api/world/reset?seed=42`：以固定随机种子重置演示世界（同一输入 -> 相同场景）
- `POST /api/events`：提交统一 Ontology Event
- `GET /api/events/audit?limit=50`：SQLite 审计日志（event_id/event_type/subject_id/source/confidence/payload）
- `GET /api/world/predict?horizon_minutes=10`：未来状态预测（5/10/30 分钟）
- `POST /api/simulation/run`、`GET /api/simulation/compare`：What-if（在 World State 深拷贝上运行，不影响实时状态）
- `POST /api/perception/mock`：Mock CV 感知（person / vehicle / crowd / risk_object；crowd 产出感知层 CrowdDetected）
- `POST /api/perception/cv/detect-image`：Trained CV 真实 YOLO 推理（见下文 Synthetic CV Training Pipeline）
- `POST /api/chat`：Agent 问答（Qwen3.8-Max Function Calling 优先，Key 缺失/超时/限流时确定性回退，见下文 Qwen3.8-Max Agent）
- `GET /api/llm/status`：LLM 状态（provider / model / connected / fallback 与 CV·风险·策略模型组件状态；不返回 API Key）
- `POST /api/llm/vision/analyze`：Qwen Vision 语义理解（发送合成 demo 图给 qwen3.8-max，结构化输出；与 YOLO 检测严格分工）

架构、规则、来源、演示方式分别见 [本体](docs/ontology.md)、[行为模型](docs/behavior-model.md)、[数据来源](docs/data-sources.md)、[演示脚本](docs/demo-script.md)。

## Synthetic ML Pipeline

在规则 World Behavior Model 之外，用同一套仿真引擎生成 120,000 条 Synthetic Episodes，训练 Risk Forecast 与 Intervention Policy 两个 ML 模型，作为 Agent Tools 接入（模型缺失时透明回退规则模型，规则模型保留不删除）。Dashboard 同时展示两条独立预测路径：**规则世界模型预测**（PredictionPanel）与 **ML 风险预测**（训练模型面板的「ML预测未来10分钟」按钮，`POST /api/ml/predict-risk`）。

**一键复现（fresh clone）：**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt

# 1. 生成 120,000 Synthetic Episodes（seed=42，确定性可复现）
python scripts/generate_training_data.py --episodes 120000 --seed 42

# 2. 训练（只在 84,000 train 上训练）
python scripts/train_risk_model.py
python scripts/train_policy_model.py

# 3. 评估（指标只在 18,000 test 上计算，写入 models/metrics.json）
python scripts/evaluate_models.py
```

数据写入 `data/synthetic/*.parquet`（按 episode_id 切分 84,000/18,000/18,000）；模型产物为 `models/risk_forecast.joblib` 与 `models/intervention_policy.joblib`（随仓库提交，可直接运行无需重训）。

启动服务：

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
# 另开终端
Set-Location frontend
npm install
npm run dev
```

ML 相关 API：

- `GET /api/ml/status`：模型状态与 test 指标（读取 `models/metrics.json`）
- `POST /api/ml/predict-risk`：运行态 ML 风险预测（World State -> features -> joblib 模型；模型缺失时 `fallback=true, fallback_source=rule_world_behavior_model`）
- `GET /api/ml/recommend`：模型推荐 + What-if 仿真独立验证

Agent Tools：`ml_predict_risk` / `ml_recommend_strategy`（World State -> 特征提取 -> 训练模型 -> 带 `model_version` 与 `synthetic_training: true` 的 Tool Response；推荐结果必须再经 What-if 仿真验证后解释）。

> 声明：Risk 标签由透明规则 World Behavior Model 生成，ML 风险模型是该规则的 surrogate/distilled 逼近，**不代表真实城市预测精度**；Policy 标签来自 What-if 仿真 utility。全部训练数据 100% Synthetic（详见 `data/synthetic/dataset_card.md` 与 `docs/model-evaluation.md`）。

## Synthetic CV Training Pipeline

在 Mock CV 之外，提供完整的**真实目标检测训练管线**：程序化合成 50,000 张视觉数据 -> Ultralytics YOLO 训练 -> test split 独立评估 + OOD 评估 -> `RealCVProvider` 真实推理（`YOLO.predict`，绝不预设 Detection）-> 标准事件 -> Event Bus -> World State / Risk / Agent。

- 数据集：50,000 张 / 149,751 bbox 实例，仅 3 类 `person / risk_object / vehicle`（`crowd` 是感知层聚合结果，绝不是训练类别）；person 为 anonymous synthetic silhouette，risk_object 为抽象物品（UI 文案「疑似风险物品」）。详见 `docs/cv-dataset-card.md`。
- 分层约束：模型只产出 PersonDetected / RiskObjectDetected / VehicleDetected；CrowdDetected 由感知聚合（>=3 person + 空间距离阈值）产生；CrowdGathered 永远由行为/空间规则层确认。
- 指标诚实声明：所有指标均为 **Synthetic-domain CV accuracy**（含 OOD），不代表真实监控场景准确率；即便 mAP50 > 0.95 也不表述为「真实场景准确率 95%」。详见 `docs/cv-model-evaluation.md`。

**一键复现（fresh clone）：**

```powershell
pip install -r backend/requirements.txt   # 含 ultralytics / opencv-python-headless / Pillow

# 1. 生成 50,000 张合成数据（seed=42 确定性；同 seed -> 同 dataset_hash）
python scripts/generate_cv_dataset.py --images 50000 --seed 42
# OOD 评估集（seed=2026，分布偏移，不参与训练）
python scripts/generate_cv_dataset.py --images 5000 --seed 2026 --ood --out data/cv_synthetic_ood
# Dashboard Trained CV 演示图（已随仓库提交于 data/cv_demo/）
python scripts/generate_cv_dataset.py --demo

# 2. 训练（GPU 自动检测；CPU 可用 --epochs 5 做 smoke；只用 train+val，test 保留独立评估）
python scripts/train_cv_model.py --data data/cv_synthetic/data.yaml \
    --epochs 40 --imgsz 640 --batch 32 --workers 4 --seed 42

# 3. 独立评估（test split + OOD split + 推理延迟，写入 models/cv_detector/metrics.json）
python scripts/evaluate_cv_model.py --data data/cv_synthetic/data.yaml --ood-data data/cv_synthetic_ood/data.yaml
```

`images/` 与 `labels/` 不入库（可确定性重建）；模型产物 `models/cv_detector/best.pt`（约 5MB）与 `metrics.json`（含 model_version / training_seed / dataset_hash / 指标 / ultralytics 版本 / SHA256 记录于 `docs/cv-model-evaluation.md`）随仓库提交，fresh clone 可直接推理无需重训。

CV 相关 API：

- `POST /api/perception/cv/detect-image`：Trained CV 真实推理（multipart：`demo_scene_id` 或图片上传 + 可选 `provider=real|mock`、`subject_ids`、`conf`）。响应 `provider="real", model_invoked=true` **只在真实执行 `YOLO.predict` 成功后出现**；模型缺失/加载失败时显式回退 `provider="mock_fallback", model_invoked=false`。
- `GET /api/perception/cv/status`：模型可用性与最近一次推理摘要（UI REAL MODEL / MOCK FALLBACK 徽标数据源）。
- `GET /api/perception/cv/demo-image/{scene_id}`：合成 demo 测试图（Trained CV 模式输入）。
- `POST /api/perception/mock-cv/detect`：Mock CV 场景识别（原有路径保留）。

环境变量 `CV_PROVIDER=mock|real`（默认 mock）控制默认 provider；Dashboard「CV 智能感知」面板提供 `[Mock CV] / [Trained CV]` 切换，Trained CV 模式点击「运行训练模型」即触发真实模型推理，检测框/置信度全部渲染自 API 响应（前端禁止伪造）。

Agent Tools：`get_cv_detection_summary`（「视觉模型检测到了什么？」——读取最近一次 CV 推理记录；provider 与 model_invoked 如实标注，绝不把 MockCV 输出说成 Trained CV）。

> **第三方依赖声明**：目标检测使用 [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)（第三方库，**AGPL-3.0 许可证**，版权归 Ultralytics Inc. 所有），本项目仅作为依赖调用、未修改其源码；合成图像渲染使用 Pillow（MIT-CMU License）与 OpenCV（Apache-2.0，`opencv-python-headless`）。内置 `yolo26n.pt` 预训练权重同样来自 Ultralytics 并遵循其许可条款。

## Qwen3.8-Max Agent 集成

聊天问答接入 **Qwen3.8-Max**（阿里云百炼 Model Studio 官方 OpenAI-compatible API，`from openai import OpenAI` + `base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`），模型名固定为 `qwen3.8-max`（禁止以 `qwen3-max` / `qwen-plus` / `qwen3.8-max-preview` 冒充）。

**配置（本地 `.env`，Key 绝不入库/不入 README/不入测试）：**

```dotenv
DASHSCOPE_API_KEY=sk-****          # 只写本地 .env 或部署 secret
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.8-max
```

**真实 Function Calling Loop**：`POST /api/chat` 将现有 10 个 Agent Tools（`get_world_state` / `get_agent_state` / `get_active_events` / `get_risk_analysis` / `predict_future` / `ml_predict_risk` / `ml_recommend_strategy` / `run_simulation` / `compare_strategies` / `get_cv_detection_summary`）注册为 OpenAI function schema，模型发起 `tool_calls` -> 后端执行**真实业务函数** -> 结果回传 -> 循环（上限 5 轮防死循环）-> 基于工具结果作答。验收问题必须走真实工具：「训练模型认为未来 10 分钟风险多少？」必须调用 `ml_predict_risk(horizon_minutes=10)`，禁止模型自己估算；策略问题走 `ml_recommend_strategy` + `compare_strategies` 并区分「模型概率」与「What-if 仿真」。

**Qwen Vision 语义理解**：`POST /api/llm/vision/analyze` 把合成 demo 图真实发送给 qwen3.8-max，返回结构化结果（`estimated_people` / `vehicle_visible` / `possible_risk_object` / `crowd_semantics` / `summary`）。与 YOLO 严格分工：YOLO 负责 bbox/类别/检测置信度，Qwen Vision 只做语义理解，**不产出检测置信度、不写入事件链**。

**诚实回退**：Key 缺失或超时/429/5xx 时系统不崩溃，聊天退回确定性 grounded 解释（真实执行工具后基于结果生成），但 UI 必须显示 `Qwen3.8-Max Offline / Fallback Explanation`，绝不显示 Connected、绝不伪造 request_id。

**API**：

- `GET /api/llm/status`：`{provider, model, configured, connected, function_calling, multimodal, fallback}` + 组件状态（CV Detector / Risk Forecast / Policy Model），全部来自真实检查；不返回 API Key。
- `POST /api/chat`：`{answer, provider, model, tools_used[], tool_rounds, request_id, latency_ms, fallback}`；trace 不记录 api_key / authorization / secret。
- `POST /api/llm/vision/analyze`：`{structured, provider, model, request_id, latency_ms, fallback}`。

**真实 API smoke**：配置合法 Key 后运行 `python scripts/qwen_smoke_test.py`（文本 / Function Calling / 多 Tool / Vision 四项逐项 PASS/FAIL）。

> 测试（`backend/tests/test_qwen_agent.py`）只在网络边界注入 FakeClient：Function Calling 循环、工具适配器、业务函数全部真实执行，不 mock Agent 核心逻辑。
