import test from 'node:test'
import assert from 'node:assert/strict'
import { eventText, measuredEvents, nodeAtEvent, relativeEventTime } from '../src/review.js'

test('review span choices exclude preparation and post-task review', () => {
  const events = [
    { index: 1, name: 'tool_committed', server_ms: 100 },
    { index: 3, name: 'trial_started', server_ms: 300 },
    { index: 8, name: 'undo', server_ms: 800 },
    { index: 12, name: 'trial_finished', server_ms: 1200 },
    { index: 15, name: 'human_note', server_ms: 1500 },
  ]
  assert.deepEqual(measuredEvents(events).map(event => event.index), [3, 8, 12])
  assert.equal(relativeEventTime(events[2], events), '+0.5 s')
  assert.equal(relativeEventTime(events[0], events), '-0.2 s')
  assert.deepEqual(measuredEvents(events.slice(0, 1)), [])
  assert.equal(eventText(events[2]), '') // Undo alone does not mean repair.
})

test('historical event inspection never uses a later canvas', () => {
  const nodes = [{ id: 'old', event_index: 2 }, { id: 'new', event_index: 9 }]
  assert.equal(nodeAtEvent(nodes, { index: 5 }).id, 'old')
  assert.equal(nodeAtEvent(nodes, { index: 9 }).id, 'new')
  assert.equal(nodeAtEvent(nodes, { index: 1 }), null)
  assert.equal(eventText({ event: { text: 'Keep the earlier categories.' } }), 'Keep the earlier categories.')
})

test('a publication precedes node creation but already exposes the new committed revision', () => {
  const nodes = [{ id: 'before', event_index: 3, revision: 1 }, { id: 'after', event_index: 9, revision: 2 }]
  for (const name of ['tool_committed', 'undo', 'restore']) {
    assert.equal(nodeAtEvent(nodes, { index: 8, name, revision: 2 }).id, 'after')
  }
  assert.equal(nodeAtEvent(nodes, { index: 10, name: 'image_captured', revision: 1 }).id, 'after')
  assert.equal(nodeAtEvent(nodes, { index: 7, name: 'tool_started' }).id, 'before')
})
