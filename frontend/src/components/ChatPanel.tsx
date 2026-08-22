import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessage, LLMStatus } from '../types'
import { api } from '../api/client'

type Props = {
  messages: ChatMessage[]
  busy: boolean
  onSend: (message: string) => void
  onViewTrace?: (message: ChatMessage) => void
}

const suggestions = ['为什么风险升高？', '训练模型认为未来10分钟风险多少？', '视觉模型检测到了什么？', '现在模型建议采取什么措施？']

function statusLabel(status: LLMStatus | null, failed: boolean): { text: string; className: string } {
  if (status) return status.connected
    ? { text: 'CONNECTED', className: 'llm-badge online' }
    : { text: 'FALLBACK', className: 'llm-badge offline' }
  return failed
    ? { text: 'FALLBACK', className: 'llm-badge offline' }
    : { text: '状态加载中…', className: 'llm-badge offline' }
}

export function ChatPanel({ messages, busy, onSend, onViewTrace }: Props) {
  const [input, setInput] = useState('')
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null)
  const [statusFailed, setStatusFailed] = useState(false)
  const [statusRefreshing, setStatusRefreshing] = useState(false)
  const statusRequestRef = useRef(0)

  const refreshStatus = useCallback(async () => {
    const requestId = ++statusRequestRef.current
    setStatusRefreshing(true)
    try {
      const status = await api.getLLMStatus()
      if (requestId !== statusRequestRef.current) return
      setLlmStatus(status)
      setStatusFailed(false)
    } catch {
      if (requestId !== statusRequestRef.current) return
      setLlmStatus(null)
      setStatusFailed(true)
    } finally {
      if (requestId === statusRequestRef.current) setStatusRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
    return () => { statusRequestRef.current += 1 }
  }, [refreshStatus])

  function submit(event: FormEvent) {
    event.preventDefault()
    const message = input.trim()
    if (!message || busy) return
    onSend(message)
    setInput('')
  }

  const badge = statusLabel(llmStatus, statusFailed)

  return (
    <section className="panel chat-panel">
      <div className="panel-heading">
        <span>智能研判</span>
        <em><i className="online-dot" /> 工具在线</em>
      </div>
      <div className="llm-status" data-testid="llm-status">
        <div className="llm-status-row">
          <span className="llm-status-name">LLM Agent</span>
          <span className="llm-status-meta">Qwen3.8-Max · Alibaba Cloud Model Studio</span>
          <span className={badge.className} data-testid="llm-status-badge">{badge.text}</span>
          <button
            type="button"
            className="llm-status-refresh"
            aria-label="刷新 Qwen 状态"
            onClick={() => void refreshStatus()}
            disabled={statusRefreshing}
          >
            {statusRefreshing ? '刷新中…' : '刷新'}
          </button>
        </div>
        {llmStatus && (
          <div className="llm-status-grid">
            <div className="llm-status-item" data-testid="llm-component-cv">
              <span className="llm-status-name">CV Detector</span>
              <span className="llm-status-meta">{llmStatus.components.cv_detector.name}</span>
              <span className={`llm-badge ${llmStatus.components.cv_detector.status === 'TRAINED' ? 'online' : 'offline'}`}>{llmStatus.components.cv_detector.status}</span>
            </div>
            <div className="llm-status-item" data-testid="llm-component-risk">
              <span className="llm-status-name">Risk Forecast</span>
              <span className="llm-status-meta">{llmStatus.components.risk_forecast.name}</span>
              <span className={`llm-badge ${llmStatus.components.risk_forecast.status === 'LOADED' ? 'online' : 'offline'}`}>{llmStatus.components.risk_forecast.status}</span>
            </div>
            <div className="llm-status-item" data-testid="llm-component-policy">
              <span className="llm-status-name">Policy Model</span>
              <span className="llm-status-meta">{llmStatus.components.policy_model.name}</span>
              <span className={`llm-badge ${llmStatus.components.policy_model.status === 'LOADED' ? 'online' : 'offline'}`}>{llmStatus.components.policy_model.status}</span>
            </div>
          </div>
        )}
      </div>
      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="agent-intro"><div className="agent-intro-logo"><img src="/logo-cityos.png" alt="智哨先锋标志" /></div><p>我只基于世界状态和模拟工具解释风险，不会凭空生成结论。</p></div>
        ) : messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
            <div>{message.content}</div>
            {message.role === 'assistant' && message.trace && (
              <div className="chat-trace" data-testid="chat-trace">
                {message.trace.fallback ? (
                  <span className="trace-fallback" data-testid="chat-trace-fallback">Qwen3.8-Max Offline · Fallback Explanation</span>
                ) : (
                  <span className="trace-provider" data-testid="chat-trace-provider">{message.trace.model} · {message.trace.tool_rounds} 轮工具 · {message.trace.latency_ms ?? '—'}ms</span>
                )}
                {message.trace.tools_used.length > 0 && (
                  <span className="trace-tools" data-testid="chat-trace-tools">
                    {message.trace.tools_used.map((tool, toolIndex) => (
                      <code key={`${tool}-${toolIndex}`}>{tool}</code>
                    ))}
                  </span>
                )}
                {onViewTrace ? <button type="button" onClick={() => onViewTrace(message)}>查看调用链</button> : null}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="suggestions">{suggestions.map((text) => <button type="button" key={text} onClick={() => onSend(text)} disabled={busy}>{text}</button>)}</div>
      <form onSubmit={submit}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="询问当前风险或干预效果…" aria-label="向推演 Agent 提问" />
        <button type="submit" disabled={busy || !input.trim()} aria-label="发送问题">↑</button>
      </form>
    </section>
  )
}
