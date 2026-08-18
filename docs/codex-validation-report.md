# 智哨先锋 Codex 独立测试与验证报告

## Validation Status

**LATEST STATUS: VALIDATION FAILED（Round 3）**

> 第一轮历史结论为 `VALIDATION FAILED`；当前有效结论见文末 `Round 2 Revalidation`，绑定 Commit `313fb8a108fe271e1206ca7dacbe2bff8bc63f46`。

- 验证日期：2026-08-18（Asia/Singapore）
- 验证模式：Fast Validation Mode，第一轮只读验证
- Git commit：`NO COMMIT`（仓库不存在可解析的 `HEAD`，当前项目文件均为 untracked）
- 结论：P0 全部通过；存在广州场景 P1 失败及多项 P2，不能判定为 Demo Ready。
- 重要说明：验证期间业务文件被外部进程持续更新，曾短暂出现 `Dashboard.tsx:147` JSX 编译错误，随后被外部修复。因此本报告以最后稳定磁盘快照为准；Codex 未修改业务代码。

## P0

| 项目 | 结果 | 实测证据 |
|---|---|---|
| `pytest -q` | PASS | `8 passed in 0.50s` |
| `python scripts/run_demo_test.py` | PASS | `DEMO READY`；风险 `28.8 → 28.8 → 49.5 → 72.5 → 100.0` |
| `npm run build` | PASS | TypeScript 与 Vite 构建成功，634 modules；仅有 507.96 kB chunk 警告 |
| What-if 隔离 | PASS | compare 前后 World State 深比较相等；结果为 none=100、warn=68、guide_leave=41、intervene=16 |
| Secret Scan | PASS | 未发现源码硬编码 secret/token/password；`frontend/.env.local` 含非空 AMap Key，但被 `.gitignore` 的 `.env.*` 规则忽略；报告未输出密钥值 |
| 真实个人敏感数据 | PASS | 数字型手机号/身份证 PCRE2 扫描无匹配，非文档业务代码中的敏感身份关键词无匹配；80 个主体均为 synthetic |

## P1

| 项目 | 结果 | 实测证据 |
|---|---|---|
| Synthetic Agent Level 3 | PASS | 80 个主体均 `synthetic=true`，字段满足指令；固定 seed 可复现。30 tick 产生 94 个事件，包含 MoveStarted/Stopped、ZoneEntered/Exited、CrowdGathered，80 个主体均产生历史轨迹 |
| ZoneEntered → Event → World State → Risk | PASS | API 四步：初始 28.8；ZoneEntered 后 49.5；CrowdGathered 后 72.4 并产生 AlertTriggered；RiskObjectDetected 后 100.0。SQLite 可查四种关键事件 |
| World Behavior Model 非硬编码 | PASS | 5/10/30 分钟预测可运行；相同 horizon 下不同 World State 得到不同风险与概率；预测读取当前风险、事件、入区主体数 |
| Agent Grounding / 反幻觉 | PASS | 未来问题调用 `predict_future`；空事件状态回答“无活跃事件”，未编造 RiskObjectDetected；答案标注 Synthetic Data |
| 广州坐标与 `school_zone_001` | **FAIL** | 后端主体范围为 lng `120.2768–120.3252`、lat `31.5573–31.5918`；前端中心 `[120.3017, 31.5747]`，页面地图显示无锡地名，不是广州 `[113.2644, 23.1291]` |
| 区域 ID 一致性 | 当前快照 PASS / 有版本漂移风险 | 用户已确认此前存在 `school_zone_001` 与 `zone_school_001` 不一致；当前稳定快照中 seed、service、map config 已统一为 `school_zone_001`，无法复现旧缺陷。因无 commit 且验证期间有并发更新，必须由 ZCode 在最终提交中再次确认 |

## P2

### COD-V-001 — P1 Critical — 广州 Demo 场景未实现

