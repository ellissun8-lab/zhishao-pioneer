import { agentDisplayName, behaviorStateLabel, riskLevelLabel } from '../labels'
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
    ['Agent ID', `${agent.id} · Synthetic Data`],
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
    ['timestamp', new Date(event.timestamp).toLocaleString('zh-CN', { hour12: false })],
    ['source', event.source],
    ['confidence', `${(event.confidence * 100).toFixed(0)}%`],
    ['subject', event.subject_id ?? 'system'],
  ]
  const details = rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')
  return `<section class="amap-info-card"><header>${escapeHtml(event.type)} · Event</header>${details}</section>`
}
