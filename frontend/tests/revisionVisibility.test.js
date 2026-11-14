import test from 'node:test'
import assert from 'node:assert/strict'
import { observeRevisionVisibility } from '../src/revisionVisibility.js'

function fixture(enabled = true) {
  let callback, tick = 0, sequence = 0, listener, disconnected = false
  const events = [], document = { visibilityState: 'visible',
    addEventListener(name, fn) { listener = fn }, removeEventListener() { listener = null } }
  class Observer {
    constructor(fn) { callback = fn }
    observe() {}
    disconnect() { disconnected = true }
  }
  const observation = observeRevisionVisibility({}, { proposalId: 'p1', proposalStatus: 'pending', surface: 'detail', enabled,
    document, IntersectionObserver: Observer, now: () => tick, newId: () => `display-${++sequence}`,
    emit: (name, details, client_ms) => events.push({ name, details, client_ms }) })
  return { events, observation,
    intersect(value) { callback([{ isIntersecting: value, intersectionRatio: value ? .1 : 0 }]) },
    visibility(value) { document.visibilityState = value; listener() },
    advance(value) { tick += value },
    cleaned() { return disconnected && listener === null },
  }
}

test('a mounted but offscreen card is not exposure; a partial intersection starts one interval', () => {
  const f = fixture()
  assert.equal(f.events.length, 0)
  f.intersect(false); assert.equal(f.events.length, 0)
  f.intersect(true); f.advance(123); f.intersect(true)
  assert.equal(f.events.length, 1)
  assert.equal(f.events[0].details.proposal_status, 'pending')
  f.intersect(false)
  assert.deepEqual(f.events.map(event => event.name), ['revision_card_visible', 'revision_card_hidden'])
  assert.equal(f.events[1].details.duration_ms, 123)
  assert.equal(f.events[0].details.display_id, f.events[1].details.display_id)
  assert.equal(f.events[1].details.visibility_reason, 'outside_view')
})

test('tab hiding closes the interval, return starts a new ID, and unmount closes it', () => {
  const f = fixture()
  f.intersect(true); f.advance(11); f.visibility('hidden'); f.advance(900); f.visibility('visible')
  assert.equal(f.events[1].details.duration_ms, 11)
  assert.equal(f.events[1].details.visibility_reason, 'document_hidden')
  assert.notEqual(f.events[0].details.display_id, f.events[2].details.display_id)
  f.advance(2); f.observation.dispose()
  assert.equal(f.events[3].details.duration_ms, 2)
  assert.equal(f.events[3].details.visibility_reason, 'unmounted')
  assert.equal(f.cleaned(), true)
})

test('a drawer covering the summary prevents exposure and splits visible intervals', () => {
  const f = fixture(false)
  f.intersect(true); assert.equal(f.events.length, 0)
  f.observation.setEnabled(true); f.advance(42); f.observation.setEnabled(false)
  assert.equal(f.events[1].details.duration_ms, 42)
  f.advance(500); f.observation.setEnabled(true); f.observation.dispose()
  assert.notEqual(f.events[0].details.display_id, f.events[2].details.display_id)
  assert.equal(f.events[3].details.duration_ms, 0)
})
