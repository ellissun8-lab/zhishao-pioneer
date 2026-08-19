# Model Evaluation（全部指标来自独立 test split，禁止人工填写）

数据：120,000 Synthetic Episodes（seed=42），
train 84,000 / validation 18,000 / test 18,000，
按 episode_id 切分，无跨集泄漏。所有训练数据 100% Synthetic。

## Risk Forecast（risk_hgb_v1，test split）

| Horizon | MAE | RMSE | R2 | Baseline mean MAE | Baseline rule MAE |
|---|---|---|---|---|---|
| 5m | 0.0934 | 0.1268 | 1.0 | 21.443 | 0.0 |
| 10m | 0.0912 | 0.122 | 1.0 | 22.3584 | 0.0 |
| 30m | 0.0874 | 0.1138 | 1.0 | 23.2761 | 0.0 |

- Baseline 1（mean predictor）：常数预测 train 均值。
- Baseline 2（rule predictor）：按 predict_world_state 透明规则从特征重算。

## Policy（policy_hgb_v1，test split）

- Accuracy: 0.9947
- Macro F1: 0.9911
- Weighted F1: 0.9947
- Baseline majority（intervene）Accuracy: 0.4178
- Baseline heuristic Accuracy: 0.4682（risk>=60 或 (risk_object 且 risk>=40) -> intervene；crowd 且 risk>=25 -> guide_leave；risk>=15 -> warn；否则 none）

Confusion Matrix（行=真实，列=预测，顺序 none/warn/guide_leave/intervene）：

| 真实\预测 | none | warn | guide_leave | intervene |
|---|---|---|---|---|
| none | 696 | 6 | 0 | 0 |
| warn | 19 | 3074 | 15 | 0 |
| guide_leave | 0 | 25 | 6630 | 15 |
| intervene | 0 | 0 | 16 | 7504 |

## 性能

- 训练耗时：risk 6.78s / policy 3.26s
- 推理延迟：risk 0.003672 ms/条，policy 0.003142 ms/条
- 模型文件：risk 2767 KB，policy 1226 KB
- 数据生成耗时：110.73s

以上均为 Synthetic Data 训练结果，不代表真实城市预测。
