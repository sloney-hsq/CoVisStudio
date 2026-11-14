// These are views of recorded evidence, not inferred judgments of user behavior.
export function measuredEvents(events) {
  const start = events.find(event => event.name === 'trial_started')
  if (!start) return []
  const end = events.find(event => event.name === 'trial_finished')
  return events.filter(event => event.index >= start.index && (!end || event.index <= end.index))
}

export function eventText(event) {
  if (event.event?.text) return event.event.text
  if (event.text) return event.text
  if (event.tool) return event.tool.replaceAll('_', ' ')
  if (event.reason) return event.reason
  if (event.file) return event.file
  if (event.revision !== undefined) return `Canvas version ${event.revision}`
  if (event.details?.revision !== undefined) return `Canvas version ${event.details.revision}`
  return ''
}

export function nodeAtEvent(nodes, event) {
  if (['tool_committed', 'undo', 'restore'].includes(event.name)) {
    return nodes.find(node => node.revision === event.revision) || null
  }
  return nodes.filter(node => node.event_index <= event.index).at(-1) || null
}

export function relativeEventTime(event, events) {
  const start = events.find(item => item.name === 'trial_started')
  if (!start) return 'Before task'
  const seconds = (event.server_ms - start.server_ms) / 1000
  return `${seconds >= 0 ? '+' : ''}${seconds.toFixed(1)} s`
}