- 文件/行：`backend/app/data/seed.py:9`、`frontend/src/config/map.ts:1-3`、`backend/app/service.py:71-84`
- 问题：地图、主体、Zone、演示事件仍使用 `120.30/31.57` 一带坐标，且 map config 没有 `city: "广州市"`。
- 复现：调用 `/api/world/reset` 检查 80 个 Agent 坐标，或打开 Dashboard 查看地图地名。
- 预期：中心 `[113.2644, 23.1291]`，所有 Demo Agent、历史/预测轨迹、Zone、Event 均落在广州场景。
- 实际：坐标和真实高德地图均指向无锡区域。
- 影响：不满足明确的广州演示验收标准。
- 建议修复：统一迁移 seed、地图配置、演示事件与目的地生成边界到广州，并增加广州范围断言。

### COD-V-002 — P2 Major — Ontology 关系与输入校验不完整

- 文件/行：`backend/app/ontology/schema.json:5`、`backend/app/ontology/models.py:57-59,98-106`、`backend/app/world/updater.py:22-23`
- 问题：Schema 只有 `located_in/member_of/near/triggered/affected_by`，缺少验收要求的 `located_at/enters/gathers_with/occurs_at/affects`；Event 的 `subject_id` 可空；Position 无经纬度范围限制。
- 复现：POST 缺少 subject_id 的 RiskObjectDetected 返回 `201`；POST lng/lat=999 的 MoveStarted 返回 `201`。
- 预期：非法事件和非法坐标返回 4xx，不进入 World State。
- 实际：两类非法输入均被接受。
- 影响：Ontology 不能作为可信边界，错误数据可污染 World State 和审计表。
- 建议修复：按 Event 类型增加条件校验、限制经纬度范围，并补齐统一关系枚举及事件驱动的关系写入。

### COD-V-003 — P2 Major — ZoneEntered 贡献没有时间衰减

- 文件/行：`backend/app/behavior/scoring.py:28-43`
- 问题：敏感区域贡献直接由当前 `active_zone_ids` 计算固定值，没有事件时间或半衰期。
- 复现：同一状态在 T0 与 T+30min 计算，`sensitive_zone` 均为 `18.0`；对照 CrowdGathered 为 `20.0 → 2.5`，RiskObjectDetected 为 `35.0 → 17.5`。
- 预期：ZoneEntered 按明确规则随时间变化，或文档明确其持续状态语义并提供可验证的退出/超时机制。
- 实际：贡献永久不衰减，直到 ZoneExited。
- 影响：长时间未退出时风险可能持续偏高，不满足指令的三类时间衰减验收。
- 建议修复：为 ZoneEntered 增加时间规则，或将 active-zone 持续风险与事件衰减拆分并补测试。

### COD-V-004 — P2 Major — 状态机不拒绝非法跳转

- 文件/行：`backend/app/world/state_machine.py:3-16`
- 问题：转换仅按 EventType 返回目标状态，不检查当前状态与允许边。
- 复现：把 agent_A 设为 Idle 后直接发送 RiskObjectDetected，会无条件跳到 `risk_escalating`。
- 预期：定义合法转换图；非法跳转被拒绝或记录明确审计错误。
- 实际：任意来源事件均可覆盖行为状态。
- 影响：状态机语义和审计可信度不足。
- 建议修复：增加 `(current_state, event_type) -> next_state` 转换表、拒绝策略及合法/非法转换测试。

### COD-V-005 — P2 Major — Mock CV 未产出标准 CrowdDetected Event

- 文件/行：`backend/app/ontology/models.py:30-41`、`backend/app/perception/mock_cv.py:5-15`
- 问题：`crowd_detected` 输入被映射为 `CrowdGathered`，EventType 中不存在验收要求的 `CrowdDetected`。
- 复现：`MockCVProvider().detect("crowd_detected")` 返回 `CrowdGathered`。
- 预期：Mock CV 至少支持并产出 PersonDetected、CrowdDetected、RiskObjectDetected、VehicleDetected 标准感知事件。
- 实际：人员、车辆、风险物品通过，CrowdDetected 缺失。
- 影响：感知事实与行为推断混为同一事件，削弱 Ontology 分层。
- 建议修复：增加 CrowdDetected，并由后续规则决定是否形成 CrowdGathered。

