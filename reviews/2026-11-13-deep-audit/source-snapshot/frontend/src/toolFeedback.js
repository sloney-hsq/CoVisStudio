export function toolFeedback(result) {
  if (result.status === 'failed' || result.status === 'error') return { tone: 'failed', title: 'Change not applied', detail: result.message }
  if (result.status === 'no_changes') return { tone: 'neutral', title: 'No chart changes', detail: 'This reply did not update the charts.' }
  if (result.status === 'awaiting_confirmation') return { tone: 'pending', title: 'Your confirmation is needed', detail: 'The current charts are unchanged.' }
  if (result.committed || result.status === 'committed') return { tone: 'committed', title: result.summary || 'Charts updated', detail: `${result.view_numbers?.length ? `Charts ${result.view_numbers.join(', ')} · ` : ''}${result.displayed ? 'Displayed' : 'Committed'} · v${result.revision}` }
  if (result.tool === 'preview_revision') return { tone: 'pending', title: 'Revision ready to review', detail: 'This preview has not changed the charts.' }
  if (result.tool === 'save_category_set') return { tone: 'saved', title: 'Comparison set saved', detail: 'Reuse these categories with the current analysis conditions.' }
  return null
}

export function recordReceipt(receipts, event) {
  if (!toolFeedback(event) || !event.request_id) return
  const previous = receipts[event.request_id]
  receipts[event.request_id] = { ...event, displayed: previous?.revision === event.revision && previous.displayed }
}

export function markReceiptDisplayed(receipts, revision) {
  for (const receipt of Object.values(receipts)) {
    if (receipt.revision === revision && (receipt.committed || receipt.status === 'committed')) receipt.displayed = true
  }
}
