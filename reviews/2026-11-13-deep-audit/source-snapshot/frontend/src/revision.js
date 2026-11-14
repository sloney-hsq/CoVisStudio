// Build an explicit user-authored patch. Empty controls preserve each target's source.
export function revisionPayload(form, evidence, condition) {
  const source_patch = {}
  for (const field of ['metric', 'region', 'start', 'end', 'status']) {
    if (form[field] !== '') source_patch[field] = form[field] === '__all__' ? null : form[field]
  }
  if (form.member_action === 'rerank') {
    source_patch.categories = null
    source_patch.top_n = Number(form.top_n)
    source_patch.rank_by = form.rank_by
  }
  if (form.member_action === 'use_evidence' && condition === 'unbound_preview') {
    source_patch.categories = [...form.categories]
    source_patch.top_n = null
  }
  return {
    evidence: evidence ? { revision: evidence.revision, view_id: evidence.view_id, members: [...evidence.members] } : null,
    view_ids: [...form.view_ids], source_patch, member_action: form.member_action,
  }
}

export function revisionDefaults(viewIds, hasEvidence) {
  return { view_ids: [...viewIds], region: '', metric: '', start: '', end: '', status: '',
    member_action: hasEvidence ? 'use_evidence' : 'keep_current', categories: [], top_n: 3, rank_by: 'orders' }
}
