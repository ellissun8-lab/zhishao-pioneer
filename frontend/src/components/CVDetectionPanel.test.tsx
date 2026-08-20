// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { CVDetectionPanel } from './CVDetectionPanel'
import { api } from '../api/client'
import type { Agent, CVSceneResult, CVStatus, CVTrainedResult } from '../types'

vi.mock('../api/client', () => ({
  api: {
    cvDetect: vi.fn(),
    getCVStatus: vi.fn(),
    cvDetectTrained: vi.fn(),
    cvDemoImageUrl: vi.fn((id: string) => `/api/perception/cv/demo-image/${id}`),
  },
}))

const agents: Agent[] = [
  { id: 'agent_A', type: 'Person', synthetic: true, display_name: '模拟人员001', risk_level: 'high', position: { lng: 113.26, lat: 23.12 }, destination: null, behavior_state: 'moving', risk_score: 28.8, active_zone_ids: [], history: [], social_group: 'group_0' },
  { id: 'agent_B', type: 'Person', synthetic: true, display_name: '模拟人员002', risk_level: 'medium', position: { lng: 113.26, lat: 23.12 }, destination: null, behavior_state: 'moving', risk_score: 16, active_zone_ids: [], history: [], social_group: 'group_1' },
  { id: 'agent_C', type: 'Person', synthetic: true, display_name: '模拟人员003', risk_level: 'low', position: { lng: 113.26, lat: 23.12 }, destination: null, behavior_state: 'moving', risk_score: 8, active_zone_ids: [], history: [], social_group: 'group_2' },
]

const sceneResult: CVSceneResult = {
  scene_id: 'scene_high_risk',
  synthetic: true,
  detections: [
    { id: 'det_001', label: 'person', confidence: 0.96, bbox: { x: 0.08, y: 0.28, width: 0.15, height: 0.55 }, subject_id: 'agent_A', synthetic: true },
    { id: 'det_002', label: 'person', confidence: 0.94, bbox: { x: 0.4, y: 0.32, width: 0.15, height: 0.52 }, subject_id: 'agent_B', synthetic: true },
    { id: 'det_003', label: 'person', confidence: 0.92, bbox: { x: 0.7, y: 0.26, width: 0.15, height: 0.56 }, subject_id: 'agent_C', synthetic: true },
    { id: 'det_004', label: 'crowd', confidence: 0.91, bbox: { x: 0.04, y: 0.18, width: 0.86, height: 0.7 }, subject_id: 'agent_A', synthetic: true },
    { id: 'det_005', label: 'risk_object', confidence: 0.89, bbox: { x: 0.58, y: 0.62, width: 0.24, height: 0.18 }, subject_id: 'agent_A', synthetic: true },
  ],
  events: [
    { id: 'e1', type: 'PersonDetected', subject_id: 'agent_A', object_id: null, timestamp: '', confidence: 0.96, source: 'mock_cv', metadata: {} },
    { id: 'e4', type: 'CrowdDetected', subject_id: 'agent_A', object_id: null, timestamp: '', confidence: 0.91, source: 'mock_cv', metadata: {} },
    { id: 'e5', type: 'RiskObjectDetected', subject_id: 'agent_A', object_id: null, timestamp: '', confidence: 0.89, source: 'mock_cv', metadata: {} },
  ],
}

const onComplete = vi.fn<(result: CVSceneResult | CVTrainedResult) => void>()

const cvStatus: CVStatus = {
  provider_preference: 'mock',
  model_available: true,
  model_loaded: true,
  model_path: 'models/cv_detector/best.pt',
  model_version: 'cv_yolo_8.4.123',
  class_names: ['person', 'risk_object', 'vehicle'],
  conf_threshold: 0.25,
  unavailable_reason: null,
  last_inference: null,
}

