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
- `POST /api/chat`：基于工具结果的风险解释与预测问答

架构、规则、来源、演示方式分别见 [本体](docs/ontology.md)、[行为模型](docs/behavior-model.md)、[数据来源](docs/data-sources.md)、[演示脚本](docs/demo-script.md)。