### COD-V-006 — P2 Major — 缺少可审计 Git 基线

- 文件/行：仓库级
- 问题：`git rev-parse --verify HEAD` 返回 `NO_COMMIT`，所有项目文件为 untracked。
- 复现：运行 `git status --short` 与 `git rev-parse --verify HEAD`。
- 预期：存在可复现 commit，可审查变更、测试删除和密钥是否被跟踪。
- 实际：无法审计历史或锁定本次验证版本；验证期间还观察到外部并发写入。
- 影响：当前 PASS 结果无法绑定到确定版本，区域 ID 旧缺陷也无法进行 commit 级追踪。
- 建议修复：完成修复后创建干净提交，确保 `.env.local` 未被跟踪，并在该 commit 上重跑验证。

### COD-V-007 — P3 Minor — 前端构建产物体积警告

- 文件/行：前端构建配置/图表模块
- 问题：`riskChartEngine` minified chunk 为 507.96 kB，超过 Vite 500 kB 警戒线。
- 复现：`cd frontend && npm run build`。
- 预期：无构建告警或明确接受阈值。
- 实际：构建通过但输出 chunk-size warning。
- 影响：首屏加载可能受影响，不阻断 Demo。
- 建议修复：按需动态加载 ECharts 或配置 manualChunks。

## Test Results

| 验证域 | 结果 |
|---|---|
| 自动化测试 | PASS |
| Demo 脚本 | PASS |
| 前端生产构建 | PASS WITH WARNING |
| 广州场景 | FAIL |
| Synthetic Agent | PASS |
| Ontology | FAIL |
| Event Flow | PASS |
| SQLite Audit | PASS；字段含 event_id/type/subject/source/confidence/time/payload，四类关键事件均存在 |
| Risk Engine | PASS；contributors 可解释，前端未直接写 risk |
| Time Decay | PARTIAL FAIL（ZoneEntered 不衰减） |
| State Machine | FAIL（无非法转换保护） |
| World Behavior Model | PASS |
| Seed Reproducibility | PASS |
| What-if Isolation | PASS |
| Mock CV | PARTIAL FAIL（缺 CrowdDetected） |
| Agent Grounding | PASS |
| AMap / Fallback | 快速抽查 PASS：真实 AMap 加载；无效 Key 约 10 秒后进入 Demo 降级空间视图 |
| Browser E2E | 未做完整验收（按 Fast Validation 指令停止）；已验证 5 次刷新均为 80 主体/84 AMap markers、四步链、预测、策略与 Agent 问答 |
| Secret Scan | PASS |
| Personal Data Scan | PASS |

## 需要 ZCode 修复的问题

1. 将整个 Demo 场景从无锡坐标统一迁移到广州，并增加自动化范围断言。
2. 修复 Ontology 关系模型和非法输入校验：subject_id 条件必填、经纬度范围、关系枚举。
3. 为 ZoneEntered 补充可验证的时间衰减或明确的持续状态超时机制。
4. 为状态机增加合法转换守卫和非法跳转测试。
5. 将 CrowdDetected 与 CrowdGathered 分层实现。
6. 在最终 commit 中再次确认全仓仅使用 `school_zone_001`，消除用户已确认的旧 ID 不一致，并提供可审计 Git 基线。
7. 修复后由 Codex 在同一 commit 上重跑 P0/P1；第一轮到此停止。

## Final Decision

**VALIDATION FAILED**

失败主因：广州场景未实现（未解决 P1），且 Ontology、ZoneEntered 衰减、状态机和 Mock CV 仍有 P2 缺陷。根据验收规则，存在未解决 P1 时不得标记 `VALIDATION PASSED` 或 `DEMO READY`。

---

## Round 2 Revalidation

### Bound Git Baseline

