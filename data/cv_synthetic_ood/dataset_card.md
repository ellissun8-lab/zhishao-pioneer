# Synthetic CV Dataset Card

- 类型：OOD（out-of-distribution）独立评估集（100% Synthetic Visual Data，程序化渲染）
- 图片数：5000
- 实例数：19400
- seed：2026
- dataset hash：15ae99da0b2a5318b10310f39af725f548e7bcb5a238ea6a74233d7958703e57
- 类别：0 person / 1 risk_object / 2 vehicle

## 数据来源声明

- 100% Synthetic Visual Data（Pillow 程序化渲染）
- No real faces（person 为 anonymous synthetic silhouette）
- No real surveillance footage
- No real Guangzhou residents
- No real police image data
- risk_object 为抽象风险物品（bag-like / dark box / synthetic prop），非写实武器

## 已知限制

- synthetic-to-real domain gap：本数据集指标仅代表 Synthetic-domain CV accuracy，
  不代表真实监控场景准确率
- crowd 不作为检测类别：CrowdDetected 由 >=3 person detection 的空间聚合规则产生

## 重建命令

```bash
python scripts/generate_cv_dataset.py --images 5000 --seed 2026 --ood
```
