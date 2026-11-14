import test from 'node:test'
import assert from 'node:assert/strict'
import { observeChartVisibility } from '../src/chartVisibility.js'

const first = { view_id: 'v1', revision: 1, render_generation: 1 }
const second = { view_id: 'v1', revision: 2, render_generation: 2 }
function fixture(enabled = true) {
  let callback, listener, tick = 0, sequence = 0, disconnected = false
  const events = [], document = { visibilityState: 'visible',
    addEventListener(name, fn) { listener = fn }, removeEventListener() { listener = null } }
  class Observer {
    constructor(fn) { callback = fn }
    observe() {}
    disconnect() { disconnected = true }
  }
  const observation = observeChartVisibility({}, { enabled, surfaceId: 'surface-1',
    document, IntersectionObserver: Observer, now: () => tick, newId: () => `display-${++sequence}`,
    emit: (name, details, client_ms) => events.push({ name, details, client_ms }) })
  return { events, observation,
    intersect(ratio) { callback([{ isIntersecting: ratio > 0, intersectionRatio: ratio }]) },
    visibility(value) { document.visibilityState = value; listener() },
    advance(value) { tick += value },
    cleaned() { return disconnected && listener === null },
  }
}

test('finished offscreen plots are not exposed; any positive intersection can start exposure', () => {
  const f = fixture()
  f.observation.beginRender(first); f.observation.rendered(first)
  f.intersect(0); assert.equal(f.events.length, 0)
  f.intersect(.01); f.advance(12); f.intersect(.3)
  assert.equal(f.events.length, 1)
  f.intersect(0)
  assert.deepEqual(f.events.map(e => e.name), ['chart_visible', 'chart_hidden'])
  assert.equal(f.events[1].details.duration_ms, 12)
  assert.equal(f.events[1].details.visibility_reason, 'outside_view')
  assert.equal(f.events[0].details.display_id, f.events[1].details.display_id)
})

test('a new render closes the previous identity and only its current finished callback reopens', () => {
  const f = fixture()
  f.intersect(1); f.observation.beginRender(first)
  assert.equal(f.events.length, 0)
  f.observation.rendered(first); f.advance(20)
  f.observation.beginRender(second); f.observation.rendered(first)
  assert.equal(f.events.length, 2)
  assert.equal(f.events[1].details.revision, 1)
  assert.equal(f.events[1].details.render_generation, 1)
  assert.equal(f.events[1].details.duration_ms, 20)
  f.observation.rendered(second)
  assert.equal(f.events[2].details.revision, 2)
  assert.equal(f.events[2].details.render_generation, 2)
  assert.equal(f.events[2].details.surface_id, 'surface-1')
  assert.notEqual(f.events[0].details.display_id, f.events[2].details.display_id)
})

test('hidden pages split intervals and exclude background time', () => {
  const f = fixture()
  f.intersect(1); f.observation.beginRender(first); f.observation.rendered(first)
  f.advance(8); f.visibility('hidden'); f.advance(900); f.visibility('visible')
  assert.equal(f.events[1].details.duration_ms, 8)
  assert.equal(f.events[1].details.visibility_reason, 'document_hidden')
  assert.equal(f.events[2].client_ms, 908)
  assert.notEqual(f.events[0].details.display_id, f.events[2].details.display_id)
})

test('coverage and disconnection disable intervals; unmount closes once and removes observers', () => {
  const f = fixture(false)
  f.intersect(1); f.observation.beginRender(first); f.observation.rendered(first)
  assert.equal(f.events.length, 0)
  f.observation.setEnabled(true); f.advance(5); f.observation.setEnabled(false)
  f.observation.setEnabled(false)
  assert.equal(f.events.length, 2)
  assert.equal(f.events[1].details.visibility_reason, 'surface_disabled')
  f.advance(200); f.observation.setEnabled(true); f.advance(3)
  f.observation.dispose(); f.observation.dispose(); f.observation.rendered(first)
  assert.equal(f.events.length, 4)
  assert.equal(f.events[3].details.duration_ms, 3)
  assert.equal(f.events[3].details.visibility_reason, 'unmounted')
  assert.equal(f.cleaned(), true)
})

test('separate component surfaces get independent identities for the same chart', () => {
  const events = [], page = { visibilityState: 'visible', addEventListener() {}, removeEventListener() {} }
  let id = 0
  class Observer { constructor(callback) { this.callback = callback } observe() { this.callback([{ isIntersecting: true, intersectionRatio: 1 }]) } disconnect() {} }
  const make = () => observeChartVisibility({}, { enabled: true, document: page, IntersectionObserver: Observer,
    newId: () => `id-${++id}`, emit: (name, details) => events.push({ name, details }) })
  const main = make(), expanded = make()
  for (const surface of [main, expanded]) { surface.beginRender(first); surface.rendered(first) }
  assert.notEqual(events[0].details.surface_id, events[1].details.surface_id)
  assert.notEqual(events[0].details.display_id, events[1].details.display_id)
  main.dispose(); expanded.dispose()
})
