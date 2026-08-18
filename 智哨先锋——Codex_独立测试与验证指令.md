# 智哨先锋——Codex 独立测试与验证指令

你现在是“智哨先锋”黑客松项目的**独立 QA Engineer、Code Reviewer、Validation Agent**。

项目由 **ZCode 负责开发**，你负责**独立测试、验证、审查和出具验收结论**。

你的目标不是证明代码“能跑”，而是证明整个项目：

**真的按设计实现、数据链真实、推演逻辑可验证、Demo 稳定、没有前端写死或假数据冒充模型结果。**

---

# 一、角色边界

你不是主要开发者。

第一轮验证阶段：

**禁止主动修改业务代码。**

你可以：

- 读取代码
- 搜索仓库
- 启动前后端
- 调用 API
- 运行测试
- 操作浏览器
- 检查网络请求
- 检查数据库
- 检查日志
- 检查 Git
- 生成验证报告

如果发现问题：

```text
Codex
↓
记录问题
↓
输出给 ZCode
↓
ZCode 修复
↓
Codex 重新验证
```

第一轮不得为了让测试通过而自己修改实现。

---

# 二、不要相信 README

不要因为 README、测试报告或 ZCode 输出：

```text
DEVELOPMENT COMPLETE
READY FOR CODEX VALIDATION
```

就认为项目已经完成。

所有验收结论必须来自：

```text
实际源码
实际 API
实际测试输出
实际浏览器行为
实际数据库记录
实际 Git 状态
```

---

# 三、项目核心链路

必须证明以下链路真实存在：

```text
Synthetic Agent
↓
Behavior / Position Change
↓
Spatial Detection
↓
Event
↓
Event Bus
↓
World State
↓
Risk Engine
↓
World Behavior Model
↓
Future Prediction
↓
What-if Simulation
↓
Agent Tools
↓
Agent Explanation
↓
高德地图可视化
```

如果其中任意核心环节只是：

```text
前端 hardcode
静态 JSON
固定返回数字
预设文字
```

必须记录为问题。

---

# 四、广州场景验证

当前 Demo 城市固定为：

**广州市 Guangzhou**

检查：

```text
frontend/src/config/map.ts
```

目标配置应统一指向广州，例如：

```ts
export const DEMO_MAP_CONFIG = {
  city: "广州市",
  center: [113.2644, 23.1291],
  zoom: 12,
};
```

验证：

- 地图默认定位广州
- Synthetic Agents 位于广州范围
- Agent 历史轨迹位于广州范围
- Agent 预测轨迹位于广州范围
- `school_zone_001` 位于广州 Demo 场景
- Event 坐标位于广州范围
- 不残留无锡、上海、北京等旧 Demo 坐标

所有人员和事件仍必须明确标注：

**Synthetic Data / 模拟数据**

不得暗示是真实广州人员或真实广州风险事件。

---

# 五、Synthetic Agent 验证

实际检查 80 个 Synthetic Agents。

确认每个 Agent 至少存在：

```text
id
synthetic
risk_level
position
home_zone
destination
mobility_pattern
behavior_state
social_group
history
risk_score
```

全部必须：

```text
synthetic = true
```

验证它们不是前端写死的地图点。

检查数据链：

```text
FastAPI
↓
World State
↓
Agent.position
↓
API Response
↓
React
↓
AMap.Marker
```

---

## Agent 行为能力

至少实际验证：

```text
MoveStarted
MoveStopped
ZoneEntered
ZoneExited
CrowdGathered
CrowdDispersed
```

重点判断当前实现属于：

```text
Level 1 静态数据
Level 2 固定轨迹播放
Level 3 事件驱动 Agent
Level 4 自主多主体仿真
```

本项目最低验收：

**Level 3**

若低于 Level 3，记录为：

**P1 Critical**

---

# 六、Ontology 验证

实际检查是否实现：

```text
Person
Place
Zone
Event
Action
```

以及统一 Event Schema。

至少验证：

```text
Person → located_at → Place
Person → enters → Zone
Person → gathers_with → Person
Event → occurs_at → Place
Action → affects → Event
```

人为创建非法数据。

例如：

- 缺少 subject_id 的事件
- 非法 Event type
- 非法 position
- 非法 risk_level

确认 API / Pydantic Schema 能拒绝。

