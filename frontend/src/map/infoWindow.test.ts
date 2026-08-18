import { describe, expect, it } from 'vitest'
import { buildAgentInfoWindowContent } from './infoWindow'
import { riskLevelLabel } from '../labels'
import type { Agent } from '../types'

const baseAgent: Agent = {
  id: 'agent_50',
  type: 'Person',
  synthetic: true,
  display_name: '模拟人员050',
  risk_level: 'low',
  position: { lng: 113.247361, lat: 23.130402 },
  destination: null,
  behavior_state: 'idle',
  risk_score: 28.8,
  active_zone_ids: [],
  history: [],
  social_group: 'group_2',
}

describe('buildAgentInfoWindowContent', () => {
  it('renders the Chinese display template for the required agent_50 case', () => {
    const html = buildAgentInfoWindowContent(baseAgent)
    expect(html).toContain('模拟人员050')
    expect(html).toContain('agent_50 · Synthetic Data')
    expect(html).toContain('低风险')
    expect(html).toContain('28.8')
    expect(html).toContain('静止')
    expect(html).toContain('当前坐标')
    expect(html).toContain('113.247361')
  })

  it('never leaks raw English field names', () => {
    const html = buildAgentInfoWindowContent(baseAgent)
    expect(html).not.toContain('risk_level')
    expect(html).not.toContain('risk_score')
    expect(html).not.toContain('behavior_state')
  })

  it('maps every risk level and behavior state to Chinese labels', () => {
    // Agent.risk_level 本身只有 low/medium/high；critical 属于整体 RiskState.level，单独在函数层断言
    const levels: Array<['low' | 'medium' | 'high', string]> = [
      ['low', '低风险'],
      ['medium', '中风险'],
      ['high', '高风险'],
    ]
    levels.forEach(([level, label]) => {
      const html = buildAgentInfoWindowContent({ ...baseAgent, risk_level: level })
      expect(html).toContain(label)
    })
    expect(riskLevelLabel('critical')).toBe('极高风险')
    const states: Array<[string, string]> = [
      ['idle', '静止'],
      ['moving', '移动中'],
      ['entering_sensitive_zone', '进入敏感区域'],
      ['gathering', '聚集中'],
      ['risk_escalating', '风险升级'],
      ['dispersing', '疏散中'],
      ['resolved', '已解除'],
    ]
    for (const [state, label] of states) {
      const html = buildAgentInfoWindowContent({ ...baseAgent, behavior_state: state })
      expect(html).toContain(label)
    }
  })

  it('falls back to the agent id when display_name is empty', () => {
    const html = buildAgentInfoWindowContent({ ...baseAgent, display_name: '', id: 'agent_Z' })
    expect(html).toContain('agent_Z')
    expect(html).not.toContain('模拟人员')
  })
})
