# CV 模型评估报告（Synthetic-domain）

> 指标诚实声明：本文全部指标均为 **Synthetic-domain CV accuracy**（合成域内与合成 OOD 域），
> 不代表真实监控场景准确率。即便 test mAP50 = 0.9223，也**绝不表述为「真实场景准确率 92%」**。
> 评估脚本 `scripts/evaluate_cv_model.py` 只在训练结束后运行一次，test split 与 OOD split
> 从不参与训练与 early stop。

## 模型卡片

| 项 | 值 |
| --- | --- |
| 模型文件 | `models/cv_detector/best.pt`（5.16 MB） |
| SHA256 | `131899505385e67e14e151cb768b0d844587165ef55d6ff5d63c17f9031606c2` |
| 架构 | Ultralytics YOLO26n（`yolo26n.pt` 微调，122 layers / 2,375,421 参数 / 5.3 GFLOPs） |
| Ultralytics / Torch | 8.4.123 / 2.11.0+cu128 |
| 训练配置 | epochs 40 · imgsz 640 · batch 32 · workers 4 · seed 42 · patience 10（未触发 early stop） |
| 硬件 | NVIDIA GeForce RTX 5080 16GB（CUDA:0），训练耗时 1.925 小时 |
| 数据集 | `data/cv_synthetic`（50,000 张 / 149,751 实例，seed 42，dataset_hash `e780807538d213731313ed672769cdd909599c3ad6e03ea3ffcd5bd219c1b1d4`，train/val/test = 35000/7500/7500） |
| 类别 | 仅 3 类：`person / risk_object / vehicle`（`crowd` 是感知层聚合结果，不是训练类别） |
| 推理延迟 | **7.57 ms/张**（GPU cuda:0，100 张 test 图实测，含 warmup） |

## Test split 指标（7,500 张 / 22,552 实例，独立于训练与调参）

| mAP50-95 | mAP50 | mAP75 | Precision | Recall |
| --- | --- | --- | --- | --- |
| **0.8852** | **0.9223** | 0.9044 | 0.9872 | 0.8990 |

Per-class AP50-95：

| person | risk_object | vehicle |
| --- | --- | --- |
| 0.8067 | 0.8818 | 0.9670 |

person 最低，符合预期：小目标（small 档 18%）与遮挡（partial/heavy 合计约半数）主要落在 person 类。

## OOD 指标（5,000 张 / 19,400 实例，seed 2026，夜间 49.8% / 雾天 42.2% 分布偏移）

| mAP50-95 | mAP50 | mAP75 | Precision | Recall |
| --- | --- | --- | --- | --- |
| **0.8454** | **0.8925** | 0.8695 | 0.9827 | 0.8646 |

Per-class AP50-95：person 0.7419 · risk_object 0.8342 · vehicle 0.9602。

与 test 相比 mAP50-95 下降 0.0398（0.8852 -> 0.8454），person 下降最大（-0.0648）——夜间低光 +
雾天条件下小目标 person 最难。这是**诚实报告的域偏移退化**，不是缺陷修复项。

## 训练期 val 过程指标（仅参考，非最终指标）

mAP50 0.9205 · mAP50-95 0.8857 · P 0.9866 · R 0.8968（val split，用于 best.pt 择优）。

## 复现

```powershell
python scripts/generate_cv_dataset.py --images 50000 --seed 42
python scripts/generate_cv_dataset.py --images 5000 --seed 2026 --ood --out data/cv_synthetic_ood
python scripts/train_cv_model.py --data data/cv_synthetic/data.yaml --epochs 40 --imgsz 640 --batch 32 --workers 4 --seed 42
python scripts/evaluate_cv_model.py --data data/cv_synthetic/data.yaml --ood-data data/cv_synthetic_ood/data.yaml
```

同 seed 生成 -> 同 dataset_hash；指标文件 `models/cv_detector/metrics.json`（含 test/ood/latency 全量数据与混淆矩阵）。

## 已知局限（诚实声明）

1. **合成到真实的域差距**：训练/评估数据 100% 程序化合成（Pillow 渲染剪影与抽象物品），
   未使用任何真实监控图像。真实场景的精度未经测量，不能由本文数字外推。
2. **类别语义抽象**：`risk_object` 是抽象几何物品（UI 文案「疑似风险物品」），不是真实违禁品识别。
3. **person 为 anonymous synthetic silhouette**：无真实人脸/人体数据，不涉及隐私；也不具备真实行人重识别能力。
4. **Crowd 不是模型能力**：CrowdDetected 由感知层聚合（>=3 person + 成对中心距 <=0.30）产生，
   CrowdGathered 永远由行为/空间规则层确认；模型只输出 3 类检测。
5. **混淆矩阵与 per-class AP** 见 `models/cv_detector/metrics.json`（`confusion_matrix` 字段）。
