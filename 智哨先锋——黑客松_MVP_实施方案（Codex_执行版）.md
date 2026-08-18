# 智哨先锋——黑客松 MVP 实施方案（Codex 执行版）

## 一、项目目标

在黑客松周期内完成一个**可运行、可演示、可验证**的城市风险智能推演系统。

项目名称：

**智哨先锋｜城市行为智能推演 Agent**

核心技术链路：

**公开城市数据 → 城市本体 Ontology → 合成行为主体 → CV/轨迹事件感知 → World State → 世界行为模型 → What-if 场景推演 → Agent 解释 → 可视化 Demo**

本项目不追求建设完整的政务业务系统，重点满足赛事评审关注的六个方向：

1. 城市问题价值
2. 公开数据利用
3. 本体建模质量
4. 世界行为模型合理性
5. 结果可验证性
6. Demo 完成度

---

# 二、MVP 要实现什么

最终 Demo 只需要完整跑通一个故事：

### 初始状态

城市地图中存在：

* 真实公开道路
* 学校
* 医院
* 商圈
* 火车站等 POI
* 若干 Synthetic Agent

例如：

```text
Agent_A
风险等级：High
当前位置：住宅区
状态：Moving

Agent_B
风险等级：Medium
当前位置：商圈
状态：Idle

Agent_C
风险等级：Medium
当前位置：学校附近
状态：Moving
```

所有人员、关系、轨迹、风险等级必须明确标注：

**Synthetic Data / 模拟数据**

---

### 场景演化

演示过程：

```text
Agent A 开始移动
↓
进入学校敏感区域
↓
风险 25 → 43
↓
Agent A、B、C 在 100 米范围内形成聚集
↓
风险 43 → 68
↓
CV / 模拟视觉事件检测到 RiskObjectDetected
↓
风险 68 → 92
↓
世界行为模型预测未来 10 分钟状态
↓
用户选择不同干预方案
↓
重新推演未来状态
```

---

### What-if 推演

至少支持四种策略：

```text
1. 不干预
2. 发送预警
3. 引导离开
4. 现场处置
```

模拟输出：

```text
不干预
风险：92 → 96
聚集人数：3 → 5

发送预警
风险：92 → 63
预计 1 名 Agent 离开

引导离开
风险：92 → 38
聚集状态解除

现场处置
风险：92 → 15
风险事件终止
```

注意：

这些数据属于**行为模型模拟结果**，不得宣称为真实公安预测结果。

---

# 三、技术架构

## 3.1 推荐技术栈

为了黑客松快速完成，优先稳定和开发速度。

### 前端

```text
React
TypeScript
Vite
TailwindCSS
高德地图 JS API 2.0
@amap/amap-jsapi-loader
ECharts
```

功能：

* 城市地图
* Agent 实时位置
* 轨迹
* 风险区域
* POI / 敏感区域覆盖物
* 地图 Marker / Polyline / Circle / Polygon
* 世界状态
* 风险曲线
* What-if 控制
* Agent 对话面板

地图实现要求：

```text
React
↓
@amap/amap-jsapi-loader
↓
高德地图 JS API 2.0
↓
AMap.Map
├── AMap.Marker       Synthetic Agent
├── AMap.Polyline     Agent 轨迹
├── AMap.Circle       动态风险围栏
├── AMap.Polygon      敏感区域
└── AMap.InfoWindow   Agent / Event 信息
```

高德地图必须封装为独立 React 组件，负责地图的加载、创建、覆盖物更新和销毁，业务逻辑不得直接散落在 Dashboard 页面中。

前端环境变量：

```text
VITE_AMAP_KEY=
VITE_AMAP_SECURITY_JS_CODE=
```

禁止将真实 Key 和安全密钥提交到 Git 仓库。

黑客松本地开发阶段允许通过环境变量配置 JS API Key 和安全密钥；部署环境优先采用服务端代理方式保护安全密钥。

---

### 后端

```text
Python 3.11+
FastAPI
Pydantic
SQLAlchemy
```

数据库第一版使用：

```text
SQLite
```

如有时间再切：

```text
PostgreSQL + PostGIS
```

MVP 不要因为数据库升级拖延 Demo。

---

### AI / 模型

第一版：

```text
规则引擎
+
状态机
+
概率模型
+
LLM 解释
```

不要第一天就训练复杂世界模型。

世界行为模型必须保证：

**输入可见 → 规则可见 → 状态变化可见 → 输出可验证**

---

### CV

