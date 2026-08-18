import { useEffect, useRef } from 'react'

export function RiskChart({ values }: { values: number[] }) {
  const chartRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let chart: { setOption: (option: unknown) => void; resize: () => void; dispose: () => void } | undefined
    let cancelled = false
    async function renderChart() {
      const { echarts } = await import('../charts/riskChartEngine')
      if (cancelled || !chartRef.current) return
      chart = echarts.init(chartRef.current)
      const data = values.length ? values : [0]
      chart.setOption({
        grid: { left: 8, right: 8, top: 24, bottom: 12, containLabel: true },
        xAxis: { type: 'category', data: data.map((_, index) => index + 1), show: false },
        yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#738384', fontSize: 10 }, splitLine: { lineStyle: { color: '#213133' } } },
        tooltip: { trigger: 'axis' },
        series: [{ type: 'line', data, smooth: 0.28, symbolSize: 7, lineStyle: { width: 3, color: '#f3b562' }, itemStyle: { color: '#ffd384' }, areaStyle: { color: 'rgba(243,181,98,.12)' } }],
      })
    }
    void renderChart()
    const onResize = () => chart?.resize()
    window.addEventListener('resize', onResize)
    return () => {
      cancelled = true
      window.removeEventListener('resize', onResize)
      chart?.dispose()
    }
  }, [values])
  return <div ref={chartRef} className="risk-chart" aria-label="风险变化曲线" />
}
