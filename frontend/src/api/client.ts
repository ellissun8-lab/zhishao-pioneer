import type { ChatTrace, CVSceneResult, CVStatus, CVTrainedResult, LLMStatus, MLRecommend, MLRiskPrediction, MLStatus, Prediction, SimulationResult, Strategy, VisionAnalyzeResult, WorldState } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`)
  return response.json() as Promise<T>
}

export const api = {
  getWorld: () => request<WorldState>('/api/world/state'),
  advance: () => request<{ state: WorldState }>('/api/world/advance', { method: 'POST' }),
  reset: () => request<WorldState>('/api/world/reset', { method: 'POST' }),
  tick: (steps = 1, dtSeconds = 45) =>
    request<{ state: WorldState; events: unknown[] }>('/api/world/tick', {
      method: 'POST',
      body: JSON.stringify({ steps, dt_seconds: dtSeconds }),
    }),
  predict: (minutes = 10) => request<Prediction>(`/api/world/predict?horizon_minutes=${minutes}`),
  compare: (minutes = 10) => request<SimulationResult[]>(`/api/simulation/compare?horizon_minutes=${minutes}`),
  simulate: (strategy: Strategy, minutes = 10) =>
    request<SimulationResult>('/api/simulation/run', {
      method: 'POST',
      body: JSON.stringify({ strategy, horizon_minutes: minutes }),
    }),
  mockDetection: (detection: string) =>
    request('/api/perception/mock', {
      method: 'POST',
      body: JSON.stringify({ detection, subject_id: 'agent_A' }),
    }),
  cvDetect: (sceneId: string, subjectIds: string[], signal?: AbortSignal) =>
    request<CVSceneResult>('/api/perception/mock-cv/detect', {
      method: 'POST',
      body: JSON.stringify({ scene_id: sceneId, subject_ids: subjectIds }),
      signal,
    }),
  getCVStatus: () => request<CVStatus>('/api/perception/cv/status'),
  // Trained CV：multipart 上传 demo_scene_id + provider=real，后端真实调用 YOLO.predict
  cvDetectTrained: (demoSceneId: string, subjectIds: string[], signal?: AbortSignal) => {
    const form = new FormData()
    form.append('demo_scene_id', demoSceneId)
    form.append('provider', 'real')
    if (subjectIds.length > 0) form.append('subject_ids', subjectIds.join(','))
    return fetch(`${API_BASE}/api/perception/cv/detect-image`, { method: 'POST', body: form, signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`)
        return response.json() as Promise<CVTrainedResult>
      })
  },
  cvDemoImageUrl: (demoSceneId: string) =>
    `${API_BASE}/api/perception/cv/demo-image/${demoSceneId}`,
  chat: (message: string) =>
    request<{ answer: string; tools_used?: string[] } & Partial<ChatTrace>>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  getLLMStatus: () => request<LLMStatus>('/api/llm/status'),
  // Qwen3.8-Max Vision：语义理解（非 YOLO 检测）
  visionAnalyze: (demoSceneId: string) =>
    request<VisionAnalyzeResult>('/api/llm/vision/analyze', {
      method: 'POST',
      body: JSON.stringify({ demo_scene_id: demoSceneId }),
    }),
  getMLStatus: () => request<MLStatus>('/api/ml/status'),
  getMLRecommend: () => request<MLRecommend>('/api/ml/recommend'),
  predictMLRisk: (horizonMinutes: number) =>
    request<MLRiskPrediction>('/api/ml/predict-risk', {
      method: 'POST',
      body: JSON.stringify({ horizon_minutes: horizonMinutes }),
    }),
}
