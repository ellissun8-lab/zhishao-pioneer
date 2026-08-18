import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { agentDisplayName } from '../labels'
import type { Agent, CVBBox, CVDetection, CVLabel, CVSceneResult } from '../types'

type Phase = 'idle' | 'analyzing' | 'scanning' | 'detecting' | 'confidence' | 'submitting' | 'done'

type SceneConfig = { id: string; name: string; hint: string }

type PreviewDetection = { id: string; label: CVLabel; confidence: number; bbox: CVBBox }

// 与后端 backend/app/perception/mock_cv.py 的 SCENE_LAYOUT / SCENE_CONFIDENCE 保持一致的展示预览；
// 权威 Detection 仍以后端 /api/perception/mock-cv/detect 返回为准
const SCENES: SceneConfig[] = [
  { id: 'scene_normal', name: '正常场景', hint: '仅人员经过' },
  { id: 'scene_crowd', name: '人员聚集', hint: '3 人 + 聚集' },
  { id: 'scene_risk_object', name: '疑似风险物品', hint: '人员 + 物品' },
  { id: 'scene_high_risk', name: '综合高风险', hint: '3 人 + 聚集 + 物品' },
]

const SCENE_PREVIEW: Record<string, PreviewDetection[]> = {
  scene_normal: [
    { id: 'det_001', label: 'person', confidence: 0.96, bbox: { x: 0.12, y: 0.3, width: 0.16, height: 0.52 } },
  ],
  scene_crowd: [
    { id: 'det_001', label: 'person', confidence: 0.96, bbox: { x: 0.08, y: 0.28, width: 0.15, height: 0.55 } },
    { id: 'det_002', label: 'person', confidence: 0.94, bbox: { x: 0.4, y: 0.32, width: 0.15, height: 0.52 } },
    { id: 'det_003', label: 'person', confidence: 0.92, bbox: { x: 0.7, y: 0.26, width: 0.15, height: 0.56 } },
    { id: 'det_004', label: 'crowd', confidence: 0.91, bbox: { x: 0.04, y: 0.18, width: 0.86, height: 0.7 } },
  ],
  scene_risk_object: [
    { id: 'det_001', label: 'person', confidence: 0.96, bbox: { x: 0.1, y: 0.28, width: 0.16, height: 0.54 } },
    { id: 'det_002', label: 'risk_object', confidence: 0.89, bbox: { x: 0.58, y: 0.62, width: 0.24, height: 0.18 } },
  ],
  scene_high_risk: [
    { id: 'det_001', label: 'person', confidence: 0.96, bbox: { x: 0.08, y: 0.28, width: 0.15, height: 0.55 } },
    { id: 'det_002', label: 'person', confidence: 0.94, bbox: { x: 0.4, y: 0.32, width: 0.15, height: 0.52 } },
    { id: 'det_003', label: 'person', confidence: 0.92, bbox: { x: 0.7, y: 0.26, width: 0.15, height: 0.56 } },
    { id: 'det_004', label: 'crowd', confidence: 0.91, bbox: { x: 0.04, y: 0.18, width: 0.86, height: 0.7 } },
    { id: 'det_005', label: 'risk_object', confidence: 0.89, bbox: { x: 0.58, y: 0.62, width: 0.24, height: 0.18 } },
  ],
}

const LABEL_COLORS: Record<CVLabel, string> = {
  person: '#5be8a9',
  crowd: '#f3b562',
  risk_object: '#ff6b57',
  vehicle: '#8fb6d9',
}

const PHASE_TEXT: Record<Phase, string> = {
  idle: '待识别 · 模拟画面就绪',
  analyzing: '正在分析画面…',
  scanning: '扫描画面中…',
  detecting: '逐个定位检测目标…',
  confidence: '计算置信度…',
  submitting: '提交检测结果至后端…',
  done: '识别完成 · 事件已进入 Event Bus',
}

function personName(index: number, subjects: Agent[]): string {
  return subjects[index] ? agentDisplayName(subjects[index]) : `模拟人员${String(index + 1).padStart(3, '0')}`
}

function boxTitle(detection: PreviewDetection | CVDetection, personIndex: number, subjects: Agent[]): string {
  if (detection.label === 'person') return personName(personIndex, subjects)
  if (detection.label === 'crowd') return '多人聚集'
  if (detection.label === 'risk_object') return '疑似风险物品'
  return '车辆'
}

type Props = { agents: Agent[]; onComplete: (result: CVSceneResult) => void }

