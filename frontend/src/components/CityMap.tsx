import { useEffect, useRef, useState } from 'react'
import { DEMO_MAP_CONFIG } from '../config/map'
import { loadAMap, waitForMapReady } from '../map/amap'
import { getSimulationEndpoint, projectToPercent } from '../map/coordinates'
import {
  createAgentMarker,
  createEventMarker,
  createHistoricalTrack,
  createPlaceMarker,
  createPredictedTrack,
  createSimulationOverlays,
  createZoneOverlays,
} from '../map/overlays'
import type { Agent, Place, SimulationResult, WorldEvent, Zone } from '../types'
import { AgentMarker } from './AgentMarker'

type Props = {
  agents: Agent[]
  places: Place[]
  zones: Zone[]
  events: WorldEvent[]
  selectedAgent: Agent | null
  trackMode: 'history' | 'prediction'
  simulationResult: SimulationResult | null
  onSelectAgent: (agent: Agent) => void
  onSelectZone: (zone: Zone) => void
  onCloseSimulation: () => void
}

type MapStatus = 'loading' | 'ready' | 'fallback'

function fallbackEventPosition(event: WorldEvent, agents: Agent[], zones: Zone[]) {
  const agent = agents.find((item) => item.id === event.subject_id)
  if (agent) return projectToPercent(agent.position)
  const zone = zones.find((item) => item.id === event.object_id)
  return zone ? projectToPercent(zone.center) : { left: '50%', top: '50%' }
}