采用插件式设计：

```text
CVEventProvider
```

提供两种实现：

```text
MockCVProvider
RealCVProvider
```

第一阶段必须完成：

**MockCVProvider**

可直接模拟：

```text
PersonDetected
CrowdDetected
RiskObjectDetected
VehicleDetected
```

如果时间充足，再接：

```text
YOLO
OpenCV
```

这样即使真实 CV 调试失败，整个 Demo 仍然可以完整运行。

---

# 四、系统目录结构

Codex 创建以下 Monorepo：

```text
zhishao-pioneer/
│
├── README.md
├── docker-compose.yml
├── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   └── Dashboard.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── CityMap.tsx
│   │   │   ├── AgentMarker.tsx
│   │   │   ├── RiskPanel.tsx
│   │   │   ├── WorldStatePanel.tsx
│   │   │   ├── SimulationPanel.tsx
│   │   │   ├── EventTimeline.tsx
│   │   │   ├── RiskChart.tsx
│   │   │   └── ChatPanel.tsx
│   │   │
│   │   ├── api/
│   │   ├── map/
│   │   │   ├── amap.ts
│   │   │   ├── overlays.ts
│   │   │   └── coordinates.ts
│   │   ├── types/
│   │   └── stores/
│   │
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── city.py
│   │   │   ├── agents.py
│   │   │   ├── events.py
│   │   │   ├── world.py
│   │   │   ├── simulation.py
│   │   │   └── chat.py
│   │   │
│   │   ├── ontology/
│   │   │   ├── models.py
│   │   │   ├── relations.py
│   │   │   └── schema.json
│   │   │
│   │   ├── world/
│   │   │   ├── state.py
│   │   │   ├── state_machine.py
│   │   │   └── updater.py
│   │   │
│   │   ├── behavior/
│   │   │   ├── engine.py
│   │   │   ├── rules.py
│   │   │   ├── scoring.py
│   │   │   └── prediction.py
│   │   │
│   │   ├── simulation/
│   │   │   ├── engine.py
│   │   │   └── strategies.py
│   │   │
│   │   ├── perception/
│   │   │   ├── base.py
│   │   │   ├── mock_cv.py
│   │   │   └── yolo_cv.py
│   │   │
│   │   ├── llm/
│   │   │   ├── agent.py
│   │   │   ├── tools.py
│   │   │   └── prompts.py
│   │   │
│   │   ├── data/
│   │   └── database/
│   │
│   ├── tests/
│   └── requirements.txt
│
├── data/
│   ├── public/
│   ├── synthetic/
│   └── demo/
│
├── scripts/
│   ├── load_city_data.py
│   ├── generate_agents.py
│   └── seed_demo.py
│
└── docs/
    ├── ontology.md
    ├── behavior-model.md
    ├── data-sources.md
    └── demo-script.md
```

---

# 五、城市本体 Ontology

这是比赛重点，必须单独实现，不要只写在 PPT 中。

## 核心实体

### Person

```json
{
  "id": "agent_A",
  "type": "Person",
  "synthetic": true,
  "risk_level": "high",
  "position": {
    "lng": 120.30,
    "lat": 31.57
  },
  "behavior_state": "moving",
  "risk_score": 25
}
```

---

### Place

```json
{
  "id": "school_001",
  "type": "Place",
  "category": "school",
  "name": "Demo School"
}
```

---

### Zone

```json
{
  "id": "zone_school_001",
  "type": "Zone",
  "zone_type": "sensitive",
  "radius": 500,
  "sensitivity": 0.9
}
```

---

### Event

统一事件结构：

```json
{
  "id": "event_001",
  "type": "ZoneEntered",
  "subject_id": "agent_A",
  "object_id": "zone_school_001",
  "timestamp": "2026-08-17T18:32:00",
  "confidence": 0.98,
  "source": "simulation"
}
```

事件类型至少支持：

```text
PersonDetected
MoveStarted
MoveStopped
ZoneEntered
ZoneExited
CrowdGathered
CrowdDispersed
RiskObjectDetected
AlertTriggered
InterventionApplied
```

---

### Action

```text
Observe
Warn
GuideLeave
Dispatch
Intervene
```

---

# 六、世界状态 World State

系统维护统一：

```text
WorldState
```

包括：

```json
{
  "timestamp": "...",
  "agents": [],
  "places": [],
  "zones": [],
  "active_events": [],
  "relations": [],
  "risk_state": {}
}
```

每发生一个 Event：

