import test from 'node:test'
import assert from 'node:assert/strict'
import { chartOption, formatValue, sortedRows, formatRange } from '../src/chart.js'
const view = { chart_type: 'bar', source: { metric: 'low_review_rate', dimension: 'category' }, style: { color: '#238579', show_labels: true, sort: 'source' }, data: { rows: [{ label: 'category_a', value: .12, orders: 300, low_review_count: 30, reviewed_orders: 250 }, { label: 'category_b', value: .08, orders: 200, low_review_count: 12, reviewed_orders: 150 }] } }
test('rates use percentages and preserve actual review denominators in tooltips', () => {
  const option = chartOption(view)
  assert.equal(formatValue(.12, 'low_review_rate'), '12.0%')
  assert.match(option.tooltip.formatter({ dataIndex: 0 }), /30 low reviews \/ 250 reviewed orders/)
  assert.equal(option.series[0].data[0].rawLabel, 'category_a')
})
test('display sorting does not mutate source query rows', () => {
  const edited = { ...view, style: { ...view.style, sort: 'ascending' } }
  assert.equal(sortedRows(edited)[0].label, 'category_b')
  assert.equal(view.data.rows[0].label, 'category_a')
})
test('all supported renderers preserve data identities', () => {
  for (const chart_type of ['bar', 'line', 'area', 'pie', 'scatter', 'heatmap']) {
    const option = chartOption({ ...view, chart_type }, ['category_b'])
    assert.equal(option.series[0].data[0].rawLabel, 'category_a')
    assert.equal(option.series[0].data[0].itemStyle.opacity, .32)
  }
})
test('visible date range respects exclusive end and does not imply extra month', () => {
  assert.equal(formatRange('2017-01-01', '2018-01-01'), 'Jan–Dec 2017')
  assert.equal(formatRange('2017-01-01', '2017-04-01'), 'Jan–Mar 2017')
  assert.equal(formatRange('2017-02-01', '2017-03-01'), 'Feb 2017')
})
