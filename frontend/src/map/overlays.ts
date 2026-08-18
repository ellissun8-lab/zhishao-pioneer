import { DEMO_MAP_CONFIG } from '../config/map'
import type { Agent, Place, Position, SimulationResult, WorldEvent, Zone } from '../types'
import { circlePolygon, getSimulationEndpoint, lngLat } from './coordinates'

type InfoWindowLike = { setContent: (content: string) => void; open: (map: any, position: [number, number]) => void }

const EVENT_COLORS: Record<string, string> = {
  ZoneEntered: '#65d9b8',
  CrowdGathered: '#f3b562',
  CrowdDetected: '#d9c98f',
  RiskObjectDetected: '#ff6650',
  AlertTriggered: '#ff3f56',
  VehicleDetected: '#8fb6d9',
}

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function showInfo(infoWindow: InfoWindowLike, map: any, position: Position, title: string, rows: Array<[string, unknown]>) {
  const details = rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')
  infoWindow.setContent(`<section class="amap-info-card"><header>${escapeHtml(title)}</header>${details}</section>`)
  infoWindow.open(map, lngLat(position))
}

export function createAgentMarker(
  AMap: any,
  map: any,
  infoWindow: InfoWindowLike,
  agent: Agent,
  onClick: (agent: Agent) => void,
): any {
  const color = agent.risk_level === 'high' ? '#ff5d46' : agent.risk_level === 'medium' ? '#ffb547' : '#65d99c'
  const marker = new AMap.Marker({
    position: lngLat(agent.position),
    title: `${agent.id} · Synthetic Data`,
    content: `<div class="amap-agent" style="--agent-color:${color}"><span></span></div>`,
    offset: new AMap.Pixel(-9, -9),
    zIndex: agent.risk_level === 'high' ? 120 : 100,
  })
  marker.on('click', () => {
    onClick(agent)
    showInfo(infoWindow, map, agent.position, `${agent.id} · Synthetic Data`, [
      ['risk_level', agent.risk_level],
      ['risk_score', agent.risk_score.toFixed(1)],
      ['behavior_state', agent.behavior_state],
      ['position', `${agent.position.lng.toFixed(6)}, ${agent.position.lat.toFixed(6)}`],
    ])
  })
  return marker
}

export function createHistoricalTrack(AMap: any, agent: Agent): any | null {
  const points = [...agent.history, agent.position]
  if (points.length < 2) return null
  return new AMap.Polyline({
    path: points.map(lngLat),
    strokeColor: '#49c9b0',
    strokeWeight: 4,
    strokeOpacity: 0.92,
    lineJoin: 'round',
    showDir: true,
    zIndex: 80,
    extData: { kind: 'history', source: 'World State Agent.history' },
  })
}

export function createPredictedTrack(AMap: any, agent: Agent): any[] {
  if (!agent.destination) return []
  return [
    new AMap.Polyline({
      path: [lngLat(agent.position), lngLat(agent.destination)],
      strokeColor: '#f3c86a',
      strokeWeight: 3,
      strokeStyle: 'dashed',
      strokeOpacity: 0.95,
      lineJoin: 'round',
      zIndex: 82,
      extData: { kind: 'prediction', source: 'World State Agent.destination' },
    }),
    new AMap.Text({
      position: lngLat(agent.destination),
      text: 'Predicted / 模拟预测',
      anchor: 'bottom-center',
      offset: new AMap.Pixel(0, -8),
      style: { color: '#f3c86a', background: '#111b1ddd', border: '1px solid #8c6a32', padding: '4px 7px', fontSize: '10px' },
      zIndex: 83,
    }),
  ]
}

