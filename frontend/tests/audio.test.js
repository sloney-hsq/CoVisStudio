import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { encodePCM, decodePCM, wavBlob, Speaker } from '../src/audio.js'
test('PCM transport preserves signed 16-bit samples', () => {
  const pcm = new Int16Array([-32768, -100, 0, 100, 32767])
  assert.deepEqual(decodePCM(encodePCM(pcm.buffer)), pcm)
})
test('WAV replay retains complete chunks and correct sample rate', async () => {
  const chunks = [new Int16Array([100, 200]), new Int16Array([-100])]
  const bytes = await wavBlob(chunks, 24000).arrayBuffer(), view = new DataView(bytes)
  assert.equal(bytes.byteLength, 50)
  assert.equal(view.getUint32(24, true), 24000)
  assert.equal(view.getUint32(40, true), 6)
  assert.deepEqual(new Int16Array(bytes, 44), new Int16Array([100, 200, -100]))
})

function playbackWorklet(rate = 24000) {
  let Worklet
  const messages = [], scope = { sampleRate: rate, currentTime: 0,
    AudioWorkletProcessor: class { constructor() { this.port = { postMessage: value => messages.push(value) } } },
    registerProcessor: (_, constructor) => { Worklet = constructor } }
  vm.runInNewContext(readFileSync(new URL('../public/playback-worklet.js', import.meta.url), 'utf8'), scope)
  const worklet = new Worklet()
  return { messages, command: data => worklet.port.onmessage({ data }), process(length = 128) {
    const out = new Float32Array(length); worklet.process([], [[out]]); scope.currentTime += length / rate; return out
  } }
}
const audio = (id = 'reply', length = 24000) => ({ data: encodePCM(new Int16Array(length).fill(8192).buffer), response_id: id, request_id: 'r1', epoch: 2 })
function speakerHost(t, suspended = false) {
  const vm = playbackWorklet(), events = [], recordings = []; let resume
  const context = { state: suspended ? 'suspended' : 'running', destination: {}, audioWorklet: { addModule: async () => {} },
    resume: () => new Promise(resolve => { resume = resolve }), close: async () => {} }
  const prior = globalThis.AudioWorkletNode
  globalThis.AudioWorkletNode = class { constructor() { this.port = { postMessage: vm.command }; this.connect = () => {}; this.disconnect = () => {} } }
  const speaker = new Speaker((name, details) => events.push({ name, ...details }), (id, url, metadata) => recordings.push({ id, url, metadata }))
  speaker.context = context
  t.after(() => { globalThis.AudioWorkletNode = prior; recordings.forEach(item => URL.revokeObjectURL(item.url)) })
  function deliver() { for (const message of vm.messages.splice(0)) speaker.worklet.port.onmessage({ data: message }) }
  return { speaker, events, recordings, vm, deliver, resume: () => resume() }
}
for (const rate of [24000, 48000]) test(`worklet receipts count actual source cursor at ${rate} Hz`, () => {
  const w = playbackWorklet(rate)
  w.command({ type: 'audio', generation_epoch: 0, chunk_id: 'c1', response_id: 'r1', pcm: new Int16Array(2400).fill(8192), sample_rate: 24000 })
  const out = w.process(rate / 20)
  assert.equal(out[0], .25)
  assert.equal(w.messages.find(m => m.type === 'progress').played_samples, 1200)
  w.command({ type: 'audio', generation_epoch: 0, chunk_id: 'c2', response_id: 'r1', pcm: new Int16Array(20), sample_rate: 24000 })
  w.command({ type: 'clear', generation_epoch: 1 })
  assert.deepEqual(w.messages.filter(m => m.type === 'ended').map(m => [m.chunk_id, m.played_samples, m.interrupted]), [['c1', 1200, true], ['c2', 0, true]])
  w.command({ type: 'audio', generation_epoch: 0, pcm: new Int16Array(20).fill(3000), sample_rate: 24000 })
  assert.equal(w.process().some(value => value !== 0), false)
})
test('end before ready waits for worklet drain and preserves received WAV', async t => {
  const h = speakerHost(t, true), pending = h.speaker.append(audio('reply', 2400))
  h.speaker.end('reply'); await Promise.resolve(); await Promise.resolve(); h.resume(); await pending
  assert.equal(h.recordings.length, 0)
  h.vm.process(2400); h.deliver()
  assert.equal(h.events.at(-1).name, 'playback_end'); assert.equal(h.events.at(-1).played_samples, 2400)
  assert.equal(h.events.at(-1).request_id, 'r1'); assert.equal(h.events.at(-1).queue_empty, true)
  assert.equal((await (await fetch(h.recordings[0].url)).arrayBuffer()).byteLength, 4844)
})
test('stop accounting waits for clear acknowledgement and credits no queued PCM', async t => {
  const h = speakerHost(t)
  await h.speaker.append(audio()); await h.speaker.append(audio()); h.deliver()
  h.vm.process(1234); h.deliver(); h.speaker.stop()
  assert.equal(h.events.some(e => e.name === 'playback_stopped'), false)
  h.deliver()
  assert.deepEqual(h.events.at(-1).chunks.map(c => c.played_samples_in_chunk), [1234, 0])
  assert.equal(h.events.at(-1).interrupted, true); assert.equal(h.events.at(-1).pending_chunks, 0)
  await h.speaker.append(audio()); assert.equal(h.recordings.length, 1)
})
test('stop during ready prevents late scheduling and records zero', async t => {
  const h = speakerHost(t, true), pending = h.speaker.append(audio())
  h.speaker.stop(); await Promise.resolve(); await Promise.resolve(); h.resume(); await pending; h.deliver()
  assert.equal(h.events.some(e => e.name === 'playback_start'), false)
  assert.equal(h.events.at(-1).played_samples, 0); assert.equal(h.events.at(-1).started, false)
})
test('late receipts from a different generation cannot change playback', async t => {
  const h = speakerHost(t); await h.speaker.append(audio('reply', 128)); h.deliver()
  h.speaker.receipt({ type: 'ended', response_id: 'reply', chunk_id: 'reply:1', generation_epoch: -1, played_samples: 128 })
  h.speaker.end('reply'); assert.equal(h.recordings.length, 0)
  h.vm.process(); h.deliver(); assert.equal(h.recordings.length, 1)
})
test('stream end after worklet drain publishes once', async t => {
  const h = speakerHost(t); await h.speaker.append(audio('reply', 128)); h.vm.process(); h.deliver()
  assert.equal(h.recordings.length, 0)
  h.speaker.end('reply'); h.speaker.end('reply'); assert.equal(h.recordings.length, 1)
  assert.equal(h.events.at(-1).played_samples, 128)
})

