export function toolFeedback(result) {
  if (result.committed || result.status === 'committed') {
    const detail = `${result.view_numbers?.length ? `Charts ${result.view_numbers.join(', ')} · ` : ''}${result.displayed ? 'Displayed' : 'Committed'} · v${result.revision}`
    if (result.status === 'failed' || result.status === 'error') return { tone: 'failed', title: 'Earlier changes kept · later action failed', detail: `${detail}. ${result.message || 'The later change was not applied.'}` }
    if (result.status === 'awaiting_confirmation') return { tone: 'pending', title: 'Earlier changes kept · confirmation needed', detail: `${detail}. The next proposed change is not applied.` }
    return { tone: 'committed', title: result.summary || 'Charts updated', detail }
  }
  if (result.status === 'failed' || result.status === 'error') return { tone: 'failed', title: 'Change not applied', detail: result.message }
  if (result.status === 'no_changes') return { tone: 'neutral', title: 'No chart changes', detail: 'This reply did not update the charts.' }
  if (result.status === 'awaiting_confirmation') return { tone: 'pending', title: 'Your confirmation is needed', detail: 'The current charts are unchanged.' }
  if (result.tool === 'preview_revision') return { tone: 'pending', title: 'Revision ready to review', detail: 'This preview has not changed the charts.' }
  if (result.tool === 'save_category_set') return { tone: 'saved', title: 'Comparison set saved', detail: 'Reuse these categories with the current analysis conditions.' }
  return null
}

export function recordReceipt(receipts, event) {
  if (!toolFeedback(event) || !event.request_id) return
  const previous = receipts[event.request_id]
  const priorCommit = previous?.committed || previous?.status === 'committed'
  const committed = event.committed || event.status === 'committed' || priorCommit
  const revision = event.committed || event.status === 'committed' ? event.revision : priorCommit ? previous.revision : event.revision
  receipts[event.request_id] = { ...event, committed: !!committed, revision,
    view_numbers: committed && !event.view_numbers?.length ? previous?.view_numbers : event.view_numbers,
    displayed: committed && previous?.revision === revision && previous.displayed }
}

export function markReceiptDisplayed(receipts, revision) {
  for (const receipt of Object.values(receipts)) {
    if (receipt.revision === revision && (receipt.committed || receipt.status === 'committed')) receipt.displayed = true
  }
}
