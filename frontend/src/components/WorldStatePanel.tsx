import type { Agent, WorldState, Zone } from '../types'
import { agentDisplayName, behaviorStateLabel, riskLevelLabel } from '../labels'

type Props = { world: WorldState; selectedAgent: Agent | null; selectedZone: Zone | null; onViewAgent?: () => void }

export function WorldStatePanel({ world, selectedAgent, selectedZone, onViewAgent }: Props) {
  const moving = Object.values(world.agents).filter((agent) => agent.behavior_state !== 'idle').length
  return (
    <section className="panel world-panel" aria-label="世界状态与当前选中主体">
      <div className="panel-heading"><span>世界状态 / 主体详情</span><em>{Object.keys(world.agents).length} 个主体 · 当前详情</em></div>
      <div className="metric-row">
        <div><strong>{Object.keys(world.agents).length}</strong><span>模拟主体</span></div>
        <div><strong>{moving}</strong><span>活跃状态</span></div>
        <div><strong>{world.active_events.length}</strong><span>事件总数</span></div>
      </div>
      {selectedAgent ? (
        <div className="selection-card">
          <div><span className={`agent-pulse ${selectedAgent.risk_level}`} /><b>{agentDisplayName(selectedAgent)}</b><small>模拟主体</small></div>
          <dl>
            <div><dt>主体编号</dt><dd>{selectedAgent.id}</dd></div>
            <div><dt>风险等级</dt><dd>{riskLevelLabel(selectedAgent.risk_level)}</dd></div>
            <div><dt>行为状态</dt><dd>{behaviorStateLabel(selectedAgent.behavior_state)}</dd></div>
            <div><dt>社会组</dt><dd>{selectedAgent.social_group}</dd></div>
            <div><dt>当前坐标</dt><dd>{selectedAgent.position.lng.toFixed(4)}, {selectedAgent.position.lat.toFixed(4)}</dd></div>
          </dl>
          <p className="selection-hint">地图共 {Object.keys(world.agents).length} 个模拟主体 · 点击其他节点可切换</p>
          {onViewAgent ? <button type="button" className="detail-link" onClick={onViewAgent}>查看主体详情 <span>→</span></button> : null}
        </div>
      ) : selectedZone ? (
        <div className="selection-card"><b>{selectedZone.name}</b><p>敏感度 {selectedZone.sensitivity} · 半径 {selectedZone.radius} m</p><p>{world.risk_state.reasons.join('；') || '暂无活跃风险因子'}</p></div>
      ) : <p className="empty-hint">点击地图中的主体或风险区域查看详情</p>}
    </section>
  )
}

