export const DEMO_MAP_CONFIG = {
  city: '广州市',
  center: [113.2644, 23.1291] as [number, number],
  // 使用整数缩放避免栅格瓦片被二次缩放造成发虚；深蓝主题提高道路与标注的对比度。
  zoom: 14,
  mapStyle: 'amap://styles/darkblue',
  viewMode: '2D' as const,
  schoolZoneDisplayId: 'school_zone_001',
}

export const AMAP_LOAD_TIMEOUT_MS = 10_000