// Trained CV 真实推理响应（置信度刻意不同于 Mock 预设 96/94/92/89，
// 用于断言 UI 数值完全来自 API 响应而非前端伪造）
const trainedResult: CVTrainedResult = {
  provider: 'real',
  model_invoked: true,
  model_path: 'models/cv_detector/best.pt',
  model_version: 'cv_yolo_8.4.123',
  synthetic_visual_data: true,
  scene_id: 'demo_high_risk',
  conf_threshold: 0.25,
  latency_ms: 42.5,
  detections: [
    { id: 'cv_det_001', label: 'person', confidence: 0.872, bbox: { x: 0.16, y: 0.24, width: 0.13, height: 0.49 }, subject_id: 'agent_A', synthetic: true },
    { id: 'cv_det_002', label: 'person', confidence: 0.791, bbox: { x: 0.45, y: 0.28, width: 0.12, height: 0.46 }, subject_id: 'agent_B', synthetic: true },
    { id: 'cv_det_003', label: 'risk_object', confidence: 0.634, bbox: { x: 0.62, y: 0.66, width: 0.19, height: 0.14 }, subject_id: 'agent_A', synthetic: true },
  ],
  events: [
    { id: 'e1', type: 'PersonDetected', subject_id: 'agent_A', object_id: null, timestamp: '', confidence: 0.872, source: 'real_cv', metadata: {} },
    { id: 'e2', type: 'PersonDetected', subject_id: 'agent_B', object_id: null, timestamp: '', confidence: 0.791, source: 'real_cv', metadata: {} },
    { id: 'e3', type: 'RiskObjectDetected', subject_id: 'agent_A', object_id: null, timestamp: '', confidence: 0.634, source: 'real_cv', metadata: {} },
  ],
  crowd: {
    person_count: 3,
    max_pair_distance: 0.29,
    confidence: 0.791,
    bbox: { x: 0.16, y: 0.24, width: 0.41, height: 0.5 },
    centroid: [0.36, 0.49],
    detection_ids: ['cv_det_001', 'cv_det_002'],
  },
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(api.cvDetect).mockReset()
  vi.mocked(api.cvDetect).mockResolvedValue(sceneResult)
  vi.mocked(api.getCVStatus).mockReset()
  vi.mocked(api.getCVStatus).mockResolvedValue(cvStatus)
  vi.mocked(api.cvDetectTrained).mockReset()
  vi.mocked(api.cvDetectTrained).mockResolvedValue(trainedResult)
  onComplete.mockClear()
})

afterEach(() => {
  act(() => {
    vi.runOnlyPendingTimers()
  })
  vi.useRealTimers()
  cleanup()
})

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

function startDetection() {
  fireEvent.click(screen.getByRole('button', { name: '开始识别' }))
}

function renderPanel(resetVersion = 0) {
  return render(<CVDetectionPanel agents={agents} resetVersion={resetVersion} onComplete={onComplete} />)
}

