# MVP 测试报告

- 测试时间：2026-08-18（Asia/Singapore）
- 测试环境：Windows、Python 3.12.10、Node.js 24.15.0、Vite 7.3.6
- 数据声明：全部 Agent、关系、轨迹和风险事件均为 Synthetic Data
- 总结：**PASS / Demo Ready**

## 自动化场景

| 场景 | 输入 | 预期 | 实际 | 状态 |
|---|---|---|---|---|
| Case 01 普通区域 | 低风险 Agent，无敏感区事件 | Risk < 30 | 测试断言通过 | PASS |
| Case 02 敏感区 | 高风险 Agent_A 发送 ZoneEntered | Risk 上升 | 风险从 28.7 上升至 49.4 | PASS |
| Case 03 三人聚集 | CrowdGathered，confidence=1 | 规则贡献 +20 | `CrowdGathered: 20` | PASS |
| Case 04 风险物品 | RiskObjectDetected，confidence=1 | 风险明显增加 | 风险贡献 +35，端到端风险升至 100 | PASS |
| Case 05 发送预警 | 相同 World State 分别运行 NONE/WARN | WARN 风险低于 NONE | NONE=100，WARN=68 | PASS |
| 状态隔离 | 在当前状态上运行 What-if | 不污染实时 World State | 深拷贝前后 JSON 一致 | PASS |
| Agent 工具约束 | 询问当前风险原因 | 使用风险和事件工具 | 使用 `get_risk_analysis`、`get_active_events` | PASS |

## 强制验收命令

### `pytest -q`

结果：`8 passed in 0.86s` — **PASS**

### `python scripts/run_demo_test.py`

结果：`DEMO READY` — **PASS**

- 风险演化：`28.7 → 28.7 → 49.4 → 72.4 → 100.0`
- 不干预：`100 → 100`
- 发送预警：`100 → 68`
- 引导离开：`100 → 41`
- 现场处置：`100 → 16`

### `npm run build`

结果：TypeScript 与 Vite 生产构建完成，633 个模块转换成功 — **PASS**

ECharts 风险图已拆为按需异步块；构建仍提示该图表块略高于 500 kB（gzip 174.09 kB），属于性能提示，不影响编译或运行。

## 浏览器运行验证

使用本地 FastAPI（8000）与 Vite（5173）进行真实页面验证：

- 页面标题、品牌、Synthetic Data 标识、80 个模拟主体正常显示
- 未配置高德 Key 时正确进入空间演示降级底图
- 无 Vite 错误覆盖层，无浏览器 console warning/error
- 连续点击 4 次“推进下一事件”后：风险 100、事件数 4、包含 RiskObjectDetected
- 点击“比较全部策略”后显示 4 组结果
- 点击风险解释问题后收到 1 条 Agent 工具化回答

结论：**PASS**

## 已知环境项

高德地图真实底图需要使用者在 `frontend/.env.local` 配置 `VITE_AMAP_KEY` 与 `VITE_AMAP_SECURITY_JS_CODE`。仓库未包含或硬编码真实密钥；无 Key 时采用明确标识的降级底图，不阻塞其余 Demo 链路。