```text
Event
↓
WorldStateUpdater
↓
更新世界状态
↓
BehaviorEngine
↓
重新计算风险
↓
预测未来状态
```

---

# 七、世界行为模型

## 7.1 第一阶段模型

采用：

**Rule Engine + State Machine + Probability**

风险基础分：

```python
risk = base_risk
```

进入敏感区域：

```python
risk += zone_sensitivity * 20
```

三人以上聚集：

```python
risk += 20
```

危险物品：

```python
risk += 35
```

异常时间：

```python
risk += 10
```

高风险主体：

```python
risk *= 1.15
```

最终：

```python
risk = min(100, risk)
```

---

## 7.2 时间衰减

事件影响不能永久存在。

例如：

```text
危险物品：
30 分钟半衰减

聚集：
10 分钟半衰减

越界：
离开区域后逐渐恢复
```

实现：

```text
weight(t) = initial_weight × exp(-lambda × t)
```

---

## 7.3 状态转移

Agent 状态：

```text
Idle
↓
Moving
↓
EnteringSensitiveZone
↓
Gathering
↓
RiskEscalating
↓
Dispersing
↓
Resolved
```

每一次状态变化都必须生成 Event。

---

# 八、未来状态预测

实现：

```text
predict_world_state(
    current_state,
    horizon_minutes
)
```

支持：

```text
5 min
10 min
30 min
```

输出：

```json
{
  "risk_score": 82,
  "risk_trend": "up",
  "gather_probability": 0.76,
  "zone_entry_probability": 0.61,
  "predicted_agents": 4
}
```

第一版允许使用规则概率。

不需要训练神经网络才能叫行为模型。

赛事更重要的是：

**模型逻辑合理并且可以验证。**

---

# 九、What-if 推演引擎

接口：

```text
POST /simulation/run
```

输入：

```json
{
  "strategy": "warn",
  "horizon_minutes": 10
}
```

策略：

### NONE

不执行动作。

### WARN

产生一定概率：

```text
Agent 离开
聚集概率下降
```

### GUIDE_LEAVE

提高人员离开的概率。

### INTERVENE

直接将当前高风险事件设置：

```text
Resolved
```

但需要记录行动成本。

---

## 输出

```json
{
  "strategy": "warn",
  "before": {
    "risk": 92
  },
  "after": {
    "risk": 63
  },
  "changes": [
    "agent_C left zone",
    "crowd size changed 3 -> 2"
  ]
}
```

前端同时展示多种策略对比。

---

# 十、CV 感知

## MVP

必须先实现 Mock CV。

例如按钮：

```text
模拟检测人员
模拟聚集
模拟危险物品
```

点击：

```text
危险物品
```

产生：

```json
{
  "type": "RiskObjectDetected",
  "subject_id": "agent_A",
  "confidence": 0.91
}
```

进入 Event Bus。

---

## 第二阶段

有时间再加：

```text
YOLO / OpenCV
```

输入：

```text
图片
视频
摄像头
```

输出必须转换成统一 Event。

CV 与世界模型之间禁止直接耦合。

必须：

```text
CV
↓
Event
↓
Ontology
↓
World State
```

---

# 十一、Agent 能力

Agent 不负责直接预测。

Agent 负责调用系统工具。

Tools：

```text
get_world_state

get_agent_state

get_active_events

get_risk_analysis

predict_future

run_simulation

compare_strategies
```

用户问题示例：

```text
为什么学校区域现在是红色？
```

Agent 获取：

```text
ZoneEntered
+
CrowdGathered
+
RiskObjectDetected
```

回答：

```text
当前学校敏感区域存在 3 名模拟主体聚集，
其中 Agent_A 为高风险模拟主体，
同时系统检测到 RiskObjectDetected 事件。

综合风险值由 43 上升至 92，
当前判定为红色风险。
```

---

用户问：

```text
如果现在发送预警，会发生什么？
```

Agent：

```text
run_simulation(strategy="warn")
```

然后解释模拟结果。

---

# 十二、前端 Demo 页面

只做一个 Dashboard。

## 页面布局

### 左侧

高德地图 JS API 2.0 城市地图。

显示：

```text
高德地图底图
POI / 敏感区域
Synthetic Agent Marker
Agent 历史与预测轨迹 Polyline
风险围栏 Circle / Polygon
事件位置 Marker
```

地图交互至少支持：