- Git Commit：`313fb8a108fe271e1206ca7dacbe2bff8bc63f46`
- `git rev-parse HEAD`：精确匹配指定 Commit。
- 验证开始及报告更新前：业务工作区干净，无 VERSION DRIFT。
- `git ls-files frontend/.env.local`：无输出，真实本地配置未进入 Commit。
- 该 Commit 是仓库根提交，不存在父提交，无法进行父提交级“删除旧测试”对比；已改为审查全部测试源码。未发现 `skip`、`xfail`、降低核心断言或以 mock 替代核心实现。

### COD-V Closure Status

| Issue | Status | 独立复验证据 |
|---|---|---|
| COD-V-001 广州场景 | **CLOSED** | `city='广州市'`、中心 `[113.2644, 23.1291]`；80 Agent 的 position/destination/history、Place、Zone、运行时轨迹均通过广州范围检查；当前业务代码无旧 `120.* / 31.57 / 31.58` 坐标 |
| COD-V-002 Ontology | **CLOSED** | lng=999、lat=999、缺 subject_id、非法 EventType、非法 risk_level、非法 metadata.position 均返回 422；关系支持 located_at/enters/gathers_with/occurs_at/changes/affects；进入/退出及聚集/解散关系正确增删 |
| COD-V-003 Zone 风险语义 | **CLOSED** | `SensitiveZoneActive` 在 T0 与 T+60min 均为 18.0；ZoneExited 后消失；CrowdGathered `20.0→0.31`、RiskObjectDetected `35.0→8.75` 保持事件衰减 |
| COD-V-004 State Machine | **CLOSED** | 合法 Idle+MoveStarted→Moving；非法 Idle+MoveStopped 保持 Idle，metadata 写入 `rejected_transition`，SQLite payload 可追溯 |
| COD-V-005 Crowd 分层 | **CLOSED** | Mock CV `crowd` 产出 CrowdDetected；与 CrowdGathered 独立共存；权重实测 9.1（confidence 0.91）与 20.0 |
| COD-V-006 Git 基线 | **CLOSED** | 固定 HEAD 存在且匹配；验证期间无业务代码漂移；`.env.local` 未被跟踪 |

### Round 2 Test Matrix

| 验证项 | 结果 | 证据 |
|---|---|---|
| pytest | **PASS** | `40 passed in 1.11s` |
| Demo test | **PASS** | `DEMO READY`；风险 `28.8→28.8→49.5→72.5→100.0` |
| Frontend build | **PASS WITH P3 WARNING** | 635 modules；构建成功；ECharts chunk 507.96 kB |
| 广州场景 | **PASS** | UI 清晰显示“广州演示场景 / SYNTHETIC DATA”；真实底图显示广州市 |
| Synthetic Agent | **PASS** | 80/80 synthetic；60 tick 产生 481 个事件；80 个主体均移动；固定 seed 两次结果一致；所有运行时位置仍在广州范围 |
| Ontology | **PASS** | 六类非法黑盒输入全部 422；关系动态增删通过 |
| State Machine | **PASS** | current state + event type guard、非法拒绝、metadata/SQLite 审计通过 |
| Risk / Time Semantics | **PASS** | Zone 持续状态贡献与 Crowd/RiskObject 事件半衰减均符合本轮规则 |
| Core Event Flow | **PASS** | MoveStarted→ZoneEntered→CrowdDetected→CrowdGathered→AlertTriggered→RiskObjectDetected；UI 风险 `29→29→50→60→83→100` |
| Prediction | **PASS** | 5/10/30 min 均可运行；Scenario A 的 10min=26.8，Scenario B 的 10min=100.0，概率亦不同，非固定返回 |
| What-if Isolation | **PASS** | 实时 WorldState 序列化前后相等；none=100、warn=68、guide_leave=41、intervene=16 |
| Mock CV | **PASS** | Person/Vehicle/CrowdDetected/RiskObject 标准事件链可用 |
| Agent Grounding | **PASS** | 风险解释使用 get_risk_analysis/get_active_events；无 RiskObject 状态不编造；未来问题仅调用 predict_future；E2E 回答与 UI 风险同为 100 |
| SQLite | **PASS** | 含 event_id/type/subject_id/source/confidence/occurred_at/payload；五类关键事件均存在；rejected_transition 可查询 |
| AMap | **PASS — ONLINE VERIFIED** | 有效 Key 下真实高德广州底图加载；80 Agent Marker、school_zone_001 500m Circle、历史/预测 Polyline、Event Marker、Agent/Event InfoWindow 均验证 |
| Browser E2E | **PASS** | 唯一端口隔离实例完成事件链、10min Prediction、WARN/GUIDE/INTERVENE、状态隔离及 Agent 解释；Console 0 error，操作网络响应正常 |
| Map Lifecycle | **PASS** | 连续 5 次加载均为 80 Agent Marker、84 总 Marker、0 Event Marker、1 个 AMap script，无重复；Console 0 error；组件 cleanup 调用 `map.destroy()` |
| Secret Scan | **PASS** | 无硬编码 key/token/password/secret；仅跟踪 `.env.example`；未在报告泄露真实值 |
| Personal Data | **PASS** | 手机号/身份证模式无匹配；无真实人脸、真实轨迹或真实在逃人员数据；全部 Person 为 Synthetic |
| Test Integrity | **PASS WITH LIMITATION** | 40 项测试断言覆盖实际 API/运行时/SQLite；无 skip/xfail/核心 mock。根提交无父版本，无法证明历史测试未被删除，但未发现规避测试证据 |

