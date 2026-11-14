export function referenceKey(reference) {
  return JSON.stringify([reference.revision, reference.view_ids, reference.entities])
}

export function visualContextLabel(reference, receipt, viewCount) {
  if (!viewCount) return 'No chart image yet'
  if (!receipt || referenceKey(receipt.reference) !== referenceKey(reference)) return `Preparing canvas v${reference.revision}`
  const labels = { empty: 'No frame delivered', captured: 'Captured locally', queued: 'Waiting for audio', sent: 'Frame sent to model' }
  return `${labels[receipt.status]} · v${reference.revision}`
}
