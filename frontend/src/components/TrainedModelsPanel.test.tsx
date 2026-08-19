// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TrainedModelsPanel } from './TrainedModelsPanel'
import { api } from '../api/client'
import type { MLRecommend, MLRiskPrediction, MLStatus } from '../types'

vi.mock('../api/client', () => ({
  api: { getMLStatus: vi.fn(), getMLRecommend: vi.fn(), predictMLRisk: vi.fn() },
}))

const loadedStatus: MLStatus = {
  risk_available: true,
  policy_available: true,
  fallback_note: null,
  model_version: 'risk_hgb_v1 + policy_hgb_v1',
  episodes: 120000,
  train_rows: 84000,
  validation_rows: 18000,
  test_rows: 18000,
  test_risk_mae_10m: 1.23,
  test_policy_macro_f1: 0.9876,
  synthetic_training: true,
}

const fallbackStatus: MLStatus = {
  ...loadedStatus,
  risk_available: false,
  policy_available: false,
  fallback_note: 'ML model unavailable, using transparent rule-based fallback.',
  episodes: 0,
  train_rows: 0,
  validation_rows: 0,
  test_rows: 0,
  test_risk_mae_10m: null,
  test_policy_macro_f1: null,
}

const recommend: MLRecommend = {
  recommendation: {
    model: 'intervention_policy',
    model_version: 'policy_hgb_v1',
    strategy: 'guide_leave',
    probabilities: { none: 0.02, warn: 0.08, guide_leave: 0.8, intervene: 0.1 },
    confidence: 0.8,
    synthetic_training: true,
  },
  fallback: false,
  simulation: [
    { strategy: 'none', before_risk: 48, after_risk: 49.9, action_cost: 0, utility: -1.9 },
    { strategy: 'warn', before_risk: 48, after_risk: 32.6, action_cost: 1, utility: 12.9 },
    { strategy: 'guide_leave', before_risk: 48, after_risk: 19.7, action_cost: 3, utility: 20.8 },
    { strategy: 'intervene', before_risk: 48, after_risk: 7.7, action_cost: 8, utility: 12.3 },
  ],
  best_by_simulation: 'guide_leave',
  explanation: '模型推荐 guide_leave（置信度 80.0%），What-if 仿真验证 utility 最大，两者一致。Synthetic Data 声明：以上基于 100% 合成数据训练。',
  synthetic: true,
}

const mlPrediction: MLRiskPrediction = {
  model: 'risk_forecast',
  model_type: 'HistGradientBoostingRegressor',
  model_version: 'risk_hgb_v1',
  horizon_minutes: 10,
  prediction: 79.4,
  test_mae: 0.0912,
  input_features: { current_risk: 62 },
  synthetic_training: true,
  fallback: false,
}

const fallbackPrediction: MLRiskPrediction = {
  model: 'transparent_rule_probability_v1',
  model_type: 'TransparentRuleWorldBehaviorModel',
  model_version: null,
  horizon_minutes: 10,
  prediction: 82,
  test_mae: null,
  input_features: { current_risk: 62 },
  synthetic_training: false,
  fallback: true,
  fallback_source: 'rule_world_behavior_model',
  note: 'ML model unavailable, using transparent rule-based fallback.',
}

beforeEach(() => {
  vi.mocked(api.getMLStatus).mockReset()
  vi.mocked(api.getMLRecommend).mockReset()
  vi.mocked(api.predictMLRisk).mockReset()
})

afterEach(() => cleanup())

describe('TrainedModelsPanel', () => {
  it('renders dataset and metric values from the ML status API', async () => {
    vi.mocked(api.getMLStatus).mockResolvedValue(loadedStatus)
    render(<TrainedModelsPanel />)
    expect(await screen.findByText(/120,000/)).toBeTruthy()
    expect(screen.getByText(/84,000/)).toBeTruthy()
    expect(screen.getByText(/18,000/)).toBeTruthy()
    expect(screen.getByText('1.23')).toBeTruthy()
    expect(screen.getByText('0.9876')).toBeTruthy()
    expect(screen.getAllByText('已加载')).toHaveLength(2)
    expect(screen.getByText(/models\/metrics\.json/)).toBeTruthy()
  })

  it('shows the transparent rule-based fallback note when models are unavailable', async () => {
    vi.mocked(api.getMLStatus).mockResolvedValue(fallbackStatus)
    render(<TrainedModelsPanel />)
    expect(await screen.findByText(/transparent rule-based fallback/)).toBeTruthy()
    expect(screen.queryByText('已加载')).toBeNull()
  })

  it('requests a recommendation and renders simulation verification plus explanation', async () => {
    vi.mocked(api.getMLStatus).mockResolvedValue(loadedStatus)
    vi.mocked(api.getMLRecommend).mockResolvedValue(recommend)
    render(<TrainedModelsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: '模型推荐 + What-if 验证' }))
    expect(await screen.findByText(/推荐策略/)).toBeTruthy()
    expect(screen.getAllByText('guide_leave')).toHaveLength(2)
    expect(screen.getAllByText(/置信度 80\.0%/)).toHaveLength(2)
    expect(screen.getByText(/What-if 仿真验证/)).toBeTruthy()
    await waitFor(() => expect(api.getMLRecommend).toHaveBeenCalledTimes(1))
  })

  it('runs a real ML prediction path and renders model metadata from the API', async () => {
    vi.mocked(api.getMLStatus).mockResolvedValue(loadedStatus)
    vi.mocked(api.predictMLRisk).mockResolvedValue(mlPrediction)
    render(<TrainedModelsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: 'ML预测未来10分钟' }))
    expect(await screen.findByText('未来10分钟：79.4')).toBeTruthy()
    expect(screen.getByText('HistGradientBoostingRegressor')).toBeTruthy()
    expect(screen.getByText('risk_hgb_v1')).toBeTruthy()
    expect(screen.getByText(/ML Model · Test MAE 0\.0912/)).toBeTruthy()
    await waitFor(() => expect(api.predictMLRisk).toHaveBeenCalledWith(10))
  })

  it('labels rule fallback explicitly when the trained model is unavailable', async () => {
    vi.mocked(api.getMLStatus).mockResolvedValue(fallbackStatus)
    vi.mocked(api.predictMLRisk).mockResolvedValue(fallbackPrediction)
    render(<TrainedModelsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: 'ML预测未来10分钟' }))
    expect(await screen.findByText('未来10分钟：82.0')).toBeTruthy()
    expect(screen.getByText('规则模型回退')).toBeTruthy()
    expect(screen.queryByText('ML 风险预测')).toBeNull()
    expect(screen.getByText('TransparentRuleWorldBehaviorModel')).toBeTruthy()
    expect(screen.getByText('rule fallback')).toBeTruthy()
    expect(screen.getByText('Rule Fallback')).toBeTruthy()
    expect(screen.getAllByText(/transparent rule-based fallback/).length).toBeGreaterThan(0)
  })

  it('surfaces status loading errors without crashing', async () => {
    vi.mocked(api.getMLStatus).mockRejectedValue(new Error('backend offline'))
    render(<TrainedModelsPanel />)
    expect(await screen.findByText('backend offline')).toBeTruthy()
    expect(screen.queryByText(/120,000/)).toBeNull()
  })
})
