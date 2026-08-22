// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { CVDetectionPanel } from './CVDetectionPanel'
import { api } from '../api/client'
import type { Agent, CVSceneResult } from '../types'

vi.mock('../api/client', () => ({
  api: { cvDetect: vi.fn() },
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

const onComplete = vi.fn<(result: CVSceneResult) => void>()

beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(api.cvDetect).mockReset()
  vi.mocked(api.cvDetect).mockResolvedValue(sceneResult)
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
  it('renders the panel, scene buttons and Chinese visual data mark', () => {
    renderPanel()
    expect(screen.getByText('视觉感知')).toBeTruthy()
    expect(screen.getByText('模拟视觉数据')).toBeTruthy()
    expect(screen.getByText('监控点 01 · 学校周边模拟监控 · 广州演示场景')).toBeTruthy()
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
    expect(screen.getByText('识别完成 · 事件已进入事件流')).toBeTruthy()
    expect(screen.getByText('模拟人员001')).toBeTruthy()
    expect(screen.getByText('多人聚集')).toBeTruthy()
    // 场景按钮也叫「疑似风险物品」，这里断言的是检测框标题（不得显示确认刀具/武器）
    expect(document.querySelector('.cv-box-risk_object b')!.textContent).toBe('疑似风险物品')
    expect(screen.getByText('89%')).toBeTruthy()
    expect(screen.getByText('感知人流聚集')).toBeTruthy()
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
