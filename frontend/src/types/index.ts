export type Position = { lng: number; lat: number }

export type Agent = {
  id: string
  type: 'Person'
  synthetic: true
  display_name: string
  risk_level: 'low' | 'medium' | 'high'
  position: Position
  destination: Position | null
  behavior_state: string
  risk_score: number
  active_zone_ids: string[]
  history: Position[]
  social_group: string
}

export type Zone = {
  id: string
  name: string
  zone_type: string
  center: Position
  radius: number
  sensitivity: number
}

export type Place = {
  id: string
  name: string
  category: string
  position: Position
  source: string
}

export type WorldEvent = {
  id: string
  type: string
  subject_id: string | null
  object_id: string | null
  timestamp: string
  confidence: number
  source: string
  metadata: Record<string, unknown>
}

export type RiskState = {
  overall_score: number
  level: 'low' | 'medium' | 'high' | 'critical'
  reasons: string[]
  contributors: Array<{ type: string; delta: number }>
  rule_contributions: Record<string, number>
  history: number[]
}

export type WorldState = {
  timestamp: string
  agents: Record<string, Agent>
  places: Record<string, Place>
  zones: Record<string, Zone>
  active_events: WorldEvent[]
  risk_state: RiskState
}

export type Prediction = {
  horizon_minutes: number
  risk_score: number
  risk_trend: string
  gather_probability: number
  zone_entry_probability: number
  predicted_agents: number
  model?: string
  synthetic?: boolean
}

export type Strategy = 'none' | 'warn' | 'guide_leave' | 'intervene'

export type SimulationResult = {
  strategy: Strategy
  horizon_minutes: number
  before: { risk: number; crowd_size: number }
  after: { risk: number; crowd_size: number }
  changes: string[]
  action_cost: number
  leave_probability: number
  prediction: Prediction
  synthetic: true
}

export type ChatMessage = { role: 'user' | 'assistant'; content: string }

export type CVLabel = 'person' | 'crowd' | 'risk_object' | 'vehicle'

export type CVBBox = { x: number; y: number; width: number; height: number }

export type CVDetection = {
  id: string
  label: CVLabel
  confidence: number
  bbox: CVBBox
  subject_id: string | null
  synthetic: true
}

export type CVSceneResult = {
  scene_id: string
  synthetic: boolean
  detections: CVDetection[]
  events: WorldEvent[]
  risk_state?: RiskState
}

export type MLStatus = {
  risk_available: boolean
  policy_available: boolean
  fallback_note: string | null
  model_version?: string | null
  episodes: number
  train_rows: number
  validation_rows: number
  test_rows: number
  test_risk_mae_10m: number | null
  test_policy_macro_f1: number | null
  synthetic_training: boolean
}

export type MLRecommendSimulation = {
  strategy: Strategy
  before_risk: number
  after_risk: number
  action_cost: number
  utility: number
}

export type MLRecommend = {
  recommendation: {
    model: string
    model_version: string | null
    strategy: Strategy
    probabilities: Record<string, number> | null
    confidence: number | null
    synthetic_training: boolean
    note?: string
  }
  fallback: boolean
  simulation: MLRecommendSimulation[]
  best_by_simulation: Strategy
  explanation: string
  synthetic: boolean
}

