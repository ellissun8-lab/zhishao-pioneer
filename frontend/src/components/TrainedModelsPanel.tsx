import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { MLRecommend, MLStatus } from '../types'

function formatCount(value: number): string {
  return value.toLocaleString('zh-Hans-CN')
}

export function TrainedModelsPanel() {
  const [status, setStatus] = useState<MLStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recommend, setRecommend] = useState<MLRecommend | null>(null)
  const [busy, setBusy] = useState(false)

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.getMLStatus())
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '模型状态不可用')
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

  async function requestRecommendation() {
    setBusy(true)
    try {
      setRecommend(await api.getMLRecommend())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '模型推荐失败')
    } finally {
      setBusy(false)
    }
  }

  const modelsReady = Boolean(status?.risk_available && status?.policy_available)

  return (
    <section className="panel ml-panel">
      <div className="panel-heading"><span>训练模型</span><em>SYNTHETIC ML</em></div>
      {error ? <p className="ml-error">{error}</p> : null}
      {status ? (
        <div className="ml-body">
          <div className="ml-stat">
            <span>训练数据</span>
            <strong>{formatCount(status.episodes)} <small>SYNTHETIC EPISODES</small></strong>
            <em>{formatCount(status.train_rows)} / {formatCount(status.validation_rows)} / {formatCount(status.test_rows)} TRAIN · VAL · TEST</em>
          </div>
          <div className="ml-badges">
            <div className={status.risk_available ? 'ml-badge loaded' : 'ml-badge'}>
              <i>RISK FORECAST</i>
              <b>{status.risk_available ? '已加载' : '未加载'}</b>
            </div>
            <div className={status.policy_available ? 'ml-badge loaded' : 'ml-badge'}>
              <i>POLICY MODEL</i>
              <b>{status.policy_available ? '已加载' : '未加载'}</b>
            </div>
          </div>
          <div className="ml-metrics">
            <div>
              <span>TEST MAE · 10MIN</span>
              <strong>{status.test_risk_mae_10m === null ? '—' : status.test_risk_mae_10m.toFixed(2)}</strong>
            </div>
            <div>
              <span>POLICY MACRO-F1</span>
              <strong>{status.test_policy_macro_f1 === null ? '—' : status.test_policy_macro_f1.toFixed(4)}</strong>
            </div>
          </div>
          {modelsReady ? (
            <p className="ml-note">指标读取自 models/metrics.json · {status.model_version} · 100% Synthetic Training</p>
          ) : (
            <p className="ml-note fallback">{status.fallback_note ?? 'ML model unavailable, using transparent rule-based fallback.'}</p>
          )}
          <button type="button" className="compare-button" onClick={() => void requestRecommendation()} disabled={busy}>
            {busy ? '正在推荐…' : '模型推荐 + What-if 验证'}
          </button>
          {recommend ? (
            <div className="ml-recommend">
              <div className="ml-recommend-head">
                <span>推荐策略：<b>{recommend.recommendation.strategy}</b></span>
                {recommend.recommendation.confidence !== null ? <span>置信度 {(recommend.recommendation.confidence * 100).toFixed(1)}%</span> : null}
              </div>
              <div className="comparison-bars">
                {recommend.simulation.map((item) => (
                  <div key={item.strategy}>
                    <span>{item.strategy}</span>
                    <i><b style={{ width: `${item.after_risk}%` }} /></i>
                    <strong>{item.after_risk.toFixed(0)}</strong>
                  </div>
                ))}
              </div>
              <p className="ml-explanation">{recommend.explanation}</p>
            </div>
          ) : null}
        </div>
      ) : !error ? <p className="ml-error">正在读取 models/metrics.json…</p> : null}
    </section>
  )
}
