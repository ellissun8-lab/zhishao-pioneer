import type { WorldEvent } from '../types'

const eventNames: Record<string, string> = {
  MoveStarted: '开始移动', MoveStopped: '停止移动', ZoneEntered: '进入敏感区域', ZoneExited: '离开敏感区域',
  CrowdDetected: '感知人流聚集', CrowdGathered: '确认形成聚集', CrowdDispersed: '聚集解除',
  PersonDetected: '检测到人员', VehicleDetected: '检测到车辆',
  RiskObjectDetected: '检测到风险物品', AlertTriggered: '触发预警', InterventionApplied: '应用干预',
}

export function EventTimeline({ events }: { events: WorldEvent[] }) {
  return (
    <section className="timeline panel">
      <div className="panel-heading"><span>事件时间轴</span><em>Event Bus</em></div>
      <div className="timeline-list">
        {events.length === 0 ? <p className="empty-hint">等待模拟事件输入…</p> : events.map((event, index) => (
          <article key={event.id} className={event.type === 'RiskObjectDetected' ? 'is-critical' : ''}>
            <time>{new Date(event.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</time>
            <i />
            <div><b>{eventNames[event.type] || event.type}</b><span>{event.subject_id || '系统'} · {event.source} · {(event.confidence * 100).toFixed(0)}%</span></div>
            <small>#{index + 1}</small>
          </article>
        ))}
      </div>
    </section>
  )
}

