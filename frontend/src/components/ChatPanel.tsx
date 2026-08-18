import { FormEvent, useState } from 'react'
import type { ChatMessage } from '../types'

type Props = { messages: ChatMessage[]; busy: boolean; onSend: (message: string) => void }

const suggestions = ['为什么风险升高？', '为什么学校区域现在是红色？', '未来10分钟会怎样？', '如果现在发送预警，会发生什么？']

export function ChatPanel({ messages, busy, onSend }: Props) {
  const [input, setInput] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    const message = input.trim()
    if (!message || busy) return
    onSend(message)
    setInput('')
  }
  return (
    <section className="panel chat-panel">
      <div className="panel-heading"><span>推演 Agent</span><em><i className="online-dot" /> 工具在线</em></div>
      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="agent-intro"><div>哨</div><p>我只基于 World State 和模拟工具解释风险，不会凭空生成结论。</p></div>
        ) : messages.map((message, index) => <div key={`${message.role}-${index}`} className={`message ${message.role}`}>{message.content}</div>)}
      </div>
      <div className="suggestions">{suggestions.map((text) => <button type="button" key={text} onClick={() => onSend(text)} disabled={busy}>{text}</button>)}</div>
      <form onSubmit={submit}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="询问当前风险或干预效果…" aria-label="向推演 Agent 提问" />
        <button type="submit" disabled={busy || !input.trim()} aria-label="发送问题">↑</button>
      </form>
    </section>
  )
}