export function CVDetectionPanel({ agents, onComplete }: Props) {
  const [sceneId, setSceneId] = useState('scene_high_risk')
  const [phase, setPhase] = useState<Phase>('idle')
  const [detections, setDetections] = useState<PreviewDetection[]>([])
  const [result, setResult] = useState<CVSceneResult | null>(null)
  const [error, setError] = useState('')
  const runningRef = useRef(false)
  const timersRef = useRef<number[]>([])

  const subjects = useMemo(() => agents.slice(0, 3), [agents])
  const preview = SCENE_PREVIEW[sceneId] ?? []
  const busy = phase !== 'idle' && phase !== 'done'

  useEffect(() => () => { timersRef.current.forEach((timer) => window.clearTimeout(timer)) }, [])

  function clearTimers() {
    timersRef.current.forEach((timer) => window.clearTimeout(timer))
    timersRef.current = []
  }

  function switchScene(nextId: string) {
    if (busy || nextId === sceneId) return
    clearTimers()
    runningRef.current = false
    setSceneId(nextId)
    setPhase('idle')
    setDetections([])
    setResult(null)
    setError('')
  }

  function startDetection() {
    if (runningRef.current) return // 连续点击不会重复提交同一次 detection
    runningRef.current = true
    setError('')
    setResult(null)
    setDetections([])
    setPhase('analyzing')
    const schedule = (delay: number, action: () => void) => {
      timersRef.current.push(window.setTimeout(action, delay))
    }
    schedule(500, () => setPhase('scanning'))
    schedule(1000, () => {
      setPhase('detecting')
      setDetections(preview)
    })
    schedule(1500, () => setPhase('confidence'))
    schedule(2000, () => {
      setPhase('submitting')
      void (async () => {
        try {
          const response = await api.cvDetect(sceneId, subjects.map((agent) => agent.id))
          setDetections(response.detections)
          setResult(response)
          setPhase('done')
          onComplete(response)
        } catch (caught) {
          setError(caught instanceof Error ? caught.message : '识别请求失败')
          setPhase('idle')
        } finally {
          runningRef.current = false
        }
      })()
    })
  }

  const personDetections = detections.filter((detection) => detection.label === 'person')
  const showBoxes = phase === 'detecting' || phase === 'confidence' || phase === 'submitting' || phase === 'done'
  const showConfidence = phase === 'confidence' || phase === 'submitting' || phase === 'done'

  return (
    <section className="panel cv-panel" aria-label="CV 智能感知">
      <div className="panel-heading"><span>CV 智能感知</span><em>MOCK CV · SYNTHETIC</em></div>
      <div className="cv-body">
        <div className={`cv-scene phase-${phase}`} aria-label="学校周边模拟监控画面">
          <div className="cv-scene-sky" />
          <div className="cv-gate"><span>校门 DEMO</span></div>
          <div className="cv-road" />
          {preview
            .filter((item) => item.label === 'person')
            .map((item, index) => (
              <div key={`silhouette-${item.id}`} className="cv-person" style={bboxStyle(item.bbox)} aria-hidden="true">
                <i className="cv-head" style={{ animationDelay: `${index * 0.4}s` }} />
                <i className="cv-torso" />
              </div>
            ))}
          {preview.some((item) => item.label === 'risk_object') ? (
            <div className="cv-object" style={bboxStyle(preview.find((item) => item.label === 'risk_object')!.bbox)} aria-hidden="true">
              <i />
            </div>
          ) : null}
          {phase === 'scanning' || phase === 'detecting' || phase === 'confidence' ? <div className="cv-scanline" /> : null}
          {showBoxes
            ? detections.map((detection, index) => {
                const personIndex = detection.label === 'person'
                  ? personDetections.findIndex((item) => item.id === detection.id)
                  : -1
                return (
                  <div
                    key={`box-${detection.id}`}
                    className={`cv-box cv-box-${detection.label}`}
                    style={{ ...bboxStyle(detection.bbox), animationDelay: `${index * 0.25}s` }}
                  >
                    <b>{boxTitle(detection, personIndex, subjects)}</b>
                    {showConfidence ? <em>{Math.round(detection.confidence * 100)}%</em> : null}
                  </div>
                )
              })
            : null}
          <div className="cv-watermark">Synthetic Visual Data / 模拟视觉数据</div>
          <div className="cv-cam">CAM-DEMO-01 · 学校周边模拟监控 · 广州演示场景</div>
        </div>
        <div className="cv-status" aria-live="polite">
          <span className={`cv-status-dot ${phase}`} />
          {PHASE_TEXT[phase]}
          {error ? <b className="cv-error">{error}</b> : null}
        </div>
        <div className="cv-scene-buttons" role="group" aria-label="场景选择">
          {SCENES.map((scene) => (
            <button
              type="button"
              key={scene.id}
              className={sceneId === scene.id ? 'active' : ''}
              onClick={() => switchScene(scene.id)}
              disabled={busy}
              title={scene.hint}
            >
              {scene.name}
            </button>
          ))}
        </div>
        <button type="button" className="cv-run primary" onClick={startDetection} disabled={busy}>
          {busy ? '识别中…' : '开始识别'}
        </button>
        {result ? (
          <div className="cv-result">
            <div className="cv-result-events">
              {result.events.map((event) => (
                <span key={event.id} className={`cv-event-chip chip-${event.type}`}>{event.type}</span>
              ))}
            </div>
            <p>共 {result.detections.length} 个 Detection / {result.events.length} 个标准事件已通过 Event Bus 写入 World State（审计 source=mock_cv）。</p>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function bboxStyle(bbox: CVBBox): { left: string; top: string; width: string; height: string } {
  return {
    left: `${(bbox.x * 100).toFixed(2)}%`,
    top: `${(bbox.y * 100).toFixed(2)}%`,
    width: `${(bbox.width * 100).toFixed(2)}%`,
    height: `${(bbox.height * 100).toFixed(2)}%`,
  }
}
