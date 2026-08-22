import { useEffect } from 'react'
import { agentDisplayName, behaviorStateLabel, eventTypeLabel, riskLevelLabel, sourceLabel } from '../labels'
import type { Agent, ChatMessage, SimulationResult, WorldEvent, WorldState, Zone } from '../types'

const strategyNames: Record<string, string> = {
  none: '不干预',
  warn: '发送预警',
  guide_leave: '引导离开',
  intervene: '现场处置',
}

type DrawerProps = { title: string; eyebrow: string; onClose: () => void; children: React.ReactNode }

function Drawer({ title, eyebrow, onClose, children }: DrawerProps) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div className="drawer-layer" role="presentation">
      <button type="button" className="drawer-backdrop" aria-label="关闭详情" onClick={onClose} />
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-label={title}>
        <header className="drawer-header">
          <div><span>{eyebrow}</span><h2>{title}</h2></div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="关闭详情" title="关闭详情">×</button>
        </header>
        <div className="drawer-content">{children}</div>
      </aside>
    </div>
  )
}

function DataRow({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="detail-row"><span>{label}</span><b>{value}</b></div>
}

export function AgentDetailDrawer({ agent, world, onClose }: { agent: Agent; world: WorldState; onClose: () => void }) {
  const events = world.active_events.filter((event) => event.subject_id === agent.id).slice(-5).reverse()
  return (
    <Drawer title={agentDisplayName(agent)} eyebrow="主体详情 · 模拟数据" onClose={onClose}>
      <div className="drawer-status-row"><span className={`status-chip ${agent.risk_level}`}>{riskLevelLabel(agent.risk_level)}</span><span className="drawer-muted">{agent.id}</span></div>
      <section className="drawer-section drawer-highlight">
        <p className="drawer-label">当前行为</p>
        <strong>{behaviorStateLabel(agent.behavior_state)}</strong>
        <p>该主体的身份、轨迹、关系和风险等级均为模拟数据，仅用于模型验证。</p>
      </section>
      <section className="drawer-section">
        <h3>世界状态</h3>
        <DataRow label="社会组" value={agent.social_group} />
        <DataRow label="主体风险" value={`${agent.risk_score.toFixed(1)} / 100`} />
        <DataRow label="当前位置" value={`${agent.position.lng.toFixed(5)}, ${agent.position.lat.toFixed(5)}`} />
        <DataRow label="目的地" value={agent.destination ? `${agent.destination.lng.toFixed(5)}, ${agent.destination.lat.toFixed(5)}` : '无'} />
        <DataRow label="敏感区域" value={agent.active_zone_ids.length ? agent.active_zone_ids.join('、') : '未进入'} />
      </section>
      <section className="drawer-section">
        <div className="drawer-section-heading"><h3>关联事件</h3><span>{events.length} 条</span></div>
        {events.length ? <div className="drawer-event-list">{events.map((event) => <div key={event.id}><b>{eventTypeLabel(event.type)}</b><span>{sourceLabel(event.source)} · {(event.confidence * 100).toFixed(0)}%</span></div>)}</div> : <p className="drawer-empty">暂无关联事件</p>}
      </section>
      <section className="drawer-section">
        <div className="drawer-section-heading"><h3>轨迹记录</h3><span>{agent.history.length} 个点</span></div>
        <p className="drawer-muted">历史轨迹可在地图左上角切换查看。当前选中主体会保持高亮。</p>
      </section>
    </Drawer>
  )
}

export function EventDetailDrawer({ event, world, onClose }: { event: WorldEvent; world: WorldState; onClose: () => void }) {
  const subject = event.subject_id ? world.agents[event.subject_id] : null
  const objectName = event.object_id ? world.zones[event.object_id]?.name ?? event.object_id : '无'
  const contribution = world.risk_state.rule_contributions[event.type]
  return (
    <Drawer title={eventTypeLabel(event.type)} eyebrow="事件流 · 审计记录" onClose={onClose}>
      <div className="drawer-status-row"><span className={`status-chip ${event.type === 'RiskObjectDetected' || event.type === 'AlertTriggered' ? 'critical' : 'info'}`}>{eventTypeLabel(event.type)}</span><span className="drawer-muted">#{event.id.slice(-6)}</span></div>
      <section className="drawer-section drawer-highlight">
        <p className="drawer-label">事件结论</p>
        <strong>{subject ? agentDisplayName(subject) : '系统事件'}</strong>
        <p>{sourceLabel(event.source)} 写入事件流，置信度 {(event.confidence * 100).toFixed(0)}%。</p>
      </section>
      <section className="drawer-section">
        <h3>事件字段</h3>
        <DataRow label="发生时间" value={new Date(event.timestamp).toLocaleString('zh-CN', { hour12: false })} />
        <DataRow label="事件来源" value={sourceLabel(event.source)} />
        <DataRow label="关联主体" value={subject ? `${agentDisplayName(subject)} · ${event.subject_id}` : '无'} />
        <DataRow label="关联区域" value={objectName} />
        <DataRow label="风险贡献" value={contribution === undefined ? '由当前规则状态共同计算' : `+${contribution}`} />
      </section>
      <section className="drawer-section">
        <h3>原始元数据</h3>
        <pre className="metadata-block">{JSON.stringify(event.metadata, null, 2)}</pre>
      </section>
    </Drawer>
  )
}

export function SimulationDetailDrawer({ result, onClose }: { result: SimulationResult; onClose: () => void }) {
  return (
    <Drawer title={strategyNames[result.strategy] ?? result.strategy} eyebrow="策略推演 · 世界状态副本" onClose={onClose}>
      <div className="drawer-status-row"><span className="status-chip simulation">模拟副本</span><span className="drawer-muted">{result.horizon_minutes} 分钟</span></div>
      <section className="drawer-section drawer-highlight simulation-highlight">
        <p className="drawer-label">风险变化</p>
        <strong>{result.before.risk.toFixed(1)} <i>→</i> {result.after.risk.toFixed(1)}</strong>
        <p>该策略在独立世界状态副本上执行，不会修改实时世界状态。</p>
      </section>
      <section className="drawer-section">
        <h3>结果指标</h3>
        <DataRow label="聚集规模" value={`${result.before.crowd_size} → ${result.after.crowd_size}`} />
        <DataRow label="离开概率" value={`${Math.round(result.leave_probability * 100)}%`} />
        <DataRow label="行动成本" value={result.action_cost} />
        <DataRow label="预测趋势" value={result.prediction.risk_trend} />
        <DataRow label="预测活跃主体" value={result.prediction.predicted_agents} />
      </section>
      <section className="drawer-section">
        <h3>模型变化</h3>
        <ul className="change-list">{result.changes.map((change) => <li key={change}>{change}</li>)}</ul>
      </section>
    </Drawer>
  )
}

export function AgentTraceDrawer({ message, onClose }: { message: ChatMessage; onClose: () => void }) {
  const tools = message.trace?.tools_used ?? []
  return (
    <Drawer title="千问调用链" eyebrow="智能研判 · 证据链" onClose={onClose}>
      <div className="drawer-status-row"><span className="status-chip info">{message.trace && !message.trace.fallback ? '千问模型' : '本地规则解释'}</span><span className="drawer-muted">可追溯回答</span></div>
      <section className="drawer-section drawer-highlight">
        <p className="drawer-label">执行路径</p>
        <strong>问题 → 工具 → 世界状态 → 回答</strong>
        <p>模型只负责选择工具和组织表达，风险计算仍由本地透明规则引擎完成。</p>
      </section>
      <section className="drawer-section">
        <div className="drawer-section-heading"><h3>已调用工具</h3><span>{tools.length} 个</span></div>
        {tools.length ? <div className="tool-list">{tools.map((tool, index) => <div key={tool}><i>{String(index + 1).padStart(2, '0')}</i><span>{tool}</span><b>已完成</b></div>)}</div> : <p className="drawer-empty">本次回答未返回工具调用记录</p>}
      </section>
      <section className="drawer-section">
        <h3>回答摘要</h3>
        <p className="trace-answer">{message.content}</p>
      </section>
    </Drawer>
  )
}
