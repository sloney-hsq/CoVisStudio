export const understandingLabels = {
  object_origin: 'Object origin', target_views: 'Target charts',
  calculation_scope: 'Calculation scope', kept_released: 'Retained and released conditions',
}

export function episodeBoundariesValid(events, boundary) {
  const byIndex = new Map(events.map(event => [event.index, event]))
  const onset = byIndex.get(boundary.onset_index)
  const terminal = events.find(event => event.name === 'trial_finished')
  return Boolean(terminal && onset && ['speech_start', 'user_input', 'request_accepted', 'manual_edit_requested'].includes(onset.name)
    && byIndex.has(boundary.utterance_end_index) && byIndex.has(boundary.end_event_index)
    && boundary.onset_index <= boundary.utterance_end_index
    && boundary.utterance_end_index <= boundary.end_event_index
    && boundary.end_event_index <= terminal.index)
}

export function episodeControls(episode, episodes, terminalIndex) {
  return {
    designate: Boolean(episode?.locked && !episode.scored && episode.end_event_index === terminalIndex
      && !episodes.some(item => item.primary)),
    score: Boolean(episode?.locked && episode.primary && !episode.scored),
  }
}

export function blankCodingFiles(packetId) {
  const intent = () => ({ status: 'unknown', disposition: 'revise', target_view_ids: [], source_patch: {},
    members: { mode: 'keep_current' }, source_requirement: { mode: 'none', candidate_id: null, reason: '' },
    retained_fields: [], released_fields: [], view_overrides: {}, reference_interval: 'unknown',
    reason: '', evidence_indices: [] })
  const coder = () => ({ schema: 'covis-intent-episode-1', packet_id: packetId, reviewer_id: '',
    status: 'pending', intent: intent(), speech_verification: 'pending' })
  return { coder_a: coder(), coder_b: coder(), adjudication: { reviewer_id: '', reason: '', intent: intent() } }
}

export function outcomeLabel(value) {
  return value === true ? 'Correct' : value === false ? 'Incorrect' : 'Unknown / pending'
}
