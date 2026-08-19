import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { ChatPanel } from '../components/ChatPanel'
import { CityMap } from '../components/CityMap'
import { CVDetectionPanel } from '../components/CVDetectionPanel'
import { EventTimeline } from '../components/EventTimeline'
import { PredictionPanel } from '../components/PredictionPanel'
import { RiskChart } from '../components/RiskChart'
import { RiskPanel } from '../components/RiskPanel'
import { SimulationPanel } from '../components/SimulationPanel'
import { TrainedModelsPanel } from '../components/TrainedModelsPanel'
import { WorldStatePanel } from '../components/WorldStatePanel'
import { useWorld } from '../stores/useWorld'
import type { Agent, ChatMessage, CVSceneResult, SimulationResult, Strategy, Zone } from '../types'

const AUTO_TICK_INTERVAL_MS = 1500

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

  const agents = useMemo(() => world ? Object.values(world.agents) : [], [world])
  const selectedAgent = world?.agents[selectedAgentId] ?? null

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
      setNotice(`已接收事件：${response.state.active_events.at(-1)?.type ?? 'Demo 已重置'}`)
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
      setAutoRun(false)
      setNotice('演示世界已重置')
    })
  }

  function runMockCV(detection: string) {
    void execute(async () => {
      await api.mockDetection(detection)
      await refresh()
      setActiveSimulation(null)
      setNotice(`Mock CV 已生成 ${detection} 事件`)
    })
  }

  function handleCVDetection(result: CVSceneResult) {
    void (async () => {
      await refresh()
      setNotice(`CV 识别完成：${result.events.length} 个感知事件已进入 Event Bus`)
    })()
  }

  function runStrategy(nextStrategy: Strategy) {
    setStrategy(nextStrategy)
    void execute(async () => {
      const result = await api.simulate(nextStrategy)
      setResults((current) => [...current.filter((item) => item.strategy !== nextStrategy), result])
      setActiveSimulation(result)
      setNotice(`${nextStrategy} 推演完成：风险 ${result.before.risk} -> ${result.after.risk}`)
    })
  }

  function compareAll() {
    void execute(async () => {
      const comparisons = await api.compare()
      setResults(comparisons)
      setActiveSimulation(comparisons.find((item) => item.strategy === strategy) ?? comparisons[0] ?? null)
      setNotice('四种策略已在独立 World State 副本上完成比较')
    })
  }

  function sendMessage(message: string) {
    setMessages((current) => [...current, { role: 'user', content: message }])
    void execute(async () => {
      const response = await api.chat(message)
      setMessages((current) => [...current, { role: 'assistant', content: response.answer }])
    })
  }

  if (loading) return <main className="loading-screen"><div className="brand-mark">哨</div><p>正在初始化城市世界状态…</p></main>
  if (!world || error) return <main className="loading-screen error"><div>!</div><p>{error || '世界状态不可用'}</p><button type="button" onClick={() => void refresh()}>重新连接</button></main>

  return (
    <main className="dashboard">
      <header className="app-header">
        <div className="brand"><div className="brand-mark">哨</div><div><h1>智哨先锋</h1><span>城市行为智能推演 AGENT</span></div></div>
        <div className="synthetic-banner"><i /> 广州演示场景 / SYNTHETIC DATA <span>模拟数据 · 仅用于模型验证</span></div>
        <div className="system-status"><span><i /> WORLD MODEL ONLINE</span><time>{new Date(world.timestamp).toLocaleString('zh-CN', { hour12: false })}</time></div>
      </header>

      <div className="command-bar">
        <div><span className="command-kicker">DEMO CONTROL</span><b>{notice}</b></div>
        <div className="command-actions">
          <button type="button" onClick={() => runMockCV('person')} disabled={busy}>模拟人员</button>
          <button type="button" onClick={() => runMockCV('vehicle')} disabled={busy}>模拟车辆</button>
          <button type="button" onClick={() => runMockCV('crowd')} disabled={busy} title="Mock CV 感知层：CrowdDetected">聚集感知</button>
          <button type="button" className="danger" onClick={() => runMockCV('risk_object')} disabled={busy}>模拟危险物品</button>
          <button type="button" className={autoRun ? 'primary' : 'auto-run'} onClick={() => setAutoRun((value) => !value)} disabled={busy}>
            {autoRun ? '⏸ 暂停推演' : '▶ 自动推演'}
          </button>
          <button type="button" className="primary" onClick={advanceDemo} disabled={busy}>推进下一事件 <span>-&gt;</span></button>
          <button type="button" className="icon-button" onClick={resetDemo} disabled={busy} title="重置演示">↻</button>
        </div>
      </div>

      <div className="workspace-grid">
        <div className="map-column">
          <CityMap
            agents={agents}
            places={Object.values(world.places)}
            zones={Object.values(world.zones)}
            events={world.active_events}
            selectedAgent={selectedAgent}
            trackMode={trackMode}
            simulationResult={activeSimulation}
            onSelectAgent={selectAgent}
            onSelectZone={(zone) => { setSelectedZone(zone); setSelectedAgentId('') }}
            onCloseSimulation={() => setActiveSimulation(null)}
          />
          <div className="track-switch"><button type="button" className={trackMode === 'history' ? 'active' : ''} onClick={() => setTrackMode('history')}>历史轨迹</button><button type="button" className={trackMode === 'prediction' ? 'active' : ''} onClick={() => setTrackMode('prediction')}>预测轨迹</button></div>
        </div>
        <div className="center-column">
          <RiskPanel risk={world.risk_state} />
          <WorldStatePanel world={world} selectedAgent={selectedAgent} selectedZone={selectedZone} />
          <section className="panel chart-panel"><div className="panel-heading"><span>风险演化</span><em>RULE ENGINE</em></div><RiskChart values={world.risk_state.history} /></section>
          <PredictionPanel currentRisk={world.risk_state.overall_score} />
        </div>
        <div className="right-column">
          <TrainedModelsPanel />
          <CVDetectionPanel agents={agents} resetVersion={resetVersion} onComplete={handleCVDetection} />
          <SimulationPanel results={results} selected={strategy} busy={busy} onRun={runStrategy} onCompare={compareAll} />
          <ChatPanel messages={messages} busy={busy} onSend={sendMessage} />
        </div>
        <EventTimeline events={world.active_events} />
      </div>

      <footer><span>模型：Transparent Rule + State Machine + Probability v1</span><span>所有人员、关系、轨迹和风险均为模拟数据，不代表真实公安预测。</span></footer>
    </main>
  )
}
