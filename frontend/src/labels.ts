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

export function agentDisplayName(agent: { id: string; display_name?: string }): string {
  return agent.display_name || agent.id
}

export function riskLevelLabel(level: string): string {
  return RISK_LEVEL_LABELS[level] ?? level
}

export function behaviorStateLabel(state: string): string {
  return BEHAVIOR_STATE_LABELS[state] ?? state
}
