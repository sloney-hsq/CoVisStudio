import { humanize, metricNames, formatRange } from './chart.js'

export const sourceLabels = { metric: 'Measure', dimension: 'Group by', region: 'Region', start: 'From', end: 'Until (exclusive)', status: 'Order status', categories: 'Comparison set', top_n: 'Ranking size', rank_by: 'Ranking measure' }

export function sourceValue(source, field) {
  const value = source[field]
  if (value === undefined) return 'Not specified'
  if (field === 'region' && value === null) return 'All regions'
  if (field === 'categories') return value === null ? 'No fixed set' : value.length ? value.map(humanize).join(', ') : 'Empty set'
  if (field === 'top_n') return value === null ? 'No top-N limit' : `Top ${value}`
  if (field === 'metric' || field === 'rank_by') return metricNames[value] || humanize(String(value))
  if (field === 'start' || field === 'end') return value === null ? 'Not specified' : value
  return value === null ? 'None' : humanize(String(value))
}

export function keptConditions(change) {
  const source = change.after_source, fields = change.kept_fields
  return fields.flatMap(field => {
    if (field === 'end' && fields.includes('start')) return []
    if (field === 'start' && fields.includes('end')) return [{ field: 'period', label: 'Period', value: formatRange(source.start, source.end) }]
    return [{ field, label: sourceLabels[field] || humanize(field), value: sourceValue(source, field) }]
  })
}

export function computationScope(source) {
  return `${source.region || 'All regions'} · ${formatRange(source.start, source.end)} · ${sourceValue(source, 'metric')} · ${sourceValue(source, 'status')}`
}

export function membershipRule(source) {
  if (source.categories !== null && source.categories !== undefined) return `Fixed categories (${source.categories.length}): ${source.categories.map(humanize).join(', ')}`
  if (source.top_n) return `Dynamic top ${source.top_n} by ${sourceValue(source, 'rank_by')} · recalculated in this scope`
  return 'All matching groups · no fixed category set or top-N limit'
}

export function untouchedNumbers(card) {
  // The proposal's snapshot, never a later canvas with different charts.
  return card.untouched_views?.map(view => view.number) || []
}

export function provenanceNotice(card) {
  const provenance = card.execution_provenance
  if (!provenance?.selected_source_at_onset) return ''
  const selected = provenance.selected_source_at_onset
  const used = provenance.executed_source
  if (!used) return `Selected, not used for this edit: ${selected.label}.`
  if (provenance.overrides_selection || provenance.members_equal === false) {
    return `Selected ${selected.label}; used ${used.label}. ${provenance.members_equal ? 'Same categories; different source.' : 'Different category selection.'}`
  }
  return ''
}
