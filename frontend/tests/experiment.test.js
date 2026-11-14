import test from 'node:test'
import assert from 'node:assert/strict'
import { clockLabel, nextTrialIndex, trialTimeLeft } from '../src/experiment.js'

test('preparation has no elapsed task time; a running task counts from its explicit begin timestamp', () => {
  const assignment = { time_limit_seconds: 480 }
  assert.equal(trialTimeLeft(assignment, null, Date.now()), 480)
  assert.equal(trialTimeLeft(assignment, '2026-11-13T00:00:00Z', Date.parse('2026-11-13T00:02:03Z')), 357)
  assert.equal(clockLabel(357), '5:57')
  assert.equal(trialTimeLeft(assignment, '2026-11-13T00:00:00Z', Date.parse('2026-11-13T00:09:00Z')), 0)
})

test('the assigned sequence ends after four tasks rather than silently restarting', () => {
  assert.equal(nextTrialIndex({ trial_index: 1 }), 2)
  assert.equal(nextTrialIndex({ trial_index: 4 }), null)
})
