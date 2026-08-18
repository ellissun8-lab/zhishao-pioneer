import type { Agent } from '../types'
import { projectToPercent } from '../map/coordinates'

type Props = { agent: Agent; onSelect: (agent: Agent) => void }

export function AgentMarker({ agent, onSelect }: Props) {
  const position = projectToPercent(agent.position)
  return (
    <button
      type="button"
      className={`fallback-agent risk-${agent.risk_level}`}
      style={position}
      onClick={() => onSelect(agent)}
      aria-label={`查看 ${agent.id} 模拟主体`}
      title={`${agent.id} · Synthetic Data`}
    >
      <span />
    </button>
  )
}