describe('CVDetectionPanel', () => {
  it('renders the panel, scene buttons and Synthetic Visual Data mark', () => {
    renderPanel()
    expect(screen.getByText('CV 智能感知')).toBeTruthy()
    expect(screen.getByText('Synthetic Visual Data / 模拟视觉数据')).toBeTruthy()
    expect(screen.getByText('CAM-DEMO-01 · 学校周边模拟监控 · 广州演示场景')).toBeTruthy()
    for (const name of ['正常场景', '人员聚集', '疑似风险物品', '综合高风险']) {
      expect(screen.getByRole('button', { name })).toBeTruthy()
    }
    expect(screen.getByText('综合高风险').className).toContain('active')
  })

  it('switches scenes when idle', () => {
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: '人员聚集' }))
    expect(screen.getByText('人员聚集').className).toContain('active')
    expect(screen.getByText('综合高风险').className).not.toContain('active')
  })

  it('runs the detection animation, submits once and shows confidence + Chinese labels', async () => {
    renderPanel()
    startDetection()
    expect(screen.getByText('正在分析画面…')).toBeTruthy()

    await advance(500)
    expect(screen.getByText('扫描画面中…')).toBeTruthy()

    await advance(500)
    expect(screen.getByText('逐个定位检测目标…')).toBeTruthy()
    // 检测框按 bbox 百分比定位
    const box = document.querySelector<HTMLElement>('.cv-box-person')
    expect(box).toBeTruthy()
    // jsdom 会把 8.00% 归一化成 8%，按数值断言 bbox 百分比定位
    expect(parseFloat(box!.style.left)).toBeCloseTo(0.08 * 100, 2)
    expect(parseFloat(box!.style.top)).toBeCloseTo(0.28 * 100, 2)
    expect(parseFloat(box!.style.width)).toBeCloseTo(0.15 * 100, 2)
    expect(box!.style.left.endsWith('%')).toBe(true)

    await advance(500)
    expect(screen.getByText('计算置信度…')).toBeTruthy()
    expect(screen.getByText('96%')).toBeTruthy()

    await advance(500)
    expect(api.cvDetect).toHaveBeenCalledTimes(1)
    expect(api.cvDetect).toHaveBeenCalledWith('scene_high_risk', ['agent_A', 'agent_B', 'agent_C'], expect.any(AbortSignal))
    expect(screen.getByText('识别完成 · 事件已进入 Event Bus')).toBeTruthy()
    expect(screen.getByText('模拟人员001')).toBeTruthy()
    expect(screen.getByText('多人聚集')).toBeTruthy()
    // 场景按钮也叫「疑似风险物品」，这里断言的是检测框标题（不得显示确认刀具/武器）
    expect(document.querySelector('.cv-box-risk_object b')!.textContent).toBe('疑似风险物品')
    expect(screen.getByText('89%')).toBeTruthy()
    expect(screen.getByText('CrowdDetected')).toBeTruthy()
    expect(onComplete).toHaveBeenCalledWith(sceneResult)
  })

  it('does not submit the same detection twice on rapid clicks', async () => {
    renderPanel()
    // 连续快速点击同一个按钮（识别中文案与 disabled 都不能替代防重入守卫）
    const runButton = screen.getByRole('button', { name: '开始识别' })
    fireEvent.click(runButton)
    fireEvent.click(runButton)
    fireEvent.click(runButton)
    await advance(2200)
    expect(api.cvDetect).toHaveBeenCalledTimes(1)
  })

  it('never claims a confirmed weapon, only 疑似风险物品', async () => {
    renderPanel()
    startDetection()
    await advance(2200)
    expect(document.querySelector('.cv-box-risk_object b')!.textContent).toBe('疑似风险物品')
    expect(document.body.textContent).not.toContain('确认刀具')
    expect(document.body.textContent).not.toContain('确认武器')
  })

  it('surfaces API failures without crashing', async () => {
    vi.mocked(api.cvDetect).mockRejectedValue(new Error('API 500'))
    renderPanel()
    startDetection()
    await advance(2200)
    expect(screen.getByText('API 500')).toBeTruthy()
    expect(screen.getByRole('button', { name: '开始识别' })).toBeTruthy()
  })

  it('reset removes all detections and completed result items', async () => {
    const { rerender } = renderPanel()
    startDetection()
    await advance(2200)
    expect(document.querySelectorAll('.cv-box')).toHaveLength(5)
    expect(document.querySelector('.cv-result')).toBeTruthy()

    rerender(<CVDetectionPanel agents={agents} resetVersion={1} onComplete={onComplete} />)

    expect(document.querySelectorAll('.cv-box')).toHaveLength(0)
    expect(document.querySelector('.cv-result')).toBeNull()
  })

  it('reset returns an in-progress detection to idle and clears timers', async () => {
    const { rerender } = renderPanel()
    startDetection()
    await advance(1100)
    expect(screen.getByText('逐个定位检测目标…')).toBeTruthy()

    rerender(<CVDetectionPanel agents={agents} resetVersion={1} onComplete={onComplete} />)
    await advance(1200)

    expect(screen.getByText('待识别 · 模拟画面就绪')).toBeTruthy()
    expect(api.cvDetect).not.toHaveBeenCalled()
  })

  it('ignores a stale detection response that resolves after reset', async () => {
    let resolveRequest!: (value: CVSceneResult) => void
    vi.mocked(api.cvDetect).mockReturnValue(new Promise((resolve) => { resolveRequest = resolve }))
    const { rerender } = renderPanel()
    startDetection()
    await advance(2000)
    expect(api.cvDetect).toHaveBeenCalledTimes(1)

    rerender(<CVDetectionPanel agents={agents} resetVersion={1} onComplete={onComplete} />)
    await act(async () => { resolveRequest(sceneResult) })

    expect(screen.getByText('待识别 · 模拟画面就绪')).toBeTruthy()
    expect(document.querySelectorAll('.cv-box')).toHaveLength(0)
    expect(document.querySelector('.cv-result')).toBeNull()
    expect(onComplete).not.toHaveBeenCalled()
  })
})