```text
点击 Agent → 查看 Agent 当前状态
点击风险区域 → 查看区域风险及活跃事件
点击 Event → 查看事件来源与时间
切换轨迹 → 历史轨迹 / 预测轨迹
运行 What-if → 在同一地图展示模拟后的状态变化
```

---

### 中间

世界状态：

```text
当前风险：92

当前事件：
ZoneEntered
CrowdGathered
RiskObjectDetected
```

风险曲线：

```text
25
↓
43
↓
68
↓
92
```

---

### 右侧

What-if：

```text
[不干预]

[发送预警]

[引导离开]

[现场处置]
```

下面：

Agent 对话框。

---

### 底部

事件时间轴：

```text
18:20 Agent_A MoveStarted

18:27 ZoneEntered

18:31 CrowdGathered

18:32 RiskObjectDetected

18:32 AlertTriggered
```

---

# 十三、地图接口与公开数据

## 13.1 地图接口

Demo 地图统一使用：

```text
高德地图 JS API 2.0
```

React 侧使用官方 Loader：

```text
@amap/amap-jsapi-loader
```

高德地图主要负责：

```text
底图展示
地图交互
Marker 展示
轨迹 Polyline
风险围栏 Circle / Polygon
InfoWindow
POI 查询（如实际使用）
地理编码 / 逆地理编码（如实际使用）
```

注意：**高德地图接口是地图能力提供方，不等于赛事公开数据本身。**赛事需要披露和评价的城市数据，应单独记录其来源、字段、用途和授权情况。

## 13.2 城市公开数据

城市环境数据优先选择合法公开来源，可包括：

```text
政府开放数据平台
公开统计数据
公开行政区划数据
合法开放的 POI / 城市设施数据
公开天气及交通统计数据
```

如果还有公开政府数据，再增加：

```text
行政区划
人口统计
交通数据
天气
城市开放数据
```

创建：

```text
docs/data-sources.md
```

每个数据源必须记录：

```text
数据名称
URL
来源
许可证
采集时间
字段
用途
```

同时在 `docs/data-sources.md` 中单独记录高德地图服务：

```text
服务名称：高德地图 JS API 2.0
用途：地图底图、覆盖物、空间交互及可选地图服务
接入方式：@amap/amap-jsapi-loader
Key 类型：Web 端（JS API）
密钥管理：环境变量；部署环境优先服务端安全代理
```

---

# 十四、模拟数据

必须生成：

```text
50~200 Synthetic Agents
```

属性：

```text
id
risk_level
home_zone
current_position
destination
mobility_pattern
behavior_state
social_group
```

重点：

全部：

```text
synthetic = true
```

UI 明确写：

> Demo 中人员身份、关系、轨迹及风险事件均为模拟数据，仅用于模型验证。

---

# 十五、验证方案

不能只演动画。

需要设计 Test Scenarios。

至少：

### Case 01

普通 Agent 进入普通区域。

预期：

```text
Risk < 30
```

### Case 02

高风险 Agent 进入敏感区域。

预期：

```text
Risk ↑
```

### Case 03

三个 Agent 聚集。

预期：

```text
CrowdGathered
Risk +20
```

### Case 04

RiskObjectDetected。

预期：

```text
Risk 明显增加
```

### Case 05

执行 Warn。

预期：

```text
未来风险 < 不干预
```

---

后台增加：

```text
pytest
```

执行：

```bash
pytest
```

必须全部通过。

---

# 十六、开发顺序

Codex 不得同时开发全部功能。

严格按顺序执行。

## P0：当天必须完成

### Task 1

创建项目结构。

### Task 2

实现 Ontology。

### Task 3

实现 WorldState。

### Task 4

实现 Event Bus。

### Task 5

实现 Risk Engine。

### Task 6

实现 Synthetic Agent。

### Task 7

做一个能运行的 FastAPI API。

验收：

```text
可以创建 Agent
可以发送 Event
World State 会变化
Risk Score 会变化
```

---

## P1：核心 Demo

### Task 8

React 接入高德地图 JS API 2.0。

要求：

```text
使用 @amap/amap-jsapi-loader
完成 AMap.Map 创建与销毁
支持 Synthetic Agent Marker
支持轨迹 Polyline
支持敏感区域 Circle / Polygon
支持 InfoWindow
Key 从环境变量读取
```

### Task 9

显示 Synthetic Agents。

### Task 10

轨迹移动。

### Task 11

敏感区域。

### Task 12

聚集事件。

### Task 13

RiskObjectDetected。

验收：

能够演示：

```text
25 → 43 → 68 → 92
```

---

## P2：世界行为模型

### Task 14

未来状态预测。

### Task 15

What-if Simulation。

### Task 16

策略对比。

验收：

页面能同时展示：

```text
不干预
发送预警
引导离开
现场处置
```

的不同结果。

---

## P3：Agent

### Task 17

实现 Tool API。

### Task 18

LLM Agent。

### Task 19

自然语言解释。

---

## P4：CV

最后再接。

禁止因为 CV 调试阻塞整个项目。

---

# 十七、最终验收标准

项目必须做到：

* [ ] 一条命令启动后端
* [ ] 一条命令启动前端
* [ ] 高德地图 JS API 2.0 正常加载
* [ ] 高德地图 Key / 安全密钥不硬编码、不提交仓库
* [ ] Synthetic Agent Marker 正常显示
* [ ] Agent 轨迹 Polyline 正常显示
* [ ] 敏感区域 Circle / Polygon 正常显示
* [ ] 至少有 3 个 Synthetic Agent
* [ ] Agent 可以移动
* [ ] 可以进入敏感区域
* [ ] 可以产生聚集事件
* [ ] 可以产生 CV 模拟事件
* [ ] 世界状态实时更新
* [ ] 风险评分实时变化
* [ ] 可以预测未来状态
* [ ] 可以执行 What-if
* [ ] 可以比较策略
* [ ] Agent 可以解释风险原因
* [ ] Demo 数据明确标记为 Synthetic
* [ ] 公共数据来源可追溯
* [ ] 单元测试可以运行
* [ ] README 包含完整启动方式

---

# 十八、Codex 总执行指令

将下面内容直接作为 Codex 的总任务：

---

你现在是“智哨先锋”黑客松项目的首席全栈工程师和 AI 工程师。

目标是在最短时间内实现一个可运行、可验证、可现场演示的 MVP。

项目核心不是传统监控平台，而是：

**城市本体 Ontology + World State + World Behavior Model + What-if Simulation + Agent。**

请严格遵循本实施方案。

执行原则：

1. 优先保证端到端 Demo 可以运行。
2. 所有人员、轨迹、关联关系和风险行为必须使用 Synthetic Data。
3. 地图统一使用高德地图 JS API 2.0，通过 `@amap/amap-jsapi-loader` 接入；地图 Key 从环境变量读取，禁止硬编码或提交真实密钥。
4. 高德仅作为地图及空间服务能力，城市公开数据仍须单独记录合法来源、字段和用途，不得把地图底图直接表述为赛事公开数据成果。
5. CV 必须采用插件式架构，MockCVProvider 优先于真实 CV。
6. 所有感知结果必须统一转换成 Event。
7. Event 必须更新 World State。
8. World Behavior Model 根据 World State 推演未来。
9. What-if 必须复制当前 World State 后独立模拟，不能污染真实运行状态。
10. Agent 只能通过 Tools 获取系统状态和运行模拟，不允许凭空生成风险结论。
11. 所有模型结果必须可以追溯到输入事件、规则和状态变化。
12. 每完成一个阶段，都必须运行测试。
13. 不要为了过度工程化牺牲 Demo 完成度。
14. 不实现真实公安系统、运营商、真实人脸库、真实在逃人员追踪。
15. 不实现信创、政务云部署等与本次 MVP 无关的能力。
16. UI 必须显著显示“模拟数据 / Synthetic Data”标识。

请按以下顺序工作：

**项目骨架 → Ontology → Event → World State → Risk Engine → Synthetic Agents → 高德地图 → Demo事件 → World Behavior Model → What-if → Agent → CV → 美化。**

每完成一个阶段：

* 检查代码
* 启动运行
* 执行测试
* 修复错误
* 更新 README
* 再进入下一阶段

不要只生成代码文件而不运行验证。

最终交付必须能够现场完成：

**Agent 移动 → 进入敏感区域 → 聚集 → CV事件 → 风险升级 → 未来预测 → What-if → Agent解释**

的完整 Demo。



任何阶段不得仅以“代码已生成”作为完成标准。每完成一个阶段，Codex 必须主动执行测试并读取测试输出；如测试失败，应自行定位原因、修改代码并重新运行，直到全部通过。

最终必须自动执行：

pytest -q

python scripts/run_demo_test.py

npm run build

只有三项全部成功，才可以判定 MVP 为 Demo Ready。

同时生成 docs/test-report.md，记录测试时间、测试场景、输入、预期结果、实际结果和 PASS/FAIL 状态。