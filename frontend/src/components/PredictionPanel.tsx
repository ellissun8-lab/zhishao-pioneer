import { useState } from 'react'
import { api } from '../api/client'
import type { Prediction } from '../types'

const HORIZONS = [5, 10, 30] as const

const trendLabel: Record<string, string> = { up: '↑ 上升', down: '↓ 回落', stable: '→ 稳定' }

export function PredictionPanel({ currentRisk }: { currentRisk: number }) {
  const [predictions, setPredictions] = useState<Record<number, Prediction>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(horizon: number) {
    try {
      const prediction = await api.predict(horizon)
      setPredictions((current) => ({ ...current, [horizon]: prediction }))
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '预测失败')
    }
  }

  async function runAll() {
    setBusy(true)
    try {
      await Promise.all(HORIZONS.map((horizon) => run(horizon)))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel prediction-panel">
      <div className="panel-heading"><span>未来推演</span><em>WORLD BEHAVIOR MODEL</em></div>
      <div className="prediction-grid">
        {HORIZONS.map((horizon) => {
          const prediction = predictions[horizon]
          return (
            <button key={horizon} type="button" onClick={() => void run(horizon)} disabled={busy}>
              <b>+{horizon} min</b>
              {prediction ? (
                <>
                  <strong className={prediction.risk_score > currentRisk ? 'worse' : prediction.risk_score < currentRisk ? 'better' : ''}>
                    {prediction.risk_score.toFixed(0)}
                  </strong>
                  <small>{trendLabel[prediction.risk_trend] ?? prediction.risk_trend}</small>
                  <small>聚集 {Math.round(prediction.gather_probability * 100)}% · 入区 {Math.round(prediction.zone_entry_probability * 100)}%</small>
                </>
              ) : (
                <em>运行预测</em>
              )}
            </button>
          )
        })}
      </div>
      <div className="prediction-footer">
        <button type="button" className="compare-button" onClick={() => void runAll()} disabled={busy}>
          {busy ? '推演中…' : `预测 5 / 10 / 30 分钟（当前 ${currentRisk.toFixed(0)}）`}
        </button>
        {error ? <p className="prediction-error">{error}</p> : null}
        {predictions[10]?.model ? <p className="prediction-model">模型：{predictions[10].model} · Synthetic Data</p> : null}
      </div>
    </section>
  )
}