describe('CVDetectionPanel · Trained CV mode', () => {
  it('shows the provider selector with Mock CV active by default', () => {
    renderPanel()
    expect(screen.getByTestId('cv-mode-mock').className).toContain('active')
    expect(screen.getByTestId('cv-mode-trained').className).not.toContain('active')
    // mock 模式显示 CSS 合成监控画面，而不是真实 demo 图
    expect(document.querySelector('.cv-trained-image')).toBeNull()
    expect(screen.getByText('CAM-DEMO-01 · 学校周边模拟监控 · 广州演示场景')).toBeTruthy()
  })

  it('switching to Trained CV loads the synthetic demo image and 运行训练模型 button', async () => {
    renderPanel()
    fireEvent.click(screen.getByTestId('cv-mode-trained'))
    expect(screen.getByTestId('cv-mode-trained').className).toContain('active')
    expect(screen.getByTestId('cv-mode-mock').className).not.toContain('active')
    const image = document.querySelector<HTMLImageElement>('.cv-trained-image')
    expect(image).toBeTruthy()
    expect(image!.src).toContain('/api/perception/cv/demo-image/demo_high_risk')
    expect(screen.getByTestId('cv-run-trained')).toBeTruthy()
    expect(screen.getByText('运行训练模型')).toBeTruthy()
    expect(screen.getByText('CAM-DEMO-02 · 独立合成测试图 · 训练模型真实推理')).toBeTruthy()
  })

  it('clicking 运行训练模型 calls /cv/detect-image once and renders real boxes from the response', async () => {
    renderPanel()
    fireEvent.click(screen.getByTestId('cv-mode-trained'))
    fireEvent.click(screen.getByTestId('cv-run-trained'))
    expect(screen.getByText('训练模型推理中（YOLO.predict）…')).toBeTruthy()
    await act(async () => {})

    expect(api.cvDetectTrained).toHaveBeenCalledTimes(1)
    expect(api.cvDetectTrained).toHaveBeenCalledWith('demo_high_risk', ['agent_A', 'agent_B', 'agent_C'], expect.any(AbortSignal))
    expect(onComplete).toHaveBeenCalledTimes(1)
    expect(onComplete).toHaveBeenCalledWith(trainedResult)
    // real 模式绝不调用 mock 端点
    expect(api.cvDetect).not.toHaveBeenCalled()

    const boxes = screen.getAllByTestId('cv-trained-box')
    expect(boxes).toHaveLength(3)
    // bbox 定位与置信度全部来自响应（0.872 -> 87%，0.791 -> 79%，0.634 -> 63%）
    const personBox = boxes[0]
    expect(parseFloat(personBox.style.left)).toBeCloseTo(16, 2)
    expect(parseFloat(personBox.style.width)).toBeCloseTo(13, 2)
    expect(screen.getByText('87%')).toBeTruthy()
    // 第二个 person 79% 与 crowd 聚合置信度（取 person 最小值 0.791）同值，允许重复
    expect(screen.getAllByText('79%').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('63%')).toBeTruthy()
    // 前端禁止伪造：Mock 预设置信度不得出现
    expect(screen.queryByText('96%')).toBeNull()
    expect(screen.queryByText('89%')).toBeNull()
    expect(document.querySelector('.cv-box-risk_object b')!.textContent).toBe('疑似风险物品')
  })

  it('shows REAL MODEL badge with model metadata after real inference', async () => {
    renderPanel()
    fireEvent.click(screen.getByTestId('cv-mode-trained'))
    fireEvent.click(screen.getByTestId('cv-run-trained'))
    await act(async () => {})

    expect(screen.getByTestId('cv-provider-badge').textContent).toBe('REAL MODEL')
    expect(document.body.textContent).toContain('model_invoked: true')
    expect(document.body.textContent).toContain('cv_yolo_8.4.123')
    // crowd 聚合框由感知层规则渲染（非模型输出）
    expect(screen.getByTestId('cv-crowd-agg')).toBeTruthy()
    expect(document.body.textContent).toContain('感知层聚合')
    expect(screen.getAllByText('PersonDetected')).toHaveLength(2)
    expect(screen.getByText('RiskObjectDetected')).toBeTruthy()
  })

  it('shows MOCK FALLBACK badge (never Trained CV) when the model is unavailable', async () => {
    vi.mocked(api.cvDetectTrained).mockResolvedValue({
      ...trainedResult,
      provider: 'mock_fallback',
      model_invoked: false,
      model_version: null,
      latency_ms: undefined,
      conf_threshold: undefined,
      fallback_reason: 'model file missing',
      crowd: null,
      detections: trainedResult.detections.slice(0, 1),
      events: trainedResult.events.slice(0, 1),
    })
    renderPanel()
    fireEvent.click(screen.getByTestId('cv-mode-trained'))
    fireEvent.click(screen.getByTestId('cv-run-trained'))
    await act(async () => {})

    expect(screen.getByTestId('cv-provider-badge').textContent).toBe('MOCK FALLBACK')
    expect(document.body.textContent).toContain('model_invoked: false')
    expect(document.body.textContent).toContain('model file missing')
    expect(document.body.textContent).not.toContain('REAL MODEL')
    expect(screen.queryByTestId('cv-crowd-agg')).toBeNull()
  })

  it('confidences come from the API response, not preset values (confidence source)', async () => {
    vi.mocked(api.cvDetectTrained).mockResolvedValue({
      ...trainedResult,
      detections: [
        { id: 'cv_det_001', label: 'person', confidence: 0.4213, bbox: { x: 0.2, y: 0.2, width: 0.1, height: 0.4 }, subject_id: 'agent_A', synthetic: true },
      ],
      events: [],
      crowd: null,
    })
    renderPanel()
    fireEvent.click(screen.getByTestId('cv-mode-trained'))
    fireEvent.click(screen.getByTestId('cv-run-trained'))
    await act(async () => {})

    expect(screen.getByText('42%')).toBeTruthy()
    expect(screen.queryByText('87%')).toBeNull()
  })

  it('surfaces trained inference API failures without crashing', async () => {
    vi.mocked(api.cvDetectTrained).mockRejectedValue(new Error('API 503'))
    renderPanel()
    fireEvent.click(screen.getByTestId('cv-mode-trained'))
    fireEvent.click(screen.getByTestId('cv-run-trained'))
    await act(async () => {})

    expect(screen.getByText('API 503')).toBeTruthy()
    expect(screen.getByTestId('cv-run-trained')).toBeTruthy()
    expect(screen.queryByTestId('cv-provider-badge')).toBeNull()
    expect(onComplete).not.toHaveBeenCalled()
  })
})
