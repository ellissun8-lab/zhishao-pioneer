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

export type ChatMessage = { role: 'user' | 'assistant'; content: string; trace?: ChatTrace }

export type ChatTrace = {
  provider: string
  model: string | null
  tools_used: string[]
  tool_rounds: number
  request_id: string | null
  latency_ms: number | null
  fallback: boolean
  fallback_reason?: string | null
}

export type LLMStatus = {
  provider: string
  model: string
  configured: boolean
  connected: boolean
  function_calling: boolean
  multimodal: boolean
  fallback: boolean
  fallback_reason: string | null
  components: {
    cv_detector: { name: string; status: string; model_version: string | null; model_path: string; available: boolean }
    risk_forecast: { name: string; status: string; model_version: string | null }
    policy_model: { name: string; status: string; model_version: string | null }
  }
}

export type VisionStructured = {
  estimated_people: number
  vehicle_visible: boolean
  possible_risk_object: boolean
  crowd_semantics: string
  summary: string
  synthetic_visual_data: boolean
}

export type VisionAnalyzeResult = {
  fallback: boolean
  provider: string
  model: string
  source?: string
  scene_id?: string
  structured: VisionStructured | null
  raw_content?: string | null
  parse_error?: boolean
  request_id?: string | null
  latency_ms?: number
  note?: string
  error?: string
}

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

export type CVCrowdSummary = {
  person_count: number
  max_pair_distance: number
  confidence: number
  bbox: CVBBox
  centroid: number[]
  detection_ids: string[]
}

// /api/perception/cv/detect-image 的真实推理响应（Trained CV 模式）
export type CVTrainedResult = {
  provider: 'real' | 'mock_fallback'
  model_invoked: boolean
  model_path?: string | null
  model_version?: string | null
  synthetic_visual_data: boolean
  scene_id: string
  conf_threshold?: number
  latency_ms?: number
  fallback_reason?: string
  detections: CVDetection[]
  events: WorldEvent[]
  crowd: CVCrowdSummary | null
  risk_state?: RiskState
  note?: string
}

export type CVStatus = {
  provider_preference: 'mock' | 'real'
  model_available: boolean
  model_loaded: boolean
  model_path: string
  model_version: string | null
  class_names: string[]
  conf_threshold: number
  unavailable_reason: string | null
  last_inference: {
    provider: 'real' | 'mock_fallback'
    model_invoked: boolean
    model_version: string | null
    scene_id: string | null
    detection_count: number
    labels: string[]
    confidences: number[]
    crowd: CVCrowdSummary | null
    latency_ms: number | null
    fallback_reason?: string
    timestamp: string
  } | null
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

export type MLRiskPrediction = {
  model: string
  model_type: string
  model_version: string | null
  horizon_minutes: number
  prediction: number
  test_mae?: number | null
  input_features: Record<string, number>
  synthetic_training: boolean
  fallback: boolean
  fallback_source?: string | null
  note?: string | null
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
    model_type?: string
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
