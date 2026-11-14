import test from 'node:test'
import assert from 'node:assert/strict'
import { blankCodingFiles, episodeBoundariesValid, episodeControls, outcomeLabel } from '../src/intentReview.js'

const events = [{ index: 2, name: 'trial_started' }, { index: 4, name: 'speech_start' },
  { index: 7, name: 'request_accepted' }, { index: 10, name: 'tool_committed' },
  { index: 13, name: 'trial_finished' }, { index: 15, name: 'review_note' }]

test('episode boundaries use actual input and include ordered recorded events within the trial', () => {
  const boundary = { onset_index: 4, utterance_end_index: 7, end_event_index: 13 }
  assert.equal(episodeBoundariesValid(events, boundary), true)
  assert.equal(episodeBoundariesValid(events, { ...boundary, onset_index: 10 }), false)
  assert.equal(episodeBoundariesValid(events, { ...boundary, utterance_end_index: 6 }), false)
  assert.equal(episodeBoundariesValid(events, { ...boundary, end_event_index: 4 }), false)
  assert.equal(episodeBoundariesValid(events, { ...boundary, end_event_index: 15 }), false)
  assert.equal(episodeBoundariesValid([{ index: 1, name: 'manual_edit_requested' }, ...events],
    { onset_index: 1, utterance_end_index: 1, end_event_index: 13 }), true)
})

test('only a locked unscored terminal episode can become the primary endpoint', () => {
  const episode = { packet_id: 'p1', locked: true, scored: false, end_event_index: 13, primary: false }
  assert.deepEqual(episodeControls(episode, [episode], 13), { designate: true, score: false })
  for (const changed of [{ locked: false }, { scored: true }, { end_event_index: 10 }]) {
    assert.equal(episodeControls({ ...episode, ...changed }, [episode], 13).designate, false)
  }
  assert.equal(episodeControls(episode, [episode, { primary: true }], 13).designate, false)
  assert.deepEqual(episodeControls({ ...episode, primary: true }, [{ primary: true }], 13), { designate: false, score: true })
  assert.equal(episodeControls({ ...episode, primary: true, scored: true }, [episode], 13).score, false)
})

test('downloaded coding templates contain no outcome or invented human judgment', () => {
  const templates = blankCodingFiles('blind-packet')
  assert.equal(templates.coder_a.packet_id, 'blind-packet')
  assert.equal(templates.coder_a.status, 'pending')
  assert.equal(templates.coder_b.reviewer_id, '')
  assert.equal(templates.adjudication.intent.status, 'unknown')
  assert.deepEqual(templates.adjudication.intent.evidence_indices, [])
  assert.equal(templates.coder_a.speech_verification, 'pending')
  assert.equal('final_correct' in templates.coder_a, false)
  templates.coder_a.intent.target_view_ids.push('v1')
  assert.deepEqual(templates.coder_b.intent.target_view_ids, [])
  assert.deepEqual(templates.adjudication.intent.target_view_ids, [])
  assert.equal(outcomeLabel(null), 'Unknown / pending')
  assert.equal(outcomeLabel(undefined), 'Unknown / pending')
  assert.equal(outcomeLabel(false), 'Incorrect')
  assert.equal(outcomeLabel(true), 'Correct')
})