export function createZoneOverlays(AMap: any, map: any, infoWindow: InfoWindowLike, zone: Zone, onClick: (zone: Zone) => void): any[] {
  const displayId = zone.id === 'school_zone_001' ? DEMO_MAP_CONFIG.schoolZoneDisplayId : zone.id
  const openZone = () => {
    onClick(zone)
    showInfo(infoWindow, map, zone.center, `${zone.name} · ${displayId}`, [
      ['World State ID', zone.id],
      ['zone_type', zone.zone_type],
      ['radius', `${zone.radius} m`],
      ['sensitivity', zone.sensitivity],
    ])
  }
  const circle = new AMap.Circle({
    center: lngLat(zone.center), radius: zone.radius, fillColor: '#ff553d', fillOpacity: 0.12,
    strokeColor: '#ff7967', strokeOpacity: 0.9, strokeWeight: 2, zIndex: 50,
  })
  const polygon = new AMap.Polygon({
    path: circlePolygon(zone.center, zone.radius * 1.08), fillOpacity: 0, strokeColor: '#ffb09f',
    strokeOpacity: 0.45, strokeWeight: 1, strokeStyle: 'dashed', zIndex: 49,
  })
  const label = new AMap.Text({
    position: lngLat(zone.center), text: `${displayId} · Synthetic Zone`, anchor: 'bottom-center',
    offset: new AMap.Pixel(0, -14),
    style: { color: '#ffb09f', background: '#241513dd', border: '1px solid #7b3d34', padding: '4px 7px', fontSize: '10px' },
    zIndex: 51,
  })
  circle.on('click', openZone)
  polygon.on('click', openZone)
  label.on('click', openZone)
  return [polygon, circle, label]
}

export function createPlaceMarker(AMap: any, place: Place): any {
  return new AMap.Marker({
    position: lngLat(place.position), title: place.name,
    content: `<div class="amap-place">${place.category === 'school' ? '校' : place.category === 'hospital' ? '医' : '站'}</div>`,
    offset: new AMap.Pixel(-12, -12), zIndex: 60,
  })
}

function resolveEventPosition(event: WorldEvent, agents: Agent[], zones: Zone[]): Position | null {
  const metadataPosition = event.metadata.position
  if (
    metadataPosition && typeof metadataPosition === 'object' &&
    'lng' in metadataPosition && typeof metadataPosition.lng === 'number' &&
    'lat' in metadataPosition && typeof metadataPosition.lat === 'number'
  ) return { lng: metadataPosition.lng, lat: metadataPosition.lat }
  const subject = agents.find((agent) => agent.id === event.subject_id)
  if (subject) return subject.position
  const objectZone = zones.find((zone) => zone.id === event.object_id)
  return objectZone?.center ?? null
}

export function createEventMarker(
  AMap: any,
  map: any,
  infoWindow: InfoWindowLike,
  event: WorldEvent,
  agents: Agent[],
  zones: Zone[],
): any | null {
  if (!(event.type in EVENT_COLORS)) return null
  const position = resolveEventPosition(event, agents, zones)
  if (!position) return null
  const color = EVENT_COLORS[event.type]
  const marker = new AMap.Marker({
    position: lngLat(position), title: `${event.type} · ${event.source}`,
    content: `<div class="amap-event" style="--event-color:${color}">!</div>`,
    offset: new AMap.Pixel(10, -24), zIndex: 150,
  })
  marker.on('click', () => showInfo(infoWindow, map, position, `${event.type} · Event`, [
    ['timestamp', new Date(event.timestamp).toLocaleString('zh-CN', { hour12: false })],
    ['source', event.source],
    ['confidence', `${(event.confidence * 100).toFixed(0)}%`],
    ['subject', event.subject_id ?? 'system'],
  ]))
  return marker
}

export function createSimulationOverlays(
  AMap: any,
  agent: Agent,
  zone: Zone | undefined,
  result: SimulationResult,
): any[] {
  const endpoint = getSimulationEndpoint(agent, zone, result.strategy)
  return [
    new AMap.Polyline({
      path: [lngLat(agent.position), lngLat(endpoint)], strokeColor: '#8e7dff', strokeWeight: 5,
      strokeStyle: 'dashed', strokeOpacity: 0.9, zIndex: 180,
      extData: { kind: 'simulation', strategy: result.strategy },
    }),
    new AMap.Marker({
      position: lngLat(endpoint), content: '<div class="amap-simulation-marker">SIM</div>',
      offset: new AMap.Pixel(-17, -17), zIndex: 181, title: `Simulation · ${result.strategy}`,
    }),
    new AMap.Text({
      position: lngLat(endpoint),
      text: `模拟推演结果 / Simulation · ${result.before.risk.toFixed(0)} → ${result.after.risk.toFixed(0)}`,
      anchor: 'bottom-center', offset: new AMap.Pixel(0, -24),
      style: { color: '#d4ceff', background: '#17142ddd', border: '1px solid #7369c6', padding: '5px 8px', fontSize: '10px' },
      zIndex: 182,
    }),
  ]
}
