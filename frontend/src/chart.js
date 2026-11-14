export const metricNames = { orders: 'Orders', revenue: 'Revenue', low_review_rate: 'Low-review rate', avg_delivery_days: 'Average delivery time' }
export function humanize(value) { return String(value).replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) }
export function formatRange(start, end) {
  const first = new Date(`${start}T00:00:00Z`), until = new Date(`${end}T00:00:00Z`)
  const last = new Date(until.getTime() - 86400000)
  const month = date => date.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })
  if (first.getUTCDate() === 1 && until.getUTCDate() === 1 && first.getUTCFullYear() === last.getUTCFullYear()) {
    return `${month(first)}${month(first) === month(last) ? '' : `–${month(last)}`} ${first.getUTCFullYear()}`
  }
  const date = value => value.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
  return `${date(first)} – ${date(last)}`
}
export function formatValue(value, metric, compact = false) {
  if (value === null || value === undefined) return 'No data'
  if (metric === 'low_review_rate') return `${(value * 100).toFixed(1)}%`
  if (metric === 'avg_delivery_days') return `${value.toFixed(1)} d`
  const opts = compact ? { notation: 'compact', maximumFractionDigits: 1 } : { maximumFractionDigits: metric === 'revenue' ? 2 : 0 }
  return `${metric === 'revenue' ? 'R$ ' : ''}${new Intl.NumberFormat('en-US', opts).format(value)}`
}
export function sortedRows(view) {
  const rows = [...view.data.rows]
  if (view.style.sort === 'ascending') rows.sort((a, b) => (a.value ?? Infinity) - (b.value ?? Infinity))
  if (view.style.sort === 'descending') rows.sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity))
  return rows
}
export function chartOption(view, selected = []) {
  const rows = sortedRows(view), metric = view.source.metric, color = view.style.color
  const labels = rows.map(r => humanize(r.label))
  const colors = [color, '#95c4bc', '#c6dcd5', '#aab7c7', '#d8bc8c', '#e2d7c5']
  const font = 'Inter, Segoe UI, sans-serif'
  const viewport = typeof window === 'undefined' ? 1920 : window.innerWidth
  const fontSize = viewport >= 3300 ? 18 : viewport >= 2300 ? 15 : 13
  const opacity = label => selected.length && !selected.includes(label) ? 0.32 : 1
  const data = rows.map(r => ({ value: r.value, name: humanize(r.label), rawLabel: r.label, itemStyle: { opacity: opacity(r.label) } }))
  const axisLabel = { color: '#66747d', fontFamily: font, fontSize, margin: 12 }
  const numberLabel = val => formatValue(val, metric, true)
  const option = {
    animation: false, backgroundColor: '#ffffff', color: colors,
    textStyle: { fontFamily: font, fontSize, color: '#203b48' },
    tooltip: { trigger: 'item', confine: true, backgroundColor: '#183541', borderWidth: 0, padding: 14, textStyle: { color: '#ffffff', fontSize: 13 },
      formatter: params => {
        const row = rows[params.dataIndex]
        const value = formatValue(row.value, metric)
        const denominator = metric === 'low_review_rate' ? `<br/><span style="opacity:.7">${row.low_review_count} low reviews / ${row.reviewed_orders} reviewed orders</span>` : ''
        return `${humanize(row.label)}<br/><b>${value}</b>${denominator}`
      }
    },
    grid: { top: 26, right: 26, bottom: 42, left: 16, containLabel: true }
  }
  if (view.chart_type === 'pie') return { ...option, legend: { bottom: 0, type: 'scroll', textStyle: { color: '#66747d' } }, series: [{ type: 'pie', radius: ['45%', '72%'], center: ['50%', '45%'], data, itemStyle: { borderColor: '#fff', borderWidth: 4, borderRadius: 5 }, label: { show: view.style.show_labels, formatter: p => numberLabel(p.value) }, emphasis: { scale: false } }] }
  if (view.chart_type === 'scatter') return { ...option,
    xAxis: { type: 'value', name: 'Orders', nameLocation: 'middle', nameGap: 30, axisLabel, splitLine: { lineStyle: { color: '#eef2f1' } } },
    yAxis: { type: 'value', axisLabel: { ...axisLabel, formatter: numberLabel }, splitLine: { lineStyle: { color: '#eef2f1' } } },
    series: [{ type: 'scatter', symbolSize: 18, data: rows.map(r => ({ value: [r.orders, r.value], name: humanize(r.label), rawLabel: r.label, itemStyle: { opacity: opacity(r.label) } })), label: { show: view.style.show_labels, position: 'top', formatter: p => p.name } }]
  }
  if (view.chart_type === 'heatmap') return { ...option,
    grid: { top: 60, left: 10, right: 10, bottom: 100, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { ...axisLabel, width: 110, overflow: 'break', interval: 0 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'category', data: [metricNames[metric]], show: false },
    visualMap: { min: 0, max: Math.max(...rows.map(r => r.value || 0)), orient: 'horizontal', left: 'center', bottom: 5, calculable: false, inRange: { color: ['#e4f0eb', color] }, formatter: numberLabel },
    series: [{ type: 'heatmap', data: rows.map((r, i) => ({ value: [i, 0, r.value], rawLabel: r.label, itemStyle: { opacity: opacity(r.label), borderColor: '#fff', borderWidth: 5 } })), label: { show: true, formatter: p => formatValue(p.value[2], metric), color: '#183541' } }]
  }
  const horizontal = view.chart_type === 'bar' && view.source.dimension !== 'month'
  const categoryAxis = { type: 'category', data: labels, axisLabel: { ...axisLabel, width: horizontal ? Math.round(fontSize * 9) : Math.round(fontSize * 7), overflow: 'break', lineHeight: fontSize * 1.25, interval: 0 }, axisLine: { show: false }, axisTick: { show: false } }
  const valueAxis = { type: 'value', axisLabel: { ...axisLabel, formatter: numberLabel }, splitNumber: 4, splitLine: { lineStyle: { color: '#edf1ef', type: 'dashed' } }, axisLine: { show: false }, axisTick: { show: false } }
  if (horizontal) categoryAxis.inverse = true
  return { ...option,
    xAxis: horizontal ? valueAxis : categoryAxis,
    yAxis: horizontal ? categoryAxis : valueAxis,
    series: [{ type: view.chart_type === 'bar' ? 'bar' : 'line', data, barMaxWidth: 36, symbol: 'circle', symbolSize: 7,
      lineStyle: { width: 3 }, itemStyle: { borderRadius: horizontal ? [0, 5, 5, 0] : [5, 5, 0, 0] },
      areaStyle: view.chart_type === 'area' ? { opacity: 0.13 } : undefined,
      label: { show: view.style.show_labels, position: horizontal ? 'right' : 'top', color: '#36535d', formatter: p => numberLabel(p.value), fontSize: 12 }
    }]
  }
}
