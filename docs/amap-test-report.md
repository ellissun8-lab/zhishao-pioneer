# 高德地图接入测试报告

- 测试时间：2026-08-18（Asia/Singapore）
- 范围：仅前端高德地图接入层与地图联动
- 后端改动：无
- 当前环境：`frontend/.env.local` 已创建，但 Key 与 securityJsCode 均为空

## 实现结果

| 项目 | 实现 | 运行验证 |
|---|---|---|
| Loader 单例 | `frontend/src/map/amap.ts` 仅有一处 `AMapLoader.load` | 静态审计 PASS |
| JS API 版本 | 高德地图 JS API 2.0 | 构建 PASS；真实 Key 待验证 |
| 生命周期 | 挂载加载、单实例创建、覆盖物更新、卸载 remove/destroy | 代码审计与 TypeScript PASS；真实 Map 销毁待 Key 验证 |
| Agent Marker | 80 个 `AMap.Marker`，坐标来自 FastAPI World State `Agent.position` | 降级视图联动 PASS；真实 AMap 待 Key 验证 |
| Agent InfoWindow | ID、Synthetic、risk_level、risk_score、behavior_state、position | 构建 PASS；真实 AMap 待 Key 验证 |
| 历史轨迹 | `AMap.Polyline`，来自 `Agent.history` | 构建 PASS；真实 AMap 待 Key 验证 |
| 预测轨迹 | 独立虚线 `AMap.Polyline`，来自 `Agent.position → Agent.destination` | 构建 PASS；真实 AMap 待 Key 验证 |
| 敏感区 | 500m `AMap.Circle` + 外圈 `AMap.Polygon`，显示 `school_zone_001` | 降级区显示 PASS；真实 AMap 待 Key 验证 |
| Event | ZoneEntered、CrowdGathered、RiskObjectDetected、AlertTriggered Marker + InfoWindow | 降级事件联动 PASS；真实 AMap 待 Key 验证 |
| What-if | 独立 Simulation Overlay、Before/After、退出恢复 | 浏览器 PASS |
| 降级模式 | 缺 Key/securityCode、Loader/网络/初始化失败自动切换 | 无 Key 浏览器 PASS |
| Synthetic 标识 | 地图状态条持续显示 `Synthetic Data / 模拟数据` | 浏览器 PASS |

## 浏览器联动结果（无 Key 降级模式）

- 页面非空，无 Vite 错误覆盖层
- 80 个 Synthetic Agent Marker 显示
- Agent_A Marker 位置从 `77.4085% / 41.7436%` 更新至 `43.16% / 55.92%`
- 产生 4 个事件，ZoneEntered、CrowdGathered、RiskObjectDetected 均在地图出现
- 风险升至 100，时间轴保持 4 条事件
- WARN Simulation 显示 `100 → 68`，模拟路径和 SIM Marker 正常
- 退出 Simulation 后临时图层消失，当前风险仍为 100、事件仍为 4
- Agent 风险解释正常
- 浏览器 console warning/error：0

## 自动验收

- `pytest -q`：8 passed
- `python scripts/run_demo_test.py`：DEMO READY
- `npm run build`：PASS（634 modules transformed）
- `@amap/amap-jsapi-loader`：1.0.1

## 密钥审计

- `.env.local` 被 `.gitignore` 的 `.env.*` 规则忽略
- `git ls-files frontend/.env.local`：NOT_TRACKED
- 源码仅通过 `import.meta.env.VITE_AMAP_KEY` 和 `VITE_AMAP_SECURITY_JS_CODE` 读取
- `AMapLoader.load` 调用点：1
- 未发现硬编码 Key

## 最终状态

实现与无 Key 降级链路已完成；由于当前没有有效高德 Key，无法完成“真实高德底图出现、真实 AMap 覆盖物/InfoWindow、真实 map.destroy”运行态验收。

**AMAP DEMO NOT READY — 等待用户配置真实 Key 后完成最终浏览器验收。**