export function CityMap({
  agents,
  places,
  zones,
  events,
  selectedAgent,
  trackMode,
  simulationResult,
  onSelectAgent,
  onSelectZone,
  onCloseSimulation,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const amapRef = useRef<any>(null)
  const infoWindowRef = useRef<any>(null)
  const overlaysRef = useRef<any[]>([])
  const agentHandlerRef = useRef(onSelectAgent)
  const zoneHandlerRef = useRef(onSelectZone)
  const [mapStatus, setMapStatus] = useState<MapStatus>('loading')
  const [fallbackReason, setFallbackReason] = useState('')

  agentHandlerRef.current = onSelectAgent
  zoneHandlerRef.current = onSelectZone

  const fallbackSimulationEndpoint = selectedAgent && simulationResult
    ? getSimulationEndpoint(selectedAgent, zones[0], simulationResult.strategy)
    : null

  useEffect(() => {
    let cancelled = false
    let createdMap: any = null
    async function initialize() {
      try {
        const AMap = await loadAMap()
        if (cancelled || !containerRef.current) return
        createdMap = new AMap.Map(containerRef.current, {
          zoom: DEMO_MAP_CONFIG.zoom,
          center: DEMO_MAP_CONFIG.center,
          mapStyle: DEMO_MAP_CONFIG.mapStyle,
          viewMode: DEMO_MAP_CONFIG.viewMode,
          resizeEnable: true,
        })
        await waitForMapReady(createdMap)
        if (cancelled) {
          createdMap.destroy()
          return
        }
        amapRef.current = AMap
        mapRef.current = createdMap
        infoWindowRef.current = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -18), isCustom: true })
        createdMap.addControl(new AMap.Scale())
        createdMap.addControl(new AMap.ToolBar({ position: 'RB' }))
        setMapStatus('ready')
      } catch (caught) {
        createdMap?.destroy()
        if (!cancelled) {
          setFallbackReason(caught instanceof Error ? caught.message : 'AMAP_INITIALIZATION_FAILED')
          setMapStatus('fallback')
        }
      }
    }
    void initialize()
    return () => {
      cancelled = true
      infoWindowRef.current?.close()
      if (mapRef.current && overlaysRef.current.length) mapRef.current.remove(overlaysRef.current)
      overlaysRef.current = []
      mapRef.current?.destroy()
      mapRef.current = null
      amapRef.current = null
      infoWindowRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const AMap = amapRef.current
    const infoWindow = infoWindowRef.current
    if (!map || !AMap || !infoWindow || mapStatus !== 'ready') return

    if (overlaysRef.current.length) map.remove(overlaysRef.current)
    const overlays: any[] = []
    for (const place of places) overlays.push(createPlaceMarker(AMap, place))
    for (const zone of zones) overlays.push(...createZoneOverlays(AMap, map, infoWindow, zone, (item) => zoneHandlerRef.current(item)))
    for (const agent of agents.slice(0, 80)) {
      overlays.push(createAgentMarker(AMap, map, infoWindow, agent, (item) => agentHandlerRef.current(item)))
    }
    for (const event of events) {
      const marker = createEventMarker(AMap, map, infoWindow, event, agents, zones)
      if (marker) overlays.push(marker)
    }
    if (selectedAgent) {
      if (trackMode === 'history') {
        const track = createHistoricalTrack(AMap, selectedAgent)
        if (track) overlays.push(track)
      } else {
        overlays.push(...createPredictedTrack(AMap, selectedAgent))
      }
      if (simulationResult) overlays.push(...createSimulationOverlays(AMap, selectedAgent, zones[0], simulationResult))
    }
    overlaysRef.current = overlays
    if (overlays.length) map.add(overlays)

    return () => {
      if (mapRef.current && overlays.length) mapRef.current.remove(overlays)
      if (overlaysRef.current === overlays) overlaysRef.current = []
    }
  }, [agents, places, zones, events, selectedAgent, trackMode, simulationResult, mapStatus])

  return (
    <section className="map-shell" aria-label="城市空间态势地图">
      <div ref={containerRef} className={`amap-container ${mapStatus === 'fallback' ? 'is-hidden' : ''}`} />
      {mapStatus === 'loading' ? <div className="map-loading">正在连接高德地图 JS API 2.0…</div> : null}
      {mapStatus === 'fallback' ? (
        <div className="fallback-map">
          <div className="fallback-grid" />
          <div className="fallback-river" />
          <div className="fallback-road road-a" />
          <div className="fallback-road road-b" />
          {zones.map((zone) => (
            <button
              type="button"
              key={zone.id}
              className="fallback-zone"
              style={projectToPercent(zone.center)}
              onClick={() => onSelectZone(zone)}
              aria-label={`查看${zone.name}`}
            >
              <span>{DEMO_MAP_CONFIG.schoolZoneDisplayId}</span>
            </button>
          ))}
          {agents.slice(0, 80).map((agent) => <AgentMarker key={agent.id} agent={agent} onSelect={onSelectAgent} />)}
          {selectedAgent && fallbackSimulationEndpoint ? (
            <>
              <svg className="fallback-simulation-path" aria-label="模拟推演路径">
                <line
                  x1={projectToPercent(selectedAgent.position).left}
                  y1={projectToPercent(selectedAgent.position).top}
                  x2={projectToPercent(fallbackSimulationEndpoint).left}
                  y2={projectToPercent(fallbackSimulationEndpoint).top}
                />
              </svg>
              <span className="fallback-simulation-marker" style={projectToPercent(fallbackSimulationEndpoint)}>SIM</span>
            </>
          ) : null}
          {events.slice(-8).map((event) => (
            <span key={event.id} className={`fallback-event event-${event.type}`} style={fallbackEventPosition(event, agents, zones)} title={`${event.type} · ${event.source}`}>!</span>
          ))}
          <div className="fallback-note">
            <b>高德地图当前不可用，已切换到 Demo 降级空间视图。</b>
            <span>{fallbackReason}</span>
          </div>
        </div>
      ) : null}

      {simulationResult ? (
        <aside className="map-simulation-card" aria-label="模拟推演地图图层">
          <div><b>模拟推演结果 / Simulation</b><span>{simulationResult.strategy.toUpperCase()}</span></div>
          <strong>{simulationResult.before.risk.toFixed(0)} <i>→</i> {simulationResult.after.risk.toFixed(0)}</strong>
          <button type="button" onClick={onCloseSimulation}>退出推演图层</button>
        </aside>
      ) : null}

      <div className="map-topbar">
        <span className={`status-dot ${mapStatus}`} />
        {mapStatus === 'ready' ? `${DEMO_MAP_CONFIG.city} · 高德地图在线` : mapStatus === 'fallback' ? 'Demo 降级空间视图' : '地图加载中'}
        <span>{agents.length} 个模拟主体</span>
        <strong>广州演示场景 · Synthetic Data</strong>
      </div>
      <div className="map-legend">
        <span><i className="legend-dot high" />高风险</span>
        <span><i className="legend-dot medium" />中风险</span>
        <span><i className="legend-dot low" />低风险</span>
        <span><i className="legend-line history" />历史轨迹</span>
        <span><i className="legend-line predicted" />模拟预测</span>
        <span><i className="legend-line simulation" />Simulation</span>
      </div>
    </section>
  )
}
