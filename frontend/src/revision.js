// Build an explicit user-authored patch. Empty controls preserve each target's source.
export function revisionPayload(form, evidence, condition) {
  const source_patch = { ...form.extra_patch }
  for (const field of ['metric', 'dimension', 'region', 'start', 'end', 'status']) {
    if (form[field] !== '') source_patch[field] = form[field] === '__all__' ? null : form[field]
  }
  if (form.member_action === 'rerank') {
    source_patch.categories = null
    source_patch.top_n = Number(form.top_n)
    source_patch.rank_by = form.rank_by
  }
  const origin = form.member_action === 'use_evidence' && form.candidate_id
    ? { candidate_id: form.candidate_id }
    : { evidence: evidence ? { revision: evidence.revision, view_id: evidence.view_id, members: [...evidence.members] } : null }
  return {
    ...origin,
    view_ids: [...form.view_ids], source_patch, member_action: form.member_action,
  }
}

export function revisionDefaults(viewIds, hasEvidence) {
  return { view_ids: [...viewIds], region: '', metric: '', dimension: '', start: '', end: '', status: '',
    member_action: hasEvidence ? 'use_evidence' : 'keep_current', categories: [], top_n: 3, rank_by: 'orders', candidate_id: '', extra_patch: {} }
}

// Reopen the actual proposal, not the unrelated current chart selection.
export function revisionSeed(proposal, authoredPayload = null) {
  const card = proposal.card
  const originalPatch = authoredPayload?.source_patch || card.source_patch
  const source_patch = originalPatch ? { ...originalPatch } : {}
  if (!originalPatch) {
    for (const change of card.changes) for (const field of change.changed_fields) source_patch[field] = change.after_source[field]
    if (card.member_action === 'use_evidence') { delete source_patch.categories; delete source_patch.top_n }
    if (card.member_action === 'rerank') {
      source_patch.top_n = card.changes[0].after_source.top_n
      source_patch.rank_by = card.changes[0].after_source.rank_by
    }
  }
  const explicitCategories = source_patch.categories
  if (card.member_action === 'use_evidence' && card.evidence) { delete source_patch.categories; delete source_patch.top_n }
  const form = revisionDefaults(card.view_ids, !!card.evidence)
  form.member_action = card.member_action
  form.candidate_id = authoredPayload?.candidate_id || card.candidate_id || ''
  for (const field of ['metric', 'dimension', 'region', 'start', 'end', 'status']) {
    if (field in source_patch) { form[field] = source_patch[field] === null ? '__all__' : source_patch[field]; delete source_patch[field] }
  }
  if (form.member_action === 'rerank') {
    form.top_n = source_patch.top_n; form.rank_by = source_patch.rank_by
    delete source_patch.categories; delete source_patch.top_n; delete source_patch.rank_by
  }
  form.categories = [...(explicitCategories || source_patch.categories || card.evidence?.members || [])]
  form.extra_patch = source_patch
  return { form, evidence: card.evidence ? JSON.parse(JSON.stringify(card.evidence)) : null, proposal_id: proposal.id }
}
