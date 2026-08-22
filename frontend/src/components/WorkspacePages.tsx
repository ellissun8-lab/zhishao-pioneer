import { useMemo, useState } from 'react'
import type { Agent, ChatMessage, CVSceneResult, SimulationResult, Strategy, WorldEvent, WorldState, Zone } from '../types'
import { agentDisplayName, behaviorStateLabel, eventTypeLabel, riskLevelLabel, sourceLabel } from '../labels'
import { ChatPanel } from './ChatPanel'
import { CityMap } from './CityMap'
import { CVDetectionPanel } from './CVDetectionPanel'
import { EventTimeline } from './EventTimeline'
import { PredictionPanel } from './PredictionPanel'
import { RiskChart } from './RiskChart'
import { RiskPanel } from './RiskPanel'
import { SimulationPanel } from './SimulationPanel'
import { WorldStatePanel } from './WorldStatePanel'

type MapProps = {
  agents: Agent[]
  world: WorldState
  selectedAgent: Agent | null
  selectedZone: Zone | null
  trackMode: 'history' | 'prediction'
  activeSimulation: SimulationResult | null
  onSelectAgent: (agent: Agent) => void
  onSelectZone: (zone: Zone) => void
  onCloseSimulation: () => void
  onTrackMode: (mode: 'history' | 'prediction') => void
}

type ControlProps = {
  busy: boolean
  autoRun: boolean
  notice: string
  onMockCV: (detection: string) => void
  onToggleAutoRun: () => void
  onAdvance: () => void
  onReset: () => void
}

