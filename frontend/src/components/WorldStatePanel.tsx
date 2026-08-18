import type { Agent, WorldState, Zone } from '../types'

type Props = { world: WorldState; selectedAgent: Agent | null; selectedZone: Zone | null }

export function WorldStatePanel({ world, selectedAgent, selectedZone }: Props) {
  const moving = Object.values(world.agents).filter((agent) => agent.behavior_state !== 'idle').length
  return (
    <section className="panel world-panel">
      <div className="panel-heading"><span>World State</span><em>{new Date(world.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}</em></div>
      <div className="metric-row">
        <div><strong>{Object.keys(world.agents).length}</strong><span>模拟主体</span></div>
        <div><strong>{moving}</strong><span>活跃状态</span></div>
        <div><strong>{world.active_events.length}</strong><span>事件总数</span></div>
      </div>
      {selectedAgent ? (
        <div className="selection-card">
          <div><span className={`agent-pulse ${selectedAgent.risk_level}`} /><b>{selectedAgent.id}</b><small>SYNTHETIC</small></div>
          <dl>
            <div><dt>风险等级</dt><dd>{selectedAgent.risk_level}</dd></div>
            <div><dt>行为状态</dt><dd>{selectedAgent.behavior_state}</dd></div>
            <div><dt>社会组</dt><dd>{selectedAgent.social_group}</dd></div>
            <div><dt>位置</dt><dd>{selectedAgent.position.lng.toFixed(4)}, {selectedAgent.position.lat.toFixed(4)}</dd></div>
          </dl>
        </div>
      ) : selectedZone ? (
        <div className="selection-card"><b>{selectedZone.name}</b><p>敏感度 {selectedZone.sensitivity} · 半径 {selectedZone.radius} m</p><p>{world.risk_state.reasons.join('；') || '暂无活跃风险因子'}</p></div>
      ) : <p className="empty-hint">点击地图中的 Agent 或风险区域查看详情</p>}
    </section>
  )
}

