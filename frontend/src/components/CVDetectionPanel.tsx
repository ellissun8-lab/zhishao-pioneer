import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { agentDisplayName } from '../labels'
import type { Agent, CVBBox, CVDetection, CVLabel, CVSceneResult, CVStatus, CVTrainedResult, VisionAnalyzeResult } from '../types'

type Phase = 'idle' | 'analyzing' | 'scanning' | 'detecting' | 'confidence' | 'submitting' | 'done'
type CVMode = 'mock' | 'trained'
type TrainedPhase = 'idle' | 'running' | 'done'
type VisionPhase = 'idle' | 'running'

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

// Trained CV 模式使用 generator 独立生成的合成测试图（与训练集不同源，seed 隔离）
const DEMO_SCENES: SceneConfig[] = [
  { id: 'demo_normal', name: '正常场景', hint: '独立合成测试图 · 1 人' },
  { id: 'demo_crowd', name: '人员聚集', hint: '独立合成测试图 · 4 人' },
  { id: 'demo_risk', name: '疑似风险物品', hint: '独立合成测试图 · 人 + 物品' },
  { id: 'demo_high_risk', name: '综合高风险', hint: '独立合成测试图 · 3 人 + 物品 + 车' },
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

type Props = {
  agents: Agent[]
  resetVersion: number
  onComplete: (result: CVSceneResult | CVTrainedResult) => void
}

export function CVDetectionPanel({ agents, resetVersion, onComplete }: Props) {
  const [mode, setMode] = useState<CVMode>('mock')
  const [sceneId, setSceneId] = useState('scene_high_risk')
  const [phase, setPhase] = useState<Phase>('idle')
  const [detections, setDetections] = useState<PreviewDetection[]>([])
  const [result, setResult] = useState<CVSceneResult | null>(null)
  const [error, setError] = useState('')
  const [cvStatus, setCvStatus] = useState<CVStatus | null>(null)
  const [demoSceneId, setDemoSceneId] = useState('demo_high_risk')
  const [trainedPhase, setTrainedPhase] = useState<TrainedPhase>('idle')
  const [trainedResult, setTrainedResult] = useState<CVTrainedResult | null>(null)
  const [trainedError, setTrainedError] = useState('')
  const [visionPhase, setVisionPhase] = useState<VisionPhase>('idle')
  const [visionResult, setVisionResult] = useState<VisionAnalyzeResult | null>(null)
  const [visionError, setVisionError] = useState('')
  const runningRef = useRef(false)
  const timersRef = useRef<number[]>([])
  const generationRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const trainedAbortRef = useRef<AbortController | null>(null)

  const subjects = useMemo(() => agents.slice(0, 3), [agents])
  const preview = SCENE_PREVIEW[sceneId] ?? []
  const busy = (mode === 'mock' && phase !== 'idle' && phase !== 'done') || (mode === 'trained' && trainedPhase === 'running')

  useEffect(() => {
    void api.getCVStatus()
      .then(setCvStatus)
      .catch(() => setCvStatus(null))
  }, [])

  useEffect(() => {
    generationRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    trainedAbortRef.current?.abort()
    trainedAbortRef.current = null
    clearTimers()
    runningRef.current = false
    setMode('mock')
    setSceneId('scene_high_risk')
    setPhase('idle')
    setDetections([])
    setResult(null)
    setError('')
    setDemoSceneId('demo_high_risk')
    setTrainedPhase('idle')
    setTrainedResult(null)
    setTrainedError('')
    setVisionPhase('idle')
    setVisionResult(null)
    setVisionError('')
  }, [resetVersion])

  useEffect(() => () => {
    generationRef.current += 1
    abortRef.current?.abort()
    trainedAbortRef.current?.abort()
    clearTimers()
  }, [])

  function clearTimers() {
    timersRef.current.forEach((timer) => window.clearTimeout(timer))
    timersRef.current = []
  }

  function switchMode(next: CVMode) {
    if (busy || next === mode) return
    clearTimers()
    generationRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    trainedAbortRef.current?.abort()
    trainedAbortRef.current = null
    runningRef.current = false
    setMode(next)
    setPhase('idle')
    setDetections([])
    setResult(null)
    setError('')
    setTrainedPhase('idle')
    setTrainedResult(null)
    setTrainedError('')
    setVisionPhase('idle')
    setVisionResult(null)
    setVisionError('')
  }

  function switchScene(nextId: string) {
    if (busy || nextId === sceneId) return
    clearTimers()
    generationRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    runningRef.current = false
    setSceneId(nextId)
    setPhase('idle')
    setDetections([])
    setResult(null)
    setError('')
  }

  function switchDemoScene(nextId: string) {
    if (busy || nextId === demoSceneId) return
    trainedAbortRef.current?.abort()
    trainedAbortRef.current = null
    setDemoSceneId(nextId)
    setTrainedPhase('idle')
    setTrainedResult(null)
    setTrainedError('')
    setVisionPhase('idle')
    setVisionResult(null)
    setVisionError('')
  }

  function startDetection() {
    if (runningRef.current) return // 连续点击不会重复提交同一次 detection
    runningRef.current = true
    const generation = generationRef.current
    const controller = new AbortController()
    abortRef.current = controller
    setError('')
    setResult(null)
    setDetections([])
    setPhase('analyzing')
    const schedule = (delay: number, action: () => void) => {
      timersRef.current.push(window.setTimeout(() => {
        if (generation === generationRef.current) action()
      }, delay))
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
          const response = await api.cvDetect(sceneId, subjects.map((agent) => agent.id), controller.signal)
          if (generation !== generationRef.current) return
          setDetections(response.detections)
          setResult(response)
          setPhase('done')
          onComplete(response)
        } catch (caught) {
          if (generation !== generationRef.current) return
          setError(caught instanceof Error ? caught.message : '识别请求失败')
          setPhase('idle')
        } finally {
          if (generation === generationRef.current) {
            runningRef.current = false
            abortRef.current = null
          }
        }
      })()
    })
  }

  // Trained CV：调用 /api/perception/cv/detect-image，后端真实执行 YOLO.predict；
  // 前端只渲染响应中的 detections（置信度/边界框全部来自模型输出，禁止伪造）
  function runTrainedDetection() {
    if (trainedPhase === 'running') return
    const controller = new AbortController()
    trainedAbortRef.current = controller
    setTrainedPhase('running')
    setTrainedResult(null)
    setTrainedError('')
    void (async () => {
      try {
        const response = await api.cvDetectTrained(demoSceneId, subjects.map((agent) => agent.id), controller.signal)
        setTrainedResult(response)
        setTrainedPhase('done')
        onComplete(response)
      } catch (caught) {
        setTrainedError(caught instanceof Error ? caught.message : '训练模型推理请求失败')
        setTrainedPhase('idle')
      } finally {
        trainedAbortRef.current = null
      }
    })()
  }

  // Qwen3.8-Max Vision：语义理解（与 YOLO 检测严格分工，不产出 bbox/检测置信度）
  function runQwenVision() {
    if (visionPhase === 'running') return
    setVisionPhase('running')
    setVisionResult(null)
    setVisionError('')
    void (async () => {
      try {
        const response = await api.visionAnalyze(demoSceneId)
        setVisionResult(response)
        setVisionPhase('idle')
      } catch (caught) {
        setVisionError(caught instanceof Error ? caught.message : 'Qwen 视觉理解请求失败')
        setVisionPhase('idle')
      }
    })()
  }

  const personDetections = detections.filter((detection) => detection.label === 'person')
  const showBoxes = phase === 'detecting' || phase === 'confidence' || phase === 'submitting' || phase === 'done'
  const showConfidence = phase === 'confidence' || phase === 'submitting' || phase === 'done'
  const trainedPersons = trainedResult?.detections.filter((item) => item.label === 'person') ?? []
  const modelBadge = trainedResult
    ? trainedResult.provider === 'real' && trainedResult.model_invoked
      ? { text: 'REAL MODEL', className: 'cv-badge real' }
      : { text: 'MOCK FALLBACK', className: 'cv-badge fallback' }
    : null

  return (
    <section className="panel cv-panel" aria-label="CV 智能感知">
      <div className="panel-heading">
        <span>CV 智能感知</span>
        <em>{mode === 'mock' ? 'MOCK CV · SYNTHETIC' : 'TRAINED CV · YOLO'}</em>
      </div>
      <div className="cv-body">
        <div className="cv-mode-switch" role="group" aria-label="CV Provider 选择">
          <button
            type="button"
            className={mode === 'mock' ? 'active' : ''}
            onClick={() => switchMode('mock')}
            disabled={busy}
            data-testid="cv-mode-mock"
          >
            Mock CV
          </button>
          <button
            type="button"
            className={mode === 'trained' ? 'active' : ''}
            onClick={() => switchMode('trained')}
            disabled={busy}
            data-testid="cv-mode-trained"
          >
            Trained CV
          </button>
        </div>

        {mode === 'mock' ? (
          <>
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
          </>
        ) : (
          <>
            <div className="cv-scene cv-trained-scene" aria-label="合成测试图 · 训练模型推理画面">
              <img
                className="cv-trained-image"
                src={api.cvDemoImageUrl(demoSceneId)}
                alt={`独立合成测试图 ${demoSceneId}`}
              />
              {trainedPhase === 'running' ? <div className="cv-scanline" /> : null}
              {trainedResult
                ? trainedResult.detections.map((detection) => {
                    const personIndex = detection.label === 'person'
                      ? trainedPersons.findIndex((item) => item.id === detection.id)
                      : -1
                    return (
                      <div
                        key={`tbox-${detection.id}`}
                        className={`cv-box cv-box-${detection.label}`}
                        style={bboxStyle(detection.bbox)}
                        data-testid="cv-trained-box"
                      >
                        <b>{boxTitle(detection, personIndex, subjects)}</b>
                        <em>{Math.round(detection.confidence * 100)}%</em>
                      </div>
                    )
                  })
                : null}
              {trainedResult?.crowd ? (
                <div className="cv-box cv-box-crowd cv-crowd-agg" style={bboxStyle(trainedResult.crowd.bbox)} data-testid="cv-crowd-agg">
                  <b>多人聚集（感知层聚合）</b>
                  <em>{Math.round(trainedResult.crowd.confidence * 100)}%</em>
                </div>
              ) : null}
              <div className="cv-watermark">Synthetic Visual Data / 模拟视觉数据</div>
              <div className="cv-cam">CAM-DEMO-02 · 独立合成测试图 · 训练模型真实推理</div>
            </div>
            <div className="cv-status" aria-live="polite">
              <span className={`cv-status-dot ${trainedPhase === 'running' ? 'detecting' : trainedPhase === 'done' ? 'done' : 'idle'}`} />
              {trainedPhase === 'idle' ? '待推理 · 合成测试图就绪' : trainedPhase === 'running' ? '训练模型推理中（YOLO.predict）…' : '推理完成 · 事件已进入 Event Bus'}
              {trainedError ? <b className="cv-error">{trainedError}</b> : null}
            </div>
            <div className="cv-scene-buttons" role="group" aria-label="合成测试图选择">
              {DEMO_SCENES.map((scene) => (
                <button
                  type="button"
                  key={scene.id}
                  className={demoSceneId === scene.id ? 'active' : ''}
                  onClick={() => switchDemoScene(scene.id)}
                  disabled={busy}
                  title={scene.hint}
                >
                  {scene.name}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="cv-run primary"
              onClick={runTrainedDetection}
              disabled={busy}
              data-testid="cv-run-trained"
            >
              {busy ? '模型推理中…' : '运行训练模型'}
            </button>
            <button
              type="button"
              className="cv-run cv-run-qwen"
              onClick={runQwenVision}
              disabled={visionPhase === 'running'}
              data-testid="cv-run-qwen-vision"
            >
              {visionPhase === 'running' ? 'Qwen 理解中…' : 'Qwen视觉理解'}
            </button>
            {visionResult ? (
              <div className="cv-qwen-vision" data-testid="cv-qwen-vision-result">
                <div className="cv-qwen-vision-head">
                  <span className="cv-qwen-vision-source" data-testid="cv-qwen-vision-source">Qwen3.8-Max Vision · 语义理解</span>
                  {visionResult.fallback ? (
                    <span className="cv-badge fallback" data-testid="cv-qwen-vision-offline">Qwen3.8-Max Offline</span>
                  ) : null}
                </div>
                {visionResult.fallback || !visionResult.structured ? (
                  <p className="cv-qwen-vision-note">{visionResult.note ?? visionResult.error ?? 'Qwen 视觉理解不可用'}</p>
                ) : (
                  <div className="cv-qwen-vision-body">
                    <p><b>估计人数</b> {visionResult.structured.estimated_people} 人 <b>车辆可见</b> {visionResult.structured.vehicle_visible ? '是' : '否'} <b>疑似风险物品</b> {visionResult.structured.possible_risk_object ? '是' : '否'}</p>
                    {visionResult.structured.crowd_semantics ? <p><b>人群语义</b> {visionResult.structured.crowd_semantics}</p> : null}
                    {visionResult.structured.summary ? <p><b>场景总结</b> {visionResult.structured.summary}</p> : null}
                    <p className="cv-qwen-vision-meta">
                      Synthetic Visual Data · {visionResult.latency_ms != null ? `${Math.round(visionResult.latency_ms)}ms` : '-'}
                      {visionResult.request_id ? ` · request ${visionResult.request_id.slice(0, 12)}…` : ''}
                      （语义理解结果，非 YOLO 检测，不产出 bbox/置信度，不写入事件链）
                    </p>
                  </div>
                )}
              </div>
            ) : null}
            {visionError ? <p className="cv-error">{visionError}</p> : null}
            {modelBadge ? <div className={modelBadge.className} data-testid="cv-provider-badge">{modelBadge.text}</div> : null}
            {trainedResult ? (
              <div className="cv-result">
                <div className="cv-result-events">
                  {trainedResult.events.map((event) => (
                    <span key={event.id} className={`cv-event-chip chip-${event.type}`}>{event.type}</span>
                  ))}
                </div>
                <p>
                  共 {trainedResult.detections.length} 个 Detection / {trainedResult.events.length} 个标准事件
                  {trainedResult.crowd ? ` / 感知层聚合出聚集（${trainedResult.crowd.person_count} 人）` : ''}
                  已通过 Event Bus 写入 World State（审计 source={trainedResult.provider === 'real' ? 'real_cv' : 'mock_fallback'}，
                  推理 {trainedResult.latency_ms != null ? `${trainedResult.latency_ms.toFixed(0)}ms` : '-'}）。
                </p>
                <p className="cv-model-meta">
                  Provider: {trainedResult.provider === 'real' ? 'REAL MODEL' : 'MOCK FALLBACK'} ·
                  model_invoked: {String(trainedResult.model_invoked)} ·
                  {trainedResult.model_version ? ` ${trainedResult.model_version}` : ' 模型未加载'}
                  {trainedResult.fallback_reason ? ` · 回退原因：${trainedResult.fallback_reason}` : ''}
                </p>
              </div>
            ) : (
              <p className="cv-model-meta">
                模型状态：{cvStatus ? (cvStatus.model_available ? `已就绪（${cvStatus.model_version ?? 'cv_yolo'}）` : `不可用（${cvStatus.unavailable_reason ?? 'models/cv_detector/best.pt 缺失'}，将回退 Mock）`) : '查询中…'}
              </p>
            )}
          </>
        )}
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