### Browser Isolation Note

首次使用共享 `8000/5173` 实例时，另一浏览器标签保留自动 Tick，导致实时 World State 串扰。该混合结果未用于通过判定。最终核心 E2E 使用运行时隔离的 `8002/5174` 实例（同一固定 Commit、未改仓库文件）重新执行并通过；验证服务已停止。

### Remaining Warning

- **P3 Minor**：`riskChartEngine` 构建产物 507.96 kB，超过 Vite 默认 500 kB 提示阈值。属于非核心性能警告，不阻断黑客松 Demo。

### Round 2 Final Decision

**VALIDATION PASSED WITH WARNINGS — DEMO READY**

依据：40 项 pytest、Demo、前端构建、COD-V-001～006、核心 E2E、What-if Isolation、Agent Grounding、真实广州 AMap、Secret Scan 与 Synthetic Data 均通过；无 P0、无未解决 P1。仅剩 ECharts chunk-size P3 警告。

---

## Round 3 — CV & Display Name Validation

### Bound Git Baseline

- Git Commit：`35a624e4cf0ffcd06c91643f74624c2d9855566d`
- 验证开始时 `git rev-parse HEAD` 精确匹配，工作区干净；验证期间未修改业务代码。
- `docs/codex-validation-report.md` 相对上一基线的差异判定为 **A 类**：提交了上一轮 Codex 已生成的 Round 2 报告内容，未发现 ZCode 重写或美化本轮结论的证据。
- 本节由 Codex 独立追加；最终工作区只允许本报告产生变更。

### Automated Regression

| 项目 | 结果 | 实测证据 |
|---|---|---|
| pytest | **PASS** | `56 passed in 1.86s`，无 skip/xfail |
| demo_test | **PASS** | `DEMO READY` |
| npm test | **PASS** | 2 files，`10 passed` |
| npm build | **PASS WITH P3 WARNING** | 638 modules；构建成功；`riskChartEngine` 507.96 kB chunk warning |
| Test Integrity | **PASS** | 相对基线新增后端 16 项、前端 10 项相关测试；未发现删除旧测试、降低断言、`.only`、skip 或 xfail |

### Validation Matrix