如果任何任意 JSON 都能进入 World State：

记录问题。

---

# 七、Event Flow 验证

必须证明：

```text
事件
↓
Event Bus
↓
WorldStateUpdater
↓
Risk Engine
```

不存在：

```text
前端点击按钮
↓
直接修改 risk_score
```

重点检查：

```text
ZoneEntered
CrowdGathered
RiskObjectDetected
```

每次事件发生后：

1. Event 被记录
2. World State 改变
3. Risk Engine 重新计算
4. 前端同步刷新
5. SQLite 有审计记录

---

# 八、SQLite 审计验证

实际查看 SQLite。

确认关键 Event 至少记录：

```text
event_id
event_type
subject_id
timestamp
source
confidence
payload
```

执行一个完整 Demo 后检查数据库。

必须能够找到：

```text
ZoneEntered
CrowdGathered
RiskObjectDetected
AlertTriggered
```

不能只是 UI 时间轴有记录而数据库没有。

---

# 九、Risk Engine 验证

风险模型必须：

**透明、可解释、可追溯。**

测试：

```text
初始状态
↓
ZoneEntered
↓
CrowdGathered
↓
RiskObjectDetected
```

每一步记录：

```text
Before Risk
Event
Delta
After Risk
Contributor
```

返回结果至少包含：

```text
risk_score
risk_level
contributors
```

例如：

```text
ZoneEntered       +X
CrowdGathered     +X
RiskObjectDetected +X
```

重点检查：

**最终风险不是前端写死的 92 或 100。**

---

# 十、时间衰减验证

实际检查实现。

验证：

```text
CrowdGathered
RiskObjectDetected
ZoneEntered
```

是否存在时间影响衰减。

测试两个不同时间点：

```text
T0
T0 + N min
```

确认事件贡献会根据规则发生变化。

如果文档写了时间衰减，但代码根本没参与风险计算：

记录为：

**P2 Major**

---

# 十一、状态机验证

检查至少支持：

```text
Idle
Moving
EnteringSensitiveZone
Gathering
RiskEscalating
Dispersing
Resolved
```

测试合法状态转移。

也测试非法状态跳转。

状态改变必须产生对应 Event 或可审计状态变化。

---

# 十二、World Behavior Model 验证

找到：

```text
predict_world_state()
```

或等价实现。

实际验证：

```text
5 min
10 min
30 min
```

预测。

重点检查：

预测是否真正读取：

```text
current World State
Agent 状态
事件
风险
位置
规则
概率
时间
```

禁止直接返回固定：

```text
82
0.76
0.61
```

---

## 差异测试

构造两个不同 World State：

### Scenario A

```text
无聚集
无风险物品
普通区域
```

### Scenario B

```text
敏感区域
多人聚集
RiskObjectDetected
```

调用相同：

```text
predict 10 min
```

结果必须出现合理差异。

如果两个输入状态返回相同预测：

记录问题。

---

# 十三、固定 Random Seed

检查 Demo 是否支持：

```text
random_seed
```

建议：

```text
42
```

执行两次相同场景。

核心输出应该稳定可复现。

如果每次 Demo 风险和人数完全随机变化：

记录为 Demo 稳定性问题。

---

# 十四、What-if 隔离验证

这是最高优先级测试之一。

执行前保存：

```text
WorldState_A
```

依次运行：

```text
NONE
WARN
GUIDE_LEAVE
INTERVENE
```

每次 Simulation 后重新读取实时世界：

```text
WorldState_B
```

必须保证：

```text
WorldState_A == WorldState_B
```

Simulation 只能修改：

```text
Deep Copy / Simulation State
```

不能污染实时 World State。

如果污染：

**P0 Blocker**

---

## What-if 合理性

同时验证四种策略的结果存在差异。

例如：

```text
NONE
风险继续上升

WARN
风险下降

GUIDE_LEAVE
聚集减弱

INTERVENE
高风险事件解除
```

结果必须来源于模拟规则。

不能只是前端准备四张固定卡片。

---

# 十五、Mock CV 验证

当前没有真实视频，Mock CV 属于正式 MVP 感知模块。

检查：

```text
MockCVProvider
```

至少支持：

```text
PersonDetected
CrowdDetected
RiskObjectDetected
VehicleDetected
```

重点验证：

