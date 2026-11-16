import test from 'node:test'
import assert from 'node:assert/strict'
import { revisionDefaults, revisionPayload, revisionSeed } from '../src/revision.js'

const evidence = { revision: 3, view_id: 'v1', members: ['category_a', 'category_b'],
  source: { region: 'SP', start: '2017-01-01', end: '2018-01-01', metric: 'orders' } }

test('referencing a historical cohort never copies its region, dates or metric into the current patch', () => {
  const form = revisionDefaults(['v2', 'v3'], true)
  const payload = revisionPayload(form, evidence, 'bound_revision')
  assert.deepEqual(payload.source_patch, {})
  assert.deepEqual(payload.evidence, { revision: 3, view_id: 'v1', members: ['category_a', 'category_b'] })
  assert.deepEqual(payload.view_ids, ['v2', 'v3'])
  assert.equal(payload.member_action, 'use_evidence')
})

test('an explicit local metric revision preserves all unspecified source fields', () => {
  const form = revisionDefaults(['v2'], true)
  form.metric = 'low_review_rate'
  assert.deepEqual(revisionPayload(form, evidence, 'bound_revision').source_patch, { metric: 'low_review_rate' })
})

test('reranking explicitly releases fixed members without restoring historical filters', () => {
  const form = revisionDefaults(['v1', 'v2', 'v3'], true)
  Object.assign(form, { member_action: 'rerank', top_n: 3, rank_by: 'orders', region: 'MG' })
  assert.deepEqual(revisionPayload(form, evidence, 'bound_revision').source_patch,
    { region: 'MG', categories: null, top_n: 3, rank_by: 'orders' })
})

test('correcting one field preserves the authored candidate, target group and original source patch', () => {
  const payload = { candidate_id: 'set:prior', view_ids: ['v2', 'v3'], member_action: 'use_evidence', source_patch: { metric: 'revenue', region: 'MG', end: '2017-07-01' } }
  const proposal = { id: 'p1', card: { candidate_id: 'set:prior', evidence, view_ids: ['v2', 'v3'], member_action: 'use_evidence', changes: [] } }
  const seed = revisionSeed(proposal, payload)
  seed.form.end = '2017-04-01'
  assert.deepEqual(revisionPayload(seed.form, seed.evidence, 'bound_revision'), { ...payload, source_patch: { metric: 'revenue', region: 'MG', end: '2017-04-01' } })
  assert.equal(payload.source_patch.end, '2017-07-01')
})

test('model proposals reconstruct their actual edit without copying historical scope', () => {
  const before = { metric: 'orders', region: 'MG', start: '2017-01-01', end: '2018-01-01', categories: null, top_n: 3, rank_by: 'orders' }
  const after = { ...before, end: '2017-04-01', categories: evidence.members, top_n: null }
  const proposal = { id: 'p2', card: { candidate_id: 'chart:3:v1', evidence, view_ids: ['v2', 'v3'], member_action: 'use_evidence', changes: [{ changed_fields: ['end', 'categories', 'top_n'], after_source: after }] } }
  const seed = revisionSeed(proposal)
  assert.deepEqual(revisionPayload(seed.form, seed.evidence, 'direct'), { candidate_id: 'chart:3:v1', view_ids: ['v2', 'v3'], member_action: 'use_evidence', source_patch: { end: '2017-04-01' } })
})

test('reopening a rerank proposal retains its unchanged ranking measure', () => {
  const proposal = { id: 'p3', card: { evidence: null, view_ids: ['v2'], member_action: 'rerank', changes: [{ changed_fields: ['categories', 'top_n'], after_source: { categories: null, top_n: 5, rank_by: 'orders' } }] } }
  const seed = revisionSeed(proposal)
  assert.deepEqual(revisionPayload(seed.form, seed.evidence, 'bound_revision').source_patch, { categories: null, top_n: 5, rank_by: 'orders' })
})

import { computationScope, membershipRule, untouchedNumbers, provenanceNotice } from '../src/revisionDisplay.js'

test('source differences remain visible even when category members are equal', () => {
  const selected = { label: 'Chart 1 · version 3' }, used = { label: 'Chart 1 · version 1' }
  const card = { execution_provenance: { selected_source_at_onset: selected, executed_source: used,
    overrides_selection: true, members_equal: true } }
  assert.match(provenanceNotice(card), /Selected Chart 1 · version 3; used Chart 1 · version 1/)
  assert.match(provenanceNotice(card), /Same categories; different source/)
  card.execution_provenance.executed_source = null
  assert.match(provenanceNotice(card), /Selected, not used for this edit/)
  assert.equal(provenanceNotice({}), '')
})

test('saved-set reuse of the selected chart version is not an override', () => {
  const selected = { label: 'Chart 1 · version 3' }, used = { label: 'Saved set: Historical' }
  assert.equal(provenanceNotice({ execution_provenance: {
    selected_source_at_onset: selected, executed_source: used,
    overrides_selection: false, lineage_equal: true, candidate_ids_equal: false, members_equal: true } }),
  'Selected Chart 1 · version 3; used Saved set: Historical, saved from the selected chart version.')
  assert.equal(provenanceNotice({ execution_provenance: {
    selected_source_at_onset: selected, executed_source: used,
    overrides_selection: false, lineage_equal: true, candidate_ids_equal: true, members_equal: true } }), '')
  assert.equal(provenanceNotice({ execution_provenance: {
    selected_source_at_onset: selected, executed_source: used,
    overrides_selection: false, members_equal: true } }), '')
})

test('revision display separates fixed category filters from a dynamic ranking for any grouping', () => {
  assert.match(membershipRule({ dimension: 'month', categories: ['health_beauty'], top_n: null }), /^Fixed categories \(1\):/)
  assert.match(membershipRule({ dimension: 'category', categories: null, top_n: 3, rank_by: 'orders' }), /^Dynamic top 3 by/)
  assert.match(computationScope({ region: 'MG', start: '2017-01-01', end: '2017-04-01', metric: 'orders', status: 'delivered' }), /^MG/)
})

test('untouched chart numbers use the proposal snapshot rather than a later canvas', () => {
  assert.deepEqual(untouchedNumbers({ untouched_views: [{ view_id: 'old', number: 1 }] }), [1])
  assert.deepEqual(untouchedNumbers({ view_ids: ['v2'] }), [])
})

test('correcting a committed card reuses its exact shared patch across heterogeneous targets', () => {
  const proposal = { id: 'p4', card: { source_patch: { end: '2017-04-01', categories: ['category_a'], top_n: null }, evidence,
    view_ids: ['v2', 'v3'], member_action: 'use_evidence', changes: [
      { changed_fields: ['end'], after_source: { metric: 'orders', end: '2017-04-01' } },
      { changed_fields: ['end'], after_source: { metric: 'low_review_rate', end: '2017-04-01' } },
    ] } }
  const seed = revisionSeed(proposal)
  assert.deepEqual(revisionPayload(seed.form, seed.evidence, 'bound_revision').source_patch, { end: '2017-04-01' })
  assert.deepEqual(seed.form.view_ids, ['v2', 'v3'])
})
