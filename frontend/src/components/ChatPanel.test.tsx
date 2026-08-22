// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ChatPanel } from './ChatPanel'
import { api } from '../api/client'
import type { ChatMessage, LLMStatus } from '../types'

vi.mock('../api/client', () => ({
  api: {
    getLLMStatus: vi.fn(),
  },
}))

const connectedStatus: LLMStatus = {
  provider: 'Alibaba Cloud Model Studio',
  model: 'qwen3.8-max',
  configured: true,
  connected: true,
  function_calling: true,
  multimodal: true,
  fallback: false,
  fallback_reason: null,
  components: {
    cv_detector: { name: 'YOLO26n', status: 'TRAINED', model_version: 'cv_yolo_8.4.123', model_path: 'models/cv_detector/best.pt', available: true },
    risk_forecast: { name: 'HistGradientBoostingRegressor', status: 'LOADED', model_version: 'risk_hgb_v1' },
    policy_model: { name: 'HistGradientBoostingClassifier', status: 'LOADED', model_version: 'policy_hgb_v1' },
  },
}

const fallbackStatus: LLMStatus = {
  ...connectedStatus,
  configured: false,
  connected: false,
  fallback: true,
  fallback_reason: 'DASHSCOPE_API_KEY 未配置',
}

beforeEach(() => {
  vi.mocked(api.getLLMStatus).mockReset()
  cleanup()
})

describe('ChatPanel Qwen 状态区', () => {
  it('connected 时渲染 CONNECTED 徽标与三个模型组件（全部来自 API，不得前端硬编码）', async () => {
    vi.mocked(api.getLLMStatus).mockResolvedValue(connectedStatus)
    render(<ChatPanel messages={[]} busy={false} onSend={vi.fn()} />)

    await waitFor(() => expect(screen.getByTestId('llm-status-badge').textContent ?? '').toContain('CONNECTED'))
    expect(screen.getByText('Qwen3.8-Max · Alibaba Cloud Model Studio')).toBeTruthy()
    expect(screen.getByTestId('llm-component-cv').textContent ?? '').toContain('TRAINED')
    expect(screen.getByTestId('llm-component-risk').textContent ?? '').toContain('LOADED')
    expect(screen.getByTestId('llm-component-policy').textContent ?? '').toContain('LOADED')
  })

  it('未配置 Key 时渲染 FALLBACK 徽标（绝不显示 Connected）', async () => {
    vi.mocked(api.getLLMStatus).mockResolvedValue(fallbackStatus)
    render(<ChatPanel messages={[]} busy={false} onSend={vi.fn()} />)

    await waitFor(() => expect(screen.getByTestId('llm-status-badge').textContent ?? '').toContain('FALLBACK'))
    expect(screen.queryByText('CONNECTED')).toBeNull()
  })

  it('状态接口失败时显示离线状态而不是崩溃', async () => {
    vi.mocked(api.getLLMStatus).mockRejectedValue(new Error('network down'))
    render(<ChatPanel messages={[]} busy={false} onSend={vi.fn()} />)

    await waitFor(() => expect(screen.getByTestId('llm-status-badge').textContent ?? '').toContain('FALLBACK'))
  })

  it('支持手动刷新陈旧状态：Offline 恢复 Online 后更新 CONNECTED', async () => {
    vi.mocked(api.getLLMStatus)
      .mockResolvedValueOnce(fallbackStatus)
      .mockResolvedValueOnce(connectedStatus)
    render(<ChatPanel messages={[]} busy={false} onSend={vi.fn()} />)

    await waitFor(() => expect(screen.getByTestId('llm-status-badge').textContent ?? '').toContain('FALLBACK'))
    fireEvent.click(screen.getByRole('button', { name: '刷新 Qwen 状态' }))
    await waitFor(() => expect(screen.getByTestId('llm-status-badge').textContent ?? '').toContain('CONNECTED'))
    expect(api.getLLMStatus).toHaveBeenCalledTimes(2)
  })
})

describe('ChatPanel 工具 trace 渲染', () => {
  it('Qwen 回答渲染 provider/轮次/延迟与工具 chips', () => {
    vi.mocked(api.getLLMStatus).mockResolvedValue(connectedStatus)
    const messages: ChatMessage[] = [
      { role: 'user', content: '训练模型认为未来10分钟风险多少？' },
      {
        role: 'assistant',
        content: '训练模型预测未来10分钟风险为 26.6。',
        trace: {
          provider: 'Alibaba Cloud Model Studio',
          model: 'qwen3.8-max',
          tools_used: ['ml_predict_risk'],
          tool_rounds: 1,
          request_id: 'req-abc',
          latency_ms: 812.4,
          fallback: false,
        },
      },
    ]
    render(<ChatPanel messages={messages} busy={false} onSend={vi.fn()} />)

    expect(screen.getByTestId('chat-trace-provider').textContent ?? '').toContain('qwen3.8-max')
    expect(screen.getByTestId('chat-trace-provider').textContent ?? '').toContain('1 轮工具')
    expect(screen.getByTestId('chat-trace-tools').textContent ?? '').toContain('ml_predict_risk')
  })

  it('多工具 trace 渲染全部工具名（policy 多工具链）', () => {
    vi.mocked(api.getLLMStatus).mockResolvedValue(connectedStatus)
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        content: '模型推荐发送预警。',
        trace: {
          provider: 'Alibaba Cloud Model Studio',
          model: 'qwen3.8-max',
          tools_used: ['ml_recommend_strategy', 'compare_strategies'],
          tool_rounds: 2,
          request_id: 'req-2',
          latency_ms: 1204.0,
          fallback: false,
        },
      },
    ]
    render(<ChatPanel messages={messages} busy={false} onSend={vi.fn()} />)

    const tools = screen.getByTestId('chat-trace-tools')
    expect(tools.textContent ?? '').toContain('ml_recommend_strategy')
    expect(tools.textContent ?? '').toContain('compare_strategies')
  })

  it('fallback 消息渲染 Qwen3.8-Max Offline · Fallback Explanation', () => {
    vi.mocked(api.getLLMStatus).mockResolvedValue(fallbackStatus)
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        content: 'ML Prediction：训练模型预测未来 10 分钟风险为 26.6。',
        trace: {
          provider: 'deterministic_fallback',
          model: null,
          tools_used: ['ml_predict_risk'],
          tool_rounds: 0,
          request_id: null,
          latency_ms: null,
          fallback: true,
          fallback_reason: 'Qwen3.8-Max Offline：DASHSCOPE_API_KEY 未配置',
        },
      },
    ]
    render(<ChatPanel messages={messages} busy={false} onSend={vi.fn()} />)

    expect(screen.getByTestId('chat-trace-fallback').textContent ?? '').toContain('Qwen3.8-Max Offline · Fallback Explanation')
    expect(screen.queryByText('Qwen Connected')).toBeNull()
  })

  it('无 trace 的旧消息不渲染 trace 区域', () => {
    vi.mocked(api.getLLMStatus).mockResolvedValue(connectedStatus)
    render(<ChatPanel messages={[{ role: 'assistant', content: '历史回答' }]} busy={false} onSend={vi.fn()} />)
    expect(screen.queryByTestId('chat-trace')).toBeNull()
  })
})
