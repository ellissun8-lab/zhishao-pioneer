import type { SimulationResult, Strategy } from '../types'

const strategyMeta: Record<Strategy, { label: string; icon: string; description: string }> = {
  none: { label: '不干预', icon: '○', description: '保持当前状态' },
  warn: { label: '发送预警', icon: '◈', description: '远程提示离开' },
  guide_leave: { label: '引导离开', icon: '↗', description: '主动疏导人群' },
  intervene: { label: '现场处置', icon: '◆', description: '终止高风险事件' },
}

type Props = {
  results: SimulationResult[]
  selected: Strategy
  busy: boolean
  onRun: (strategy: Strategy) => void
  onCompare: () => void
}

export function SimulationPanel({ results, selected, busy, onRun, onCompare }: Props) {
  const resultByStrategy = new Map(results.map((result) => [result.strategy, result]))
  return (
    <section className="panel simulation-panel">
      <div className="panel-heading"><span>What-if 推演</span><em>10 MIN</em></div>
      <div className="strategy-grid">
        {(Object.keys(strategyMeta) as Strategy[]).map((strategy) => {
          const meta = strategyMeta[strategy]
          const result = resultByStrategy.get(strategy)
          return (
            <button key={strategy} type="button" className={selected === strategy ? 'selected' : ''} onClick={() => onRun(strategy)} disabled={busy}>
              <i>{meta.icon}</i><span><b>{meta.label}</b><small>{meta.description}</small></span>
              {result ? <strong>{result.after.risk.toFixed(0)}</strong> : <em>运行</em>}
            </button>
          )
        })}
      </div>
      <button type="button" className="compare-button" onClick={onCompare} disabled={busy}>{busy ? '正在推演…' : '比较全部策略'}</button>
      {results.length ? (
        <div className="comparison-bars">
          {results.map((result) => (
            <div key={result.strategy}>
              <span>{strategyMeta[result.strategy].label}</span>
              <i><b style={{ width: `${result.after.risk}%` }} /></i>
              <strong>{result.after.risk.toFixed(0)}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  )
}

