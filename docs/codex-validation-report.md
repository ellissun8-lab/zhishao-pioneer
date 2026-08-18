# 智哨先锋 Codex 独立测试与验证报告

## Validation Status

**VALIDATION FAILED**

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
