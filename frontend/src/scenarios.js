// Display helpers for the researcher scenario panel.
export function timingLabel(timing) {
  if (!timing || timing.type === 'after_end') return 'after reply'
  const label = { barge_in: 'barge-in', backchannel: 'backchannel', during_tool: 'during tool' }[timing.type] || timing.type
  return timing.offset_s === undefined || timing.offset_s === null ? label : `${label} +${timing.offset_s}s`
}

const CAUSES = {
  asr: 'Speech recognition', segmentation_timing: 'Segmentation / timing',
  contract_execution: 'Tool contract', decision: 'Decision', unknown: 'Unknown',
}
export function causeLabel(cause) {
  return cause === null || cause === undefined ? 'Correct' : CAUSES[cause] || cause
}

export function viewSummary(views) {
  if (!views) return '—'
  return Object.entries(views).map(([id, result]) =>
    result.status === 'match' ? `${id} ✓` : result.status === 'unknown' ? `${id} ?` : `${id} ✗ ${result.fields.join(', ')}`).join(' · ')
}
