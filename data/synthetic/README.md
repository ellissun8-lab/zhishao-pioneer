# Synthetic Training Data

本目录只保存程序生成的训练数据说明与数据卡；Parquet 数据集由脚本本地重建，不纳入 Git。数据不对应任何真实个人。

完整流水线：

```powershell
python scripts/generate_training_data.py --episodes 120000 --seed 2025
python scripts/train_risk_model.py
python scripts/train_policy_model.py
python scripts/evaluate_models.py
```

固定拆分为 84,000 / 18,000 / 18,000（train / validation / test），按 `episode_id` 隔离。风险标签调用 `predict_world_state()` 生成，策略标签来自四策略 What-if Simulation 的效用比较。

这是对透明规则世界模型和仿真器的 surrogate learning（代理学习）演示，不是现实世界风险模型。接近完美的指标、Risk R²≈1 与 rule baseline MAE=0 均源于确定性教师规则；不能解释为真实世界泛化能力。
