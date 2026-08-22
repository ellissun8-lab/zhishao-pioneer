import { useMemo, useState } from 'react'
import { eventTypeLabel, sourceLabel } from '../labels'
import type { WorldEvent } from '../types'

type EventFilter = 'all' | 'risk' | 'sensing'

const filterLabels: Record<EventFilter, string> = { all: '全部', risk: '风险', sensing: '感知' }

function matchesFilter(event: WorldEvent, filter: EventFilter) {
  if (filter === 'all') return true
  if (filter === 'risk') return ['RiskObjectDetected', 'AlertTriggered', 'InterventionApplied'].includes(event.type)
  return ['PersonDetected', 'VehicleDetected', 'CrowdDetected', 'CrowdGathered', 'CrowdDispersed', 'ZoneEntered', 'ZoneExited', 'MoveStarted', 'MoveStopped'].includes(event.type)
}

export function EventTimeline({ events, onSelect }: { events: WorldEvent[]; onSelect?: (event: WorldEvent) => void }) {
  const [filter, setFilter] = useState<EventFilter>('all')
  const visibleEvents = useMemo(() => events.filter((event) => matchesFilter(event, filter)), [events, filter])
  return (
    <section className="timeline panel">
      <div className="panel-heading"><span>事件时间轴</span><div className="timeline-controls">{(Object.keys(filterLabels) as EventFilter[]).map((item) => <button type="button" key={item} className={filter === item ? 'active' : ''} aria-pressed={filter === item} onClick={() => setFilter(item)}>{filterLabels[item]}</button>)}</div><em>事件总线</em></div>
      <div className="timeline-list">
        {visibleEvents.length === 0 ? <p className="empty-hint">{events.length === 0 ? '等待模拟事件输入…' : '当前筛选条件下暂无事件'}</p> : visibleEvents.map((event, index) => (
            <article key={event.id} className={event.type === 'RiskObjectDetected' ? 'is-critical' : ''}>
            <time>{new Date(event.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</time>
            <i />
            {onSelect ? <button type="button" className="timeline-event-button" onClick={() => onSelect(event)}><b>{eventTypeLabel(event.type)}</b><span>{event.subject_id || '系统'} · {sourceLabel(event.source)} · {(event.confidence * 100).toFixed(0)}%</span></button> : <div><b>{eventTypeLabel(event.type)}</b><span>{event.subject_id || '系统'} · {sourceLabel(event.source)} · {(event.confidence * 100).toFixed(0)}%</span></div>}
            <small>#{index + 1}</small>
          </article>
        ))}
      </div>
    </section>
  )
}

