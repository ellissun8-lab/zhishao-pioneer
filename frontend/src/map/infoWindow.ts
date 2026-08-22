import { agentDisplayName, behaviorStateLabel, eventTypeLabel, riskLevelLabel, sourceLabel } from '../labels'
import type { Agent, WorldEvent } from '../types'

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

// 真实 AMap Agent InfoWindow 的唯一内容生成器；
// 降级视图之外任何 Agent 弹窗展示都必须走这个函数，避免出现第二套模板
export function buildAgentInfoWindowContent(agent: Agent): string {
  const rows: Array<[string, string]> = [
    ['主体编号', `${agent.id} · 模拟主体`],
    ['风险等级', riskLevelLabel(agent.risk_level)],
    ['风险评分', agent.risk_score.toFixed(1)],
    ['行为状态', behaviorStateLabel(agent.behavior_state)],
    ['当前坐标', `${agent.position.lng.toFixed(6)}, ${agent.position.lat.toFixed(6)}`],
  ]
  const details = rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')
  return `<section class="amap-info-card"><header>${escapeHtml(agentDisplayName(agent))}</header>${details}</section>`
}

export function buildEventInfoWindowContent(event: WorldEvent): string {
  const rows: Array<[string, string]> = [
    ['发生时间', new Date(event.timestamp).toLocaleString('zh-CN', { hour12: false })],
    ['事件来源', sourceLabel(event.source)],
    ['置信度', `${(event.confidence * 100).toFixed(0)}%`],
    ['关联主体', event.subject_id ?? '系统'],
  ]
  const details = rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')
  return `<section class="amap-info-card"><header>${escapeHtml(eventTypeLabel(event.type))}</header>${details}</section>`
}