| 验证项 | 结果 | 独立证据 |
|---|---|---|
| Validation Report Integrity | **PASS** | 判定为 A 类历史报告入库；本轮未依赖 Commit 内既有结论 |
| Display Name API | **PASS** | World State 返回 80 个 Agent；`agent_A=模拟人员001`、第 20 个 `agent_T=模拟人员020`、`agent_50=模拟人员050`、`agent_80=模拟人员080`；80/80 `synthetic=true` |
| ID Stability | **PASS** | World State 字典键与 Agent.id 80/80 相等；源码中 display_name 仅用于展示/模拟元数据，Event、Relation、Simulation、Agent Tools 与 SQLite subject 均继续使用 Agent ID |
| Chinese Labels | **PASS** | low/medium/high 与 7 个 behavior_state 均映射为中文；未知值安全回退原值；未错误要求 Agent 枚举存在 critical |
| AMap InfoWindow | **PASS — ONLINE VERIFIED** | 真实广州高德在线，80 Marker；指定 001/020/050/080 均存在。agent_50 显示中文字段、Agent ID、实际坐标与风险值，不含 `risk_level/risk_score/behavior_state/position` 旧字段名 |
| Latest State Behavior | **PASS** | agent_50 首次显示 28.8；CV 后 Marker 重建并写入最新 extData，再次点击显示 75.0；调用链包含 getExtData → formatter → setContent/open |
| Formatter / HTML Escape | **PASS** | Agent InfoWindow 统一经过 `buildAgentInfoWindowContent()`；运行时注入 `<测试>&\"'` 展示名后未生成 script 或注入标签，特殊字符按文本显示 |
| Vite Runtime Consistency | **PASS** | `5173` 实际返回的 infoWindow/overlays/CV 模块均包含新版 formatter、get/setExtData、runningRef 与 sceneId API 调用；浏览器实际显示中文模板和新版 CV UI，无旧 transform cache |
| Detection Schema | **FAIL — P2** | confidence 越界会拒绝；预置四场景 bbox 均在画面内。但 BBox 模型会接受 `x=.9,width=.2` 或 `y=.9,height=.2`，缺少 `x+width<=1`、`y+height<=1` 跨字段校验 |
| Four CV Scenes | **PASS** | 浏览器逐一运行：normal=1 Detection/PersonDetected；crowd=4/含 CrowdDetected；risk_object=2/含 RiskObjectDetected；high_risk=5/Person×3+CrowdDetected+RiskObjectDetected；scene_id 与 UI 选择一致 |
| Crowd Layering | **PASS** | MockCVProvider 所有入口只产生 CrowdDetected 感知事实，不产生 CrowdGathered；空间/行为层 CrowdGathered 链路保持独立 |
| CV Event Flow | **PASS** | UI POST → Provider → Detection → Standard Event → world_service.publish → Event Bus → World State/Risk；源码和 Provider 黑盒均证明 CV 不直接修改 risk_score |
| Risk Update | **PASS** | Reset 后 `28.8→75.0`；contributors 为 CrowdDetected 9.1、RiskObjectDetected 31.15、高风险倍率 9.79，属于后端规则计算而非前端固定赋值 |
| Alert Deduplication | **PASS** | high_risk 产生 1 个 AlertTriggered；继续发布非关键 PersonDetected 后 Alert 数仍为 1，无递归事件风暴 |
| SQLite Audit | **PASS** | mock_cv 记录具备 event_id/type/subject_id/source/confidence/timestamp/payload；payload 含 scene_id/detection_id/label/bbox；subject 均为 agent_* ID |
| CV UI / Animation | **PARTIAL — P1** | 1920×1080 下初态、四场景、扫描线、Detection Box、Label、Confidence 与完成状态均可见；最终框使用后端 Detection bbox。**1366×768 下 CV Panel 高度仅约 2px，被 `.panel{overflow:hidden}` 裁掉，开始识别入口不可访问** |
| Duplicate Submission | **PASS** | 浏览器快速双击 high_risk 后 SQLite mock_cv 记录仅增加 5 条，等于一次场景事件数；runningRef 实际有效 |
| Timeline | **PASS** | high_risk 后真实 Timeline 显示 PersonDetected×3、CrowdDetected、RiskObjectDetected、AlertTriggered，数据来自后端 World State |
| AMap Event Marker | **PARTIAL — P2** | CrowdDetected 与 RiskObjectDetected Marker 均实际存在；但两者同位置完全重叠，点击 CrowdDetected Marker 实际打开 RiskObjectDetected InfoWindow，无法可靠检查/访问 Crowd Marker 信息 |
| Agent Grounding | **PASS** | Reset 前回答“无活跃事件”；CV 后仅引用真实 CrowdDetected、RiskObjectDetected、AlertTriggered/contributors，tools_used 为 get_risk_analysis/get_active_events，无 CrowdGathered 幻觉 |
| Prediction | **PASS** | 10min Prediction 从 26.8/低风险基线变化为 82.0（单次 high_risk）；浏览器高风险累积状态亦得到不同预测，模型为 transparent_rule_probability_v1 |
| What-if | **PASS** | none/warn/guide_leave/intervene 结果有差异；浏览器 WARN 显示 100→68；运行前后 World State SHA-256 与实时风险完全相同 |
| Reset | **FAIL — P1** | 世界风险、Timeline、事件 Marker 与 Agent 状态能重置；但 UI Reset 后 CV Panel 仍显示“识别完成”、5 个框及上次结果，未回到待识别状态，违反重置完整性要求 |
| Synthetic Visual Data | **PASS** | 画面由 CSS 合成，无图片/视频资产、真实人脸或摄像头流；UI 明示 Synthetic Visual Data / 模拟视觉数据与广州演示场景 |
| Secret | **PASS** | `.env.local` 被忽略且不在 Commit；新增文件密钥值候选为 0；报告未输出 AMap Key/securityJsCode |
| Personal Data | **PASS** | 80 个名称仅为模拟人员001～080；无真实姓名、人脸、监控视频或个人敏感数据 |
| Browser E2E | **FAIL** | 1920×1080 主链可运行，Console 0 error；但 1366×768 无法访问 CV 操作入口，Reset 留存 CV 结果，且 Crowd Event Marker 点击被重叠 Marker 劫持，完整演示验收不成立 |

