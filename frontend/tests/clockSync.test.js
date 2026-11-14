import test from 'node:test'
import assert from 'node:assert/strict'
import { ClockSync } from '../src/clockSync.js'

function setup() {
  let time = 100, id = 0, periodic
  const sent = [], stopped = []
  const clock = new ClockSync(event => sent.push(event), {
    now: () => time, newId: () => `id-${++id}`,
    schedule: callback => { periodic = callback; return 1 },
    unschedule: timer => stopped.push(timer),
  })
  function pong(session = clock.sessionId) {
    const request = sent.at(-1)
    time += 10
    clock.acceptPong({ ...request, type: 'clock_pong', session_id: session,
      server_receive_ms: time - 8, server_send_ms: time - 6 })
  }
  return { clock, sent, stopped, pong, tick: () => periodic() }
}

test('one calibration sends three timestamp exchanges without model messages', () => {
  const { clock, sent, pong, tick } = setup()
  clock.start('session-a')
  pong(); pong(); pong()
  assert.deepEqual(sent.map(event => event.type), ['clock_ping', 'clock_ping', 'clock_ping', 'clock_sample'])
  const sample = sent.at(-1)
  assert.equal(sample.samples.length, 3)
  assert.deepEqual(sample.samples[0], { sync_id: 'id-2', client_send_ms: 100,
    client_receive_ms: 110, server_receive_ms: 102, server_send_ms: 104 })
  assert.equal(sample.client_clock_id, clock.clockId)
  tick()
  assert.equal(sent.at(-1).type, 'clock_ping')
  clock.stop()
})

test('a task change cannot accept an old session clock response', () => {
  const { clock, sent, pong } = setup()
  clock.start('session-a')
  const previous = sent[0]
  const clientClock = clock.clockId
  clock.reset('session-b')
  clock.acceptPong({ ...previous, type: 'clock_pong', server_receive_ms: 1, server_send_ms: 2 })
  assert.equal(sent.length, 2)
  pong(); pong(); pong()
  assert.equal(sent.at(-1).session_id, 'session-b')
  assert.equal(sent.at(-1).samples.length, 3)
  assert.equal(clock.clockId, clientClock)
  clock.stop()
})

test('closing the socket stops periodic sampling and ignores an outstanding pong', () => {
  const { clock, sent, stopped, pong } = setup()
  clock.start('session-a')
  clock.stop()
  pong('session-a')
  assert.equal(sent.length, 1)
  assert.deepEqual(stopped, [1])
})
