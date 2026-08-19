# Model Evaluation（全部指标来自独立 test split，禁止人工填写）

数据：120,000 Synthetic Episodes（seed=42），
train 84,000 / validation 18,000 / test 18,000，
按 episode_id 切分，无跨集泄漏。所有训练数据 100% Synthetic。

## Risk Forecast（risk_hgb_v1，test split）

| Horizon | MAE | RMSE | R2 | Baseline mean MAE | Baseline rule MAE |
|---|---|---|---|---|---|
| 5m | 0.0944 | 0.1276 | 1.0 | 21.4686 | 0.0 |
| 10m | 0.0917 | 0.1223 | 1.0 | 22.3851 | 0.0 |
| 30m | 0.088 | 0.1145 | 1.0 | 23.3033 | 0.0 |

- Baseline 1（mean predictor）：常数预测 train 均值。
- Baseline 2（rule predictor）：按 predict_world_state 透明规则从特征重算。

## Policy（policy_hgb_v1，test split）

- Accuracy: 0.9969
- Macro F1: 0.9942
- Weighted F1: 0.9969
- Baseline majority（intervene）Accuracy: 0.4186
- Baseline heuristic Accuracy: 0.4681（risk>=60 或 (risk_object 且 risk>=40) -> intervene；crowd 且 risk>=25 -> guide_leave；risk>=15 -> warn；否则 none）

Confusion Matrix（行=真实，列=预测，顺序 none/warn/guide_leave/intervene）：

| 真实\预测 | none | warn | guide_leave | intervene |
|---|---|---|---|---|
| none | 679 | 3 | 0 | 0 |
| warn | 18 | 3146 | 0 | 0 |
| guide_leave | 0 | 0 | 6595 | 25 |
| intervene | 0 | 0 | 9 | 7525 |

## 性能

- 训练耗时：risk 5.74s / policy 2.81s
- 推理延迟：risk 0.003875 ms/条，policy 0.002797 ms/条
- 模型文件：risk 2852 KB，policy 1042 KB
- 数据生成耗时：88.93s

以上均为 Synthetic Data 训练结果，不代表真实城市预测。
