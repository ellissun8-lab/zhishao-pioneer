// 黑客松现场演示用的中文名称映射；仅作用于展示层，不改变 World State 字段本身
export const RISK_LEVEL_LABELS: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '极高风险',
}

export const BEHAVIOR_STATE_LABELS: Record<string, string> = {
  idle: '静止',
  moving: '移动中',
  entering_sensitive_zone: '进入敏感区域',
  gathering: '聚集中',
  risk_escalating: '风险升级',
  dispersing: '疏散中',
  resolved: '已解除',
}

export const EVENT_TYPE_LABELS: Record<string, string> = {
  MoveStarted: '开始移动',
  MoveStopped: '停止移动',
  ZoneEntered: '进入敏感区域',
  ZoneExited: '离开敏感区域',
  CrowdDetected: '感知人流聚集',
  CrowdGathered: '确认形成聚集',
  CrowdDispersed: '聚集解除',
  PersonDetected: '检测到人员',
  VehicleDetected: '检测到车辆',
  RiskObjectDetected: '检测到风险物品',
  AlertTriggered: '触发预警',
  InterventionApplied: '应用干预',
}

export const SOURCE_LABELS: Record<string, string> = {
  synthetic_runtime: '模拟运行时',
  mock_cv: '模拟视觉感知',
  rule_engine: '风险规则引擎',
  risk_engine: '风险引擎',
  simulation: '策略推演',
  what_if: '策略副本',
  demo_public_dataset: '公开演示数据',
  system: '系统',
}

export const RULE_LABELS: Record<string, string> = {
  base_risk: '基础风险',
  sensitive_zone: '敏感区域',
  crowd_risk: '聚集风险',
  risk_object: '风险物品',
  high_risk_multiplier: '高风险倍率',
  CrowdDetected: '感知人流聚集',
  CrowdGathered: '确认形成聚集',
  RiskObjectDetected: '检测到风险物品',
  AlertTriggered: '触发预警',
  InterventionApplied: '应用干预',
}

export function agentDisplayName(agent: { id: string; display_name?: string }): string {
  return agent.display_name || agent.id
}

export function riskLevelLabel(level: string): string {
  return RISK_LEVEL_LABELS[level] ?? level
}

export function behaviorStateLabel(state: string): string {
  return BEHAVIOR_STATE_LABELS[state] ?? state
}

export function eventTypeLabel(type: string): string {
  return EVENT_TYPE_LABELS[type] ?? type
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

export function ruleLabel(rule: string): string {
  return RULE_LABELS[rule] ?? EVENT_TYPE_LABELS[rule] ?? rule.replaceAll('_', ' ')
}
