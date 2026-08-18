import type { Prediction, SimulationResult, Strategy, WorldState } from '../types'

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
  chat: (message: string) =>
    request<{ answer: string }>('/api/chat', { method: 'POST', body: JSON.stringify({ message }) }),
}