### Issues for ZCode

1. **COD-V3-001 — P1：1366×768 CV Panel 被布局压缩并裁切。** `.right-column` 配置两行但包含 CV、Simulation、Chat 三个子面板；在 1366 宽布局中 CV Panel 高度约 2px。需要调整 grid rows/最小高度/滚动策略，并在 1366×768 与约 720px 高视口复验。
2. **COD-V3-002 — P1：Reset 未清理 CVDetectionPanel 本地状态。** Reset 后必须清除 phase/result/detections/timers/runningRef，并回到“待识别 · 模拟画面就绪”。
3. **COD-V3-003 — P2：BBox 缺少边界和校验。** 增加模型级 `x+width<=1` 与 `y+height<=1` 校验及非法输入单测。
4. **COD-V3-004 — P2：同主体 CV Event Marker 完全重叠。** 需要聚合、偏移、蜘蛛展开或可选择列表，保证 CrowdDetected 与 RiskObjectDetected 均可点击且 InfoWindow 对应正确 Event。
5. **COD-V3-005 — P3：ECharts chunk 507.96 kB。** 非本轮核心阻断，可后续做懒加载或 manualChunks。

### Round 3 Final Decision

**VALIDATION FAILED**

失败依据：新增 display_name、中文真实 AMap InfoWindow、四场景 CV 事件链、风险、告警、审计、Prediction、What-if、Agent Grounding、Secret 与 Synthetic Data 大部分通过；但存在两个未解决 P1（1366×768 下 CV Demo 不可操作、Reset 未清理 CV 结果）及两个 P2（BBox 跨字段越界未拒绝、同位置 Event Marker 不可可靠点击）。因此完整 Browser E2E 与核心演示验收不能通过。
