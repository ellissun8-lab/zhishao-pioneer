import type { Agent, Position, Strategy, Zone } from '../types'
import { DEMO_MAP_CONFIG } from '../config/map'

export type CoordinateSystem = 'gcj02' | 'wgs84'

const SOURCE_COORDINATE_SYSTEM: CoordinateSystem = 'gcj02'

export function toAMapPosition(position: Position): Position {
  if (SOURCE_COORDINATE_SYSTEM === 'gcj02') return position
  return position
}

export function lngLat(position: Position): [number, number] {
  const converted = toAMapPosition(position)
  return [converted.lng, converted.lat]
}

export function projectToPercent(position: Position): { left: string; top: string } {
  const left = 50 + (position.lng - DEMO_MAP_CONFIG.center[0]) * 1200
  const top = 50 - (position.lat - DEMO_MAP_CONFIG.center[1]) * 1600
  return { left: `${Math.max(4, Math.min(96, left))}%`, top: `${Math.max(4, Math.min(96, top))}%` }
}

export function circlePolygon(center: Position, radiusMeters: number, points = 8): [number, number][] {
  const latitudeRadians = center.lat * Math.PI / 180
  const latitudeDelta = radiusMeters / 111_320
  const longitudeDelta = radiusMeters / (111_320 * Math.cos(latitudeRadians))
  return Array.from({ length: points }, (_, index) => {
    const angle = (Math.PI * 2 * index) / points
    return [center.lng + longitudeDelta * Math.cos(angle), center.lat + latitudeDelta * Math.sin(angle)]
  })
}

export function projectAwayFrom(center: Position, origin: Position, scale: number): Position {
  const lngDelta = origin.lng - center.lng
  const latDelta = origin.lat - center.lat
  const length = Math.hypot(lngDelta, latDelta) || 0.004
  return {
    lng: origin.lng + (lngDelta / length) * scale,
    lat: origin.lat + (latDelta / length) * scale,
  }
}

export function getSimulationEndpoint(agent: Agent, zone: Zone | undefined, strategy: Strategy): Position {
  const center = zone?.center ?? { lng: DEMO_MAP_CONFIG.center[0], lat: DEMO_MAP_CONFIG.center[1] }
  const strategyScale = strategy === 'none' ? -0.002 : strategy === 'warn' ? 0.003 : strategy === 'guide_leave' ? 0.006 : 0.001
  return strategy === 'none' && agent.destination ? agent.destination : projectAwayFrom(center, agent.position, strategyScale)
}