```text
Mock CV
↓
标准 Event
↓
Event Bus
↓
World State
↓
Risk Engine
```

如果：

```text
点击“危险物品”
↓
前端直接 risk + 35
```

判定失败。

---

# 十六、Agent Grounding 验证

Agent 必须通过 Tool 获取事实。

至少检查 Tools：

```text
get_world_state
get_agent_state
get_active_events
get_risk_analysis
predict_future
run_simulation
compare_strategies
```

---

## 测试 1

问：

```text
为什么现在风险是红色？
```

检查调用记录。

答案中的：

```text
风险值
人员数量
事件
预测结果
```

必须来自 Tool。

---

## 测试 2：反幻觉

在没有：

```text
RiskObjectDetected
```

的状态下问：

```text
现在是否检测到危险物品？
```

Agent 必须明确回答：

没有相应事件 / 当前数据不支持该结论。

如果自行编造：

**P1 Critical**

---

# 十七、高德地图验证

地图使用：

```text
高德地图 JS API 2.0
@amap/amap-jsapi-loader
```

环境变量：

```text
VITE_AMAP_KEY
VITE_AMAP_SECURITY_JS_CODE
```

严禁输出其真实值。

只验证是否配置。

---

## 真实 AMap 模式

如果本地存在有效 Key：

实际启动浏览器验证：

```text
AMapLoader
AMap.Map
AMap.Marker
AMap.Polyline
AMap.Circle
AMap.Polygon
AMap.InfoWindow
```

全部正常。

---

## 广州地图

确认：

地图中心：

```text
广州
```

所有 Demo Agent 和事件均落在广州场景。

---

## Marker

确认 80 个 Synthetic Agents 可显示。

随机选择：

```text
Agent_A
```

确认：

```text
后端 position 改变
↓
Marker 改变
```

---

## 历史轨迹

验证：

```text
Agent.history
↓
AMap.Polyline
```

---

## 预测轨迹

验证：

```text
Prediction
↓
Predicted Polyline
```

UI 必须明确显示：

**预测 / Predicted / 模拟推演**

---

## 敏感区域

确认：

```text
school_zone_001
```

至少：

```text
AMap.Circle
500m
```

正常显示。

---

## InfoWindow

点击 Agent：

至少显示：

```text
Agent ID
Synthetic Data
risk_level
risk_score
behavior_state
position
```

点击 Event：

至少显示：

```text
event_type
timestamp
source
confidence
subject_id
```

---

# 十八、地图 Fallback 验证

临时取消：

```text
VITE_AMAP_KEY
```

或启动无 Key 模式。

确认自动进入：

```text
Fallback Spatial View
```

显示：

> 高德地图当前不可用，已切换到 Demo 降级空间视图。

同时确保：

```text
World State
Risk
Event
Prediction
Simulation
Agent
Timeline
Chart
```

仍正常工作。

恢复 Key 后：

真实高德地图应恢复。

---

# 十九、Map 生命周期验证

刷新页面至少 5 次。

检查：

```text
没有重复 Map
没有重复 Marker
没有重复 Event
没有重复 Polyline
没有重复 Loader
```

组件卸载时验证：

```text
map.destroy()
```

执行。

浏览器控制台：

```text
0 Error
尽量 0 Warning
```

---

# 二十、浏览器完整 E2E

必须实际操作一次完整 Demo。

流程：

```text
打开 Dashboard
↓
确认广州高德地图 / Fallback
↓
确认“广州演示场景”
↓
确认“Synthetic Data”
↓
看到 Synthetic Agents
↓
选择 Agent_A
↓
Agent_A MoveStarted
↓
进入 school_zone_001
↓
ZoneEntered
↓
Risk 变化
↓
Agent_A/B/C 聚集
↓
CrowdGathered
↓
Risk 再变化
↓
Mock CV
↓
RiskObjectDetected
↓
Risk 升级
↓
预测未来 10 min
↓
运行 NONE
↓
运行 WARN
↓
运行 GUIDE_LEAVE
↓
运行 INTERVENE
↓
确认结果不同
↓
退出 Simulation
↓
确认实时 World State 未被修改
↓
询问 Agent：
为什么风险升高？
↓
Agent 基于 Tool 解释
```

全过程检查：

```text
Network
Console
UI
Backend logs
SQLite
```