function microphoneWorklet() {
  let Worklet
  const messages = []
  const context = { AudioWorkletProcessor: class { constructor() { this.port = { postMessage: value => messages.push(value) } } },
    registerProcessor: (_, constructor) => { Worklet = constructor }, Int16Array, sampleRate: 16000 }
  vm.runInNewContext(readFileSync(new URL('../public/microphone.js', import.meta.url), 'utf8'), context)
  const worklet = new Worklet()
  const command = data => worklet.port.onmessage({ data })
  const input = (value, length) => worklet.process([[new Float32Array(length).fill(value)]])
  const samples = () => messages.filter(message => message.type === 'pcm').flatMap(message => [...new Int16Array(message.buffer)])
  return { command, input, samples, messages }
}

test('paused microphone samples are excluded from the next submitted segment', () => {
  const { command, input, samples } = microphoneWorklet()
  input(.7, 200)
  command({ type: 'start', limit_samples: null })
  input(.1, 200)
  command({ type: 'pause' })
  input(.9, 200)
  command({ type: 'start', limit_samples: null })
  input(.2, 200)
  command({ type: 'pause' })
  assert.deepEqual(samples(), [...Array(200).fill(3276), ...Array(200).fill(6553)])
})

test('push-to-talk stops at exactly ten seconds of captured PCM', () => {
  const { command, input, samples, messages } = microphoneWorklet()
  command({ type: 'start', limit_samples: 160000 })
  for (let i = 0; i < 1300; i++) input(.1, 128)
  assert.equal(samples().length, 160000)
  assert.equal(messages.filter(message => message.type === 'limit_reached').length, 1)
  command({ type: 'pause' })
  assert.equal(samples().length, 160000)
})