export function OverviewPage({
  agents, world, selectedAgent, selectedZone, trackMode, activeSimulation, onSelectAgent, onSelectZone, onCloseSimulation, onTrackMode,
  onViewAgent, onSelectEvent, onNavigate, busy, autoRun, notice, onMockCV, onToggleAutoRun, onAdvance, onReset,
}: MapProps & ControlProps & { onViewAgent: () => void; onSelectEvent: (event: WorldEvent) => void; onNavigate: (view: 'events' | 'agents' | 'lab') => void }) {
  const recentEvents = world.active_events.slice(-4).reverse()
  return (
    <div className="overview-page">
      <DemoControlPanel busy={busy} autoRun={autoRun} notice={notice} onMockCV={onMockCV} onToggleAutoRun={onToggleAutoRun} onAdvance={onAdvance} onReset={onReset} />
      <div className="overview-grid">
        <div className="map-column">
          <CityMap agents={agents} places={Object.values(world.places)} zones={Object.values(world.zones)} events={world.active_events} selectedAgent={selectedAgent} trackMode={trackMode} simulationResult={activeSimulation} onSelectAgent={onSelectAgent} onSelectZone={onSelectZone} onCloseSimulation={onCloseSimulation} />
          <div className="track-switch"><button type="button" className={trackMode === 'history' ? 'active' : ''} onClick={() => onTrackMode('history')}>历史轨迹</button><button type="button" className={trackMode === 'prediction' ? 'active' : ''} onClick={() => onTrackMode('prediction')}>预测轨迹</button></div>
        </div>
        <aside className="overview-rail">
          <RiskPanel risk={world.risk_state} />
          <WorldStatePanel world={world} selectedAgent={selectedAgent} selectedZone={selectedZone} onViewAgent={onViewAgent} />
        </aside>
      </div>
      <div className="overview-insights">
        <section className="panel overview-events">
          <div className="panel-heading"><span>实时事件摘要</span><button type="button" onClick={() => onNavigate('events')}>进入事件中心 →</button></div>
          {recentEvents.length ? <div className="overview-event-list">{recentEvents.map((event) => <button type="button" key={event.id} onClick={() => onSelectEvent(event)}><i className={event.type === 'RiskObjectDetected' ? 'critical' : ''} /><span><b>{eventTypeLabel(event.type)}</b><small>{event.subject_id || '系统'} · {sourceLabel(event.source)}</small></span><time>{new Date(event.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}</time></button>)}</div> : <div className="overview-empty"><strong>事件流待命</strong><span>使用顶部模拟控制生成一条感知事件，事件详情会在这里出现。</span></div>}
        </section>
        <section className="panel overview-status">
          <div className="panel-heading"><div className="overview-status-title"><span>运行概览</span><span className="overview-online"><i className="online-dot" /> 世界模型在线</span></div><em>系统运行</em></div>
          <div className="overview-metrics"><div><strong>{Object.keys(world.zones).length}</strong><span>敏感区域</span></div><div><strong>{Object.values(world.places).length}</strong><span>城市设施</span></div><div><strong>{world.active_events.length ? '活跃' : '待命'}</strong><span>事件引擎</span></div></div>
        </section>
      </div>
    </div>
  )
}

function DemoControlPanel({ busy, autoRun, notice, onMockCV, onToggleAutoRun, onAdvance, onReset }: ControlProps) {
  const [sensorMenuOpen, setSensorMenuOpen] = useState(false)

  function triggerDetection(detection: string) {
    setSensorMenuOpen(false)
    onMockCV(detection)
  }

  return (
    <section className={`panel control-module command-bar ${busy ? 'is-busy' : ''}`} aria-label="运行控制">
      <div><span className="command-kicker">运行控制</span><b>{notice}</b></div>
      <div className="command-actions">
        <div className="command-group command-group-sensors" aria-label="感知注入">
          <button
            type="button"
            className={`sensor-fab ${sensorMenuOpen ? 'is-open' : ''}`}
            onClick={() => setSensorMenuOpen((value) => !value)}
            disabled={busy}
            aria-expanded={sensorMenuOpen}
            aria-controls="sensor-menu"
            title="选择模拟感知"
          >
            <span className="sensor-fab-icon" aria-hidden="true">+</span>
            <span>感知</span>
          </button>
          {sensorMenuOpen ? (
            <div id="sensor-menu" className="sensor-menu" role="menu" aria-label="选择模拟感知">
              <span className="sensor-menu-title">选择模拟感知</span>
              <button type="button" role="menuitem" onClick={() => triggerDetection('person')} disabled={busy}>模拟人员</button>
              <button type="button" role="menuitem" onClick={() => triggerDetection('vehicle')} disabled={busy}>模拟车辆</button>
              <button type="button" role="menuitem" onClick={() => triggerDetection('crowd')} disabled={busy} title="Mock CV 感知层：CrowdDetected">聚集感知</button>
              <button type="button" role="menuitem" className="danger" onClick={() => triggerDetection('risk_object')} disabled={busy}>模拟危险物品</button>
              <button type="button" role="menuitem" className="sensor-reset" onClick={() => { setSensorMenuOpen(false); onReset() }} disabled={busy}>重置演示</button>
            </div>
          ) : null}
        </div>
        <div className="command-group command-group-run" aria-label="演示推进">
          <button type="button" className={autoRun ? 'primary' : 'auto-run'} onClick={onToggleAutoRun} disabled={busy}>{autoRun ? '⏸ 暂停推演' : '▶ 自动推演'}</button>
          <button type="button" className="primary" onClick={onAdvance} disabled={busy}>推进下一事件 <span>-&gt;</span></button>
        </div>
      </div>
    </section>
  )
}

export function EventsPage({ world, agents, resetVersion, onComplete, onSelectEvent }: { world: WorldState; agents: Agent[]; resetVersion: number; onComplete: (result: CVSceneResult) => void; onSelectEvent: (event: WorldEvent) => void }) {
  return (
    <div className="secondary-page">
      <PageHeading kicker="事件流 / 实时监控" title="事件中心" description="集中查看感知事件、来源置信度与实时处理结果。" stats={[['事件总数', String(world.active_events.length)], ['高风险事件', String(world.active_events.filter((event) => event.type === 'RiskObjectDetected').length)], ['数据来源', '模拟数据']]} />
      <div className="events-layout"><EventTimeline events={world.active_events} onSelect={onSelectEvent} /><CVDetectionPanel agents={agents} resetVersion={resetVersion} onComplete={onComplete} /></div>
    </div>
  )
}

export function AgentsPage({ world, agents, selectedAgent, onSelectAgent, onViewAgent }: { world: WorldState; agents: Agent[]; selectedAgent: Agent | null; onSelectAgent: (agent: Agent) => void; onViewAgent: () => void }) {
  const [riskFilter, setRiskFilter] = useState<'all' | Agent['risk_level']>('all')
  const sortedAgents = [...agents].sort((a, b) => b.risk_score - a.risk_score)
  const visibleAgents = useMemo(() => riskFilter === 'all' ? sortedAgents : sortedAgents.filter((agent) => agent.risk_level === riskFilter), [riskFilter, sortedAgents])
  return (
    <div className="secondary-page">
      <PageHeading kicker="世界状态 / 模拟主体" title="主体目录" description="按风险等级查看模拟主体，选择主体后可继续查看轨迹与关联事件。" stats={[['主体总数', String(agents.length)], ['高风险', String(agents.filter((agent) => agent.risk_level === 'high').length)], ['活跃中', String(agents.filter((agent) => agent.behavior_state !== 'idle').length)]]} />
      <div className="agents-layout">
        <section className="panel agent-directory"><div className="panel-heading"><span>模拟主体列表</span><div className="agent-filters">{(['all', 'high', 'medium', 'low'] as const).map((item) => <button type="button" key={item} className={riskFilter === item ? 'active' : ''} aria-pressed={riskFilter === item} onClick={() => setRiskFilter(item)}>{item === 'all' ? '全部' : riskLevelLabel(item)}</button>)}</div><em>按风险排序</em></div><div className="agent-grid">{visibleAgents.length ? visibleAgents.map((agent) => <button type="button" key={agent.id} className={`agent-row ${selectedAgent?.id === agent.id ? 'selected' : ''}`} onClick={() => onSelectAgent(agent)}><i className={`agent-pulse ${agent.risk_level}`} /><span><b>{agentDisplayName(agent)}</b><small>{agent.id} · {behaviorStateLabel(agent.behavior_state)} · {agent.social_group}</small></span><strong className={agent.risk_level}>{agent.risk_score.toFixed(0)}</strong><em>{riskLevelLabel(agent.risk_level)}</em></button>) : <p className="empty-hint">没有符合筛选条件的主体</p>}</div></section>
        <aside className="agent-side"><WorldStatePanel world={world} selectedAgent={selectedAgent} selectedZone={null} onViewAgent={onViewAgent} /><RiskPanel risk={world.risk_state} /></aside>
      </div>
    </div>
  )
}

export function LabPage({ results, strategy, busy, onRun, onCompare, onViewResult, currentRisk, riskHistory, messages, onSend, onViewTrace }: { results: SimulationResult[]; strategy: Strategy; busy: boolean; onRun: (strategy: Strategy) => void; onCompare: () => void; onViewResult: (result: SimulationResult) => void; currentRisk: number; riskHistory: number[]; messages: ChatMessage[]; onSend: (message: string) => void; onViewTrace: (message: ChatMessage) => void }) {
  return (
    <div className="secondary-page">
      <PageHeading kicker="策略推演 / 智能研判" title="推演实验室" description="在独立世界状态副本中比较干预策略，并让智能研判解释风险变化。" stats={[['当前风险', currentRisk.toFixed(0)], ['已完成策略', String(results.length)], ['模型状态', '工具在线']]} />
      <div className="lab-layout"><div className="lab-primary"><SimulationPanel results={results} selected={strategy} busy={busy} onRun={onRun} onCompare={onCompare} onViewResult={onViewResult} /><PredictionPanel currentRisk={currentRisk} /><section className="panel chart-panel"><div className="panel-heading"><span>风险演化</span><em>风险规则</em></div><RiskChart values={riskHistory} /></section></div><ChatPanel messages={messages} busy={busy} onSend={onSend} onViewTrace={onViewTrace} /></div>
    </div>
  )
}

function PageHeading({ kicker, title, description, stats }: { kicker: string; title: string; description: string; stats: Array<[string, string]> }) {
  return <div className="page-heading"><div><span>{kicker}</span><h2>{title}</h2><p>{description}</p></div><div className="page-stats">{stats.map(([label, value]) => <div key={label}><strong>{value}</strong><small>{label}</small></div>)}</div></div>
}