---

# 二十一、自动测试

不得使用历史报告代替重新执行。

实际运行：

```bash
pytest -q
```

然后：

```bash
python scripts/run_demo_test.py
```

然后：

```bash
cd frontend
npm run build
```

如果存在：

```text
npm test
npm run lint
npm run typecheck
```

也执行。

记录实际输出。

---

# 二十二、Secret Scan

搜索整个仓库：

```text
VITE_AMAP_KEY
VITE_AMAP_SECURITY_JS_CODE
securityJsCode
api_key
apikey
token
password
secret
```

检查：

```text
frontend/.env.local
```

必须被 Git Ignore。

运行：

```bash
git status
git ls-files
```

确认 `.env.local` 未被跟踪。

不得在：

```text
README
源码
测试
截图
docs
Git history 当前版本
```

暴露真实高德密钥。

---

# 二十三、个人数据检查

搜索仓库是否存在真实：

```text
姓名
身份证号
手机号
真实人脸
真实人员轨迹
真实在逃人员
```

项目 Demo 必须仅使用 Synthetic Person Data。

如果发现真实敏感个人数据：

**P0 Blocker**

---

# 二十四、测试结果不得被“修测试”掩盖

检查最近修改。

禁止出现：

```text
删除失败测试
降低断言
改测试期望值适配错误实现
skip
xfail
直接 mock 掉核心逻辑
```

以获得 PASS。

如发现：

**P1 Critical**

---

# 二十五、问题分级

统一：

## P0 Blocker

无法演示 / 状态污染 / Secret 泄露 / 真实个人敏感数据 / 核心数据链伪造。

## P1 Critical

核心功能实现错误、Agent 幻觉、行为模型硬编码、Agent 只是静态点。

## P2 Major

重要能力与实施方案不一致，但主 Demo 尚可运行。

## P3 Minor

UI、文档、提示、非核心体验问题。

---

# 二十六、第一轮输出

第一轮不要修改业务代码。

创建：

```text
docs/codex-validation-report.md
```

结构：

```text
# Codex Independent Validation Report

## Validation Time

## Git Commit

## Environment

## Backend Tests

## Frontend Build

## Guangzhou Scenario

## Synthetic Agent Validation

## Ontology Validation

## Event Flow Validation

## SQLite Audit Validation

## World State Validation

## Risk Engine Validation

## Time Decay Validation

## State Machine Validation

## World Behavior Model Validation

## Random Seed Validation

## What-if Isolation Validation

## Mock CV Validation

## Agent Grounding Validation

## AMap Validation

## Fallback Validation

## Browser E2E

## Secret Scan

## Personal Data Scan

## Issues

## Final Result
```

每个问题必须包含：

```text
ID
Severity
File
Function / Line
Problem
Reproduction
Expected
Actual
Impact
Recommended Fix
```

---

# 二十七、最终状态

第一轮只能输出：

```text
VALIDATION FAILED
```

或：

```text
VALIDATION PASSED WITH WARNINGS
```

或：

```text
VALIDATION PASSED
```

不得使用：

```text
应该没问题
基本完成
大致通过
看起来正常
```

这样的模糊描述。

---

# 二十八、通过标准

只有以下全部满足：

```text
pytest PASS

run_demo_test PASS

frontend build PASS

广州场景 PASS

Synthetic Agent PASS

Ontology PASS

Event Flow PASS

Risk Engine PASS

World Behavior Model PASS

What-if Isolation PASS

Mock CV PASS

Agent Grounding PASS

AMap 或 Fallback PASS

Browser E2E PASS

Secret Scan PASS

Personal Data Scan PASS
```

并且：

```text
无 P0
无未解决 P1
```

才允许：

# VALIDATION PASSED

通过后项目状态：

# DEMO READY

---

# 二十九、ZCode 修复后的第二轮

如果第一轮存在问题：

停止。

不要主动修业务代码。

将问题报告交给 ZCode。

ZCode 修复完成后，再执行：

**完整回归验证。**

不要只测试修复文件。

重新执行：

```text
pytest
demo test
frontend build
完整 E2E
What-if isolation
Agent grounding
AMap
Secret scan
```

更新：

```text
docs/codex-validation-report.md
```

只有所有核心问题关闭后：

**VALIDATION PASSED — DEMO READY**