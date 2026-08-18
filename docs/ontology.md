# 城市本体

MVP 将对象统一为 `Person`、`Place`、`Zone`、`Event`、`Action`，关系包括 `located_at`（Person->Place）、`enters`（Person->Zone）、`gathers_with`（Person->Person）、`occurs_at`（Event->Place）、`changes`（Event->WorldState）、`affects`（Action->Event）。

- `Person`：仅为 Synthetic Agent，包含风险等级、位置、行为状态、社交组。
- `Place`：学校、医院、车站等城市设施，保留数据来源。
- `Zone`：普通或敏感空间区域，带半径和敏感度。
- `Event`：所有轨迹、CV 和干预输入的唯一交换格式，保留时间、置信度和来源。
- `Action`：Observe、Warn、GuideLeave、Dispatch、Intervene。

事件经 `EventBus → WorldStateUpdater → BehaviorEngine` 更新世界状态，确保输入、规则贡献和风险结果可追溯。

