import test from 'node:test'
import assert from 'node:assert/strict'
import { causeLabel, timingLabel, viewSummary } from '../src/scenarios.js'

test('scenario timing labels follow the playback-anchored injection points', () => {
  assert.equal(timingLabel({ type: 'after_end' }), 'after reply')
  assert.equal(timingLabel({ type: 'barge_in', offset_s: 3 }), 'barge-in +3s')
  assert.equal(timingLabel({ type: 'barge_in' }), 'barge-in')
  assert.equal(timingLabel({ type: 'during_tool', offset_s: 0.3 }), 'during tool +0.3s')
})

test('scores show first causes and per-view field mismatches without inventing verdicts', () => {
  assert.equal(causeLabel(null), 'Correct')
  assert.equal(causeLabel('segmentation_timing'), 'Segmentation / timing')
  assert.equal(viewSummary({ v1: { status: 'match', fields: [] }, v2: { status: 'mismatch', fields: ['region'] },
    v3: { status: 'unknown' } }), 'v1 ✓ · v2 ✗ region · v3 ?')
})
