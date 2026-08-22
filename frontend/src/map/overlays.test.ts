import { describe, expect, it, vi } from 'vitest'
import { createEventMarker, offsetOverlappingEventPositions } from './overlays'
import type { Agent, WorldEvent } from '../types'

const agent: Agent = {
  id: 'agent_A', type: 'Person', synthetic: true, display_name: '模拟人员001', risk_level: 'high',
  position: { lng: 113.2644, lat: 23.1291 }, destination: null, behavior_state: 'moving',
  risk_score: 75, active_zone_ids: [], history: [], social_group: 'group_0',
}

function event(id: string, type: string): WorldEvent {
  return {
    id, type, subject_id: 'agent_A', object_id: null, timestamp: '2026-08-18T12:00:00Z',
    confidence: type === 'CrowdDetected' ? 0.91 : 0.89, source: 'mock_cv', metadata: {},
  }
}

class MockMarker {
  extData: WorldEvent | null = null
  handlers: Record<string, () => void> = {}

  constructor(public options: Record<string, unknown>) {}
  setExtData(value: WorldEvent) { this.extData = value }
  getExtData() { return this.extData }
  getPosition() { return this.options.position }
  on(name: string, handler: () => void) { this.handlers[name] = handler }
  click() { this.handlers.click?.() }
}

const AMap = {
  Marker: MockMarker,
  Pixel: class MockPixel { constructor(public x: number, public y: number) {} },
}

describe('overlapping AMap event markers', () => {
  it('assigns unique deterministic render offsets without changing event coordinates', () => {
    const crowd = event('event_crowd', 'CrowdDetected')
    const risk = event('event_risk', 'RiskObjectDetected')
    const original = { ...agent.position }

    const layouts = offsetOverlappingEventPositions([crowd, risk], [agent], [])

    expect(layouts.map((item) => item.event.id)).toEqual(['event_crowd', 'event_risk'])
    expect(new Set(layouts.map((item) => `${item.offset.x},${item.offset.y}`)).size).toBe(2)
    expect(agent.position).toEqual(original)
  })

  it('binds each marker to its own extData and opens the matching event content', () => {
    const crowd = event('event_crowd', 'CrowdDetected')
    const risk = event('event_risk', 'RiskObjectDetected')
    const layouts = offsetOverlappingEventPositions([crowd, risk], [agent], [])
    const infoWindow = { setContent: vi.fn(), open: vi.fn() }
    const map = {}
    const markers = layouts.map(({ event: item, offset }) =>
      createEventMarker(AMap, map, infoWindow, item, [agent], [], offset) as MockMarker,
    )

    expect(markers[0].getExtData()).toBe(crowd)
    expect(markers[1].getExtData()).toBe(risk)

    markers[0].click()
    expect(infoWindow.setContent).toHaveBeenLastCalledWith(expect.stringContaining('感知人流聚集'))
    expect(infoWindow.setContent).not.toHaveBeenLastCalledWith(expect.stringContaining('检测到风险物品'))

    markers[1].click()
    expect(infoWindow.setContent).toHaveBeenLastCalledWith(expect.stringContaining('检测到风险物品'))
  })
})
