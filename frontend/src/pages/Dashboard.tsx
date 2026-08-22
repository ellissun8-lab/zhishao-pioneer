import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { AgentDetailDrawer, AgentTraceDrawer, EventDetailDrawer, SimulationDetailDrawer } from '../components/DetailDrawer'
import { AgentsPage, EventsPage, LabPage, OverviewPage } from '../components/WorkspacePages'
import { useWorld } from '../stores/useWorld'
import { eventTypeLabel } from '../labels'
import type { Agent, ChatMessage, CVSceneResult, CVTrainedResult, SimulationResult, Strategy, WorldEvent, Zone } from '../types'

const AUTO_TICK_INTERVAL_MS = 1500

type DetailState =
  | { type: 'agent'; agent: Agent }
  | { type: 'event'; event: WorldEvent }
  | { type: 'simulation'; result: SimulationResult }
  | { type: 'trace'; message: ChatMessage }
  | null

type WorkspaceView = 'overview' | 'events' | 'agents' | 'lab'

const viewLabels: Record<WorkspaceView, { label: string; hint: string }> = {
  overview: { label: '态势总览', hint: '实时' },
  events: { label: '事件中心', hint: '事件流' },
  agents: { label: '主体目录', hint: '模拟主体' },
  lab: { label: '推演实验室', hint: '策略分析' },
}

function getInitialView(): WorkspaceView {
  const value = window.location.hash.slice(1) as WorkspaceView
  return value in viewLabels ? value : 'overview'
}

