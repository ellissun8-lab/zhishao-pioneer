# Synthetic Training Dataset Card

## Dataset Size
120,000 Synthetic Episodes（100% Synthetic Data）

## Generated from
- World Behavior Model（backend/app/behavior/prediction.py::predict_world_state）
- Event Simulation（backend/app/simulation/engine.py::SimulationEngine）
- What-if Intervention Engine（四策略 What-if 对比 + utility 标签）

## Not
- real Guangzhou residents
- real surveillance footage
- real police data
- real personal trajectories

所有 Episode 均为参数化采样的模拟世界状态，不含任何真实个人数据。

## Reproducibility
- seed: 42
- episodes: 120,000
- intervention_cost_weight: 2.5
- 首批 100 条记录 sha256: `2b92e31c8e5e8765550ec6a874e165a8d017f288572902fdd3247cb3553d734b`
- 同参数重跑生成一致的统计与标签

## Feature Schema
current_risk, active_event_count, nearby_agent_count, high_risk_agent_count, sensitive_zone_active, crowd_detected, crowd_gathered, risk_object_detected, vehicle_detected, average_agent_risk, event_recency_minutes, hour_of_day, crowd_size, zone_sensitivity_max, mobility_intensity, event_confidence_max

禁止把 agent id / display_name / episode id / event id 作为训练特征。

## Label Generation
- risk_5m / risk_10m / risk_30m：来自 predict_world_state(state, horizon)
- best_strategy：对同一 World State 运行 run_simulation(NONE/WARN/GUIDE_LEAVE/INTERVENE)，
  utility = risk_reduction - intervention_cost_weight * action_cost，取 utility 最大者
- 不得随机生成标签

## Train/Val/Test Split（按 episode_id 切分，禁止同 episode 跨集）
- train: 84,000
- validation: 18,000
- test: 18,000

## Distribution Summary
- strategy label distribution: {"guide_leave": 44382, "intervene": 49739, "none": 4693, "warn": 21186}
- risk score distribution: {"0-10": 9659, "10-20": 18469, "20-30": 11401, "30-40": 14250, "40-50": 16140, "50-60": 17602, "60-70": 15168, "70-80": 9978, "80-90": 5333, "90-100": 2000}
- zone active ratio: 0.8661
- risk object ratio: 0.2231
- crowd ratio: 0.3338
