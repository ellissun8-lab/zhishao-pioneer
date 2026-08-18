# 数据来源登记

## 高德地图 JS API 2.0

- 服务名称：高德地图 JS API 2.0
- URL：https://lbs.amap.com/api/javascript-api-v2/summary
- 来源：高德开放平台
- 用途：地图底图、覆盖物、空间交互及可选地图服务
- 接入方式：`@amap/amap-jsapi-loader`
- Key 类型：Web 端（JS API）
- 密钥管理：本地环境变量；部署环境优先服务端安全代理
- 说明：地图能力提供方，不作为赛事公开城市数据成果申报

## MVP 演示设施样本

- 数据名称：演示 POI 样本
- URL：本仓库 `data/demo/places.json`
- 来源：黑客松合成演示样本
- 许可证：项目内部演示用途
- 采集时间：2026-08-17
- 字段：id、category、name、lng、lat、source
- 用途：验证本体、地图覆盖物与推演链路
- 限制：当前并非真实城市公开数据；接入真实开放数据前必须补充 URL 和许可证

## Synthetic Agents

- 数据名称：80 个程序生成模拟主体
- 来源：固定随机种子 `20260817`
- 字段：id、risk_level、home_zone、current_position、destination、mobility_pattern、behavior_state、social_group、synthetic
- 用途：行为模型与 What-if 验证
- 限制：不对应任何真实人员、关系、轨迹或事件