export default function Dashboard() {
  const { world, setWorld, loading, error, refresh } = useWorld()
  const [selectedAgentId, setSelectedAgentId] = useState('agent_A')
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null)
  const [trackMode, setTrackMode] = useState<'history' | 'prediction'>('history')
  const [results, setResults] = useState<SimulationResult[]>([])
  const [activeSimulation, setActiveSimulation] = useState<SimulationResult | null>(null)
  const [strategy, setStrategy] = useState<Strategy>('warn')
  const [busy, setBusy] = useState(false)
  const [autoRun, setAutoRun] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [notice, setNotice] = useState('系统就绪 · 等待事件输入')
  const [resetVersion, setResetVersion] = useState(0)
  const [detail, setDetail] = useState<DetailState>(null)
  const [view, setView] = useState<WorkspaceView>(getInitialView)

  const agents = useMemo(() => world ? Object.values(world.agents) : [], [world])
  const selectedAgent = world?.agents[selectedAgentId] ?? null

  useEffect(() => {
    const syncView = () => setView(getInitialView())
    window.addEventListener('popstate', syncView)
    window.addEventListener('hashchange', syncView)
    return () => {
      window.removeEventListener('popstate', syncView)
      window.removeEventListener('hashchange', syncView)
    }
  }, [])

  function navigate(nextView: WorkspaceView) {
    setView(nextView)
    window.history.pushState(null, '', `#${nextView}`)
  }

  useEffect(() => {
    if (!autoRun) return
    let cancelled = false
    const timer = setInterval(() => {
      void (async () => {
        try {
          const response = await api.tick()
          if (!cancelled) setWorld(response.state)
        } catch {
          if (!cancelled) {
            setAutoRun(false)
            setNotice('自动推演已停止：无法连接仿真引擎')
          }
        }
      })()
    }, AUTO_TICK_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [autoRun, setWorld])

  async function execute(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  function selectAgent(agent: Agent) {
    setSelectedAgentId(agent.id)
    setSelectedZone(null)
  }

  function advanceDemo() {
    void execute(async () => {
      const response = await api.advance()
      setWorld(response.state)
      setActiveSimulation(null)
      const event = response.state.active_events.at(-1)
      setNotice(`已接收事件：${event ? eventTypeLabel(event.type) : '演示世界已重置'}`)
    })
  }

  function resetDemo() {
    void execute(async () => {
      // 先使正在进行的 CV 请求失效，再重置后端，避免迟到响应污染重置后的演示状态。
      setResetVersion((version) => version + 1)
      setWorld(await api.reset())
      setResults([])
      setActiveSimulation(null)
      setMessages([])
      setDetail(null)
      setAutoRun(false)
      setNotice('演示世界已重置')
    })
  }

  function runMockCV(detection: string) {
    void execute(async () => {
      await api.mockDetection(detection)
      await refresh()
      setActiveSimulation(null)
      const detectionLabel: Record<string, string> = { person: '人员', vehicle: '车辆', crowd: '聚集', risk_object: '风险物品' }
      setNotice(`模拟感知已生成${detectionLabel[detection] ?? detection}事件`)
    })
  }

  function handleCVDetection(result: CVSceneResult | CVTrainedResult) {
    void (async () => {
      await refresh()
      setNotice(`视觉识别完成：${result.events.length} 个感知事件已进入事件流`)
    })()
  }

  function runStrategy(nextStrategy: Strategy) {
    setStrategy(nextStrategy)
    void execute(async () => {
      const result = await api.simulate(nextStrategy)
      setResults((current) => [...current.filter((item) => item.strategy !== nextStrategy), result])
      setActiveSimulation(result)
      setNotice(`策略推演完成：风险 ${result.before.risk} → ${result.after.risk}`)
    })
  }

  function compareAll() {
    void execute(async () => {
      const comparisons = await api.compare()
      setResults(comparisons)
      setActiveSimulation(comparisons.find((item) => item.strategy === strategy) ?? comparisons[0] ?? null)
      setNotice('四种策略已在独立世界状态副本上完成比较')
    })
  }

  function sendMessage(message: string) {
    setMessages((current) => [...current, { role: 'user', content: message }])
    void execute(async () => {
      const response = await api.chat(message)
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: response.answer,
          trace: {
            provider: response.provider ?? 'deterministic_fallback',
            model: response.model ?? null,
            tools_used: response.tools_used ?? [],
            tool_rounds: response.tool_rounds ?? 0,
            request_id: response.request_id ?? null,
            latency_ms: response.latency_ms ?? null,
            fallback: response.fallback ?? false,
            fallback_reason: response.fallback_reason ?? null,
          },
        },
      ])
    })
  }

  function openSelectedAgent() {
    if (selectedAgent) setDetail({ type: 'agent', agent: selectedAgent })
  }

  if (loading) return <main className="loading-screen"><div className="brand-mark"><img src="/logo-cityos.png" alt="智哨先锋标志" /></div><p>正在初始化城市世界状态…</p></main>
  if (!world || error) return <main className="loading-screen error"><div>!</div><p>{error || '世界状态不可用'}</p><button type="button" onClick={() => void refresh()}>重新连接</button></main>

  return (
    <main className={`dashboard ${view === 'overview' ? 'is-overview' : ''}`}>
      <header className="app-header">
        <div className="brand"><div className="brand-mark"><img src="/logo-cityos.png" alt="智哨先锋标志" /></div><div><h1>智哨先锋</h1><span>城市行为智能推演系统</span></div></div>
        <div className="system-status"><span><i /> 世界模型在线</span><time>{new Date(world.timestamp).toLocaleString('zh-CN', { hour12: false })}</time></div>
      </header>

      <nav className="workspace-nav" aria-label="工作区导航">
        {(Object.keys(viewLabels) as WorkspaceView[]).map((item, index) => <button type="button" key={item} className={view === item ? 'active' : ''} data-step={index + 1} onClick={() => navigate(item)}><span className="step-node" aria-hidden="true">{index + 1}</span><span className="step-label">{viewLabels[item].label}</span><small>{viewLabels[item].hint}</small></button>)}
      </nav>

      {view === 'overview' ? <OverviewPage agents={agents} world={world} selectedAgent={selectedAgent} selectedZone={selectedZone} trackMode={trackMode} activeSimulation={activeSimulation} busy={busy} autoRun={autoRun} notice={notice} onMockCV={runMockCV} onToggleAutoRun={() => setAutoRun((value) => !value)} onAdvance={advanceDemo} onReset={resetDemo} onSelectAgent={selectAgent} onSelectZone={(zone) => { setSelectedZone(zone); setSelectedAgentId('') }} onCloseSimulation={() => setActiveSimulation(null)} onTrackMode={setTrackMode} onViewAgent={openSelectedAgent} onSelectEvent={(event) => setDetail({ type: 'event', event })} onNavigate={(next) => navigate(next)} /> : null}
      {view === 'events' ? <EventsPage world={world} agents={agents} resetVersion={resetVersion} onComplete={handleCVDetection} onSelectEvent={(event) => setDetail({ type: 'event', event })} /> : null}
      {view === 'agents' ? <AgentsPage world={world} agents={agents} selectedAgent={selectedAgent} onSelectAgent={selectAgent} onViewAgent={openSelectedAgent} /> : null}
      {view === 'lab' ? <LabPage resetVersion={resetVersion} results={results} strategy={strategy} busy={busy} onRun={runStrategy} onCompare={compareAll} onViewResult={(result) => setDetail({ type: 'simulation', result })} currentRisk={world.risk_state.overall_score} riskHistory={world.risk_state.history} messages={messages} onSend={sendMessage} onViewTrace={(message) => setDetail({ type: 'trace', message })} /> : null}

      <footer><span>模型：透明规则 + 状态机 + 概率模型 v1</span><span>所有人员、关系、轨迹和风险均为模拟数据，不代表真实公安预测。</span></footer>
      {detail?.type === 'agent' ? <AgentDetailDrawer agent={world.agents[detail.agent.id] ?? detail.agent} world={world} onClose={() => setDetail(null)} /> : null}
      {detail?.type === 'event' ? <EventDetailDrawer event={detail.event} world={world} onClose={() => setDetail(null)} /> : null}
      {detail?.type === 'simulation' ? <SimulationDetailDrawer result={detail.result} onClose={() => setDetail(null)} /> : null}
      {detail?.type === 'trace' ? <AgentTraceDrawer message={detail.message} onClose={() => setDetail(null)} /> : null}
    </main>
  )
}
