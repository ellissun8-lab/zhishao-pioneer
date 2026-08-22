import type { RiskState } from '../types'
import { ruleLabel } from '../labels'

export function RiskPanel({ risk }: { risk: RiskState }) {
  const circumference = 289
  const dashOffset = circumference * (1 - risk.overall_score / 100)
  return (
    <section className="panel risk-panel">
      <div className="panel-heading"><span>综合风险</span><em>实时</em></div>
      <div className="risk-gauge">
        <svg viewBox="0 0 110 110" aria-label={`当前风险 ${risk.overall_score}`}>
          <circle cx="55" cy="55" r="46" className="gauge-bg" />
          <circle cx="55" cy="55" r="46" className={`gauge-value ${risk.level}`} style={{ strokeDashoffset: dashOffset }} />
        </svg>
        <div><strong>{risk.overall_score.toFixed(0)}</strong><span>/ 100</span></div>
      </div>
      <div className={`risk-label ${risk.level}`}>{risk.level === 'critical' ? '极高风险' : risk.level === 'high' ? '高风险' : risk.level === 'medium' ? '中风险' : '低风险'}</div>
      <div className="rule-list">
        {Object.entries(risk.rule_contributions).map(([rule, value]) => (
          <div key={rule}><span>{ruleLabel(rule)}</span><b>{rule.includes('multiplier') ? `×${value}` : `+${value}`}</b></div>
        ))}
      </div>
    </section>
  )
}

