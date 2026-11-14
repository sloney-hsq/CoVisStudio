export function encodePCM(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
}
export function decodePCM(data) {
  const bytes = Uint8Array.from(atob(data), char => char.charCodeAt(0))
  return new Int16Array(bytes.buffer)
}
export function wavBlob(chunks, sampleRate = 24000) {
  const count = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0)
  const bytes = new ArrayBuffer(44 + count), view = new DataView(bytes)
  const string = (offset, text) => [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)))
  string(0, 'RIFF'); view.setUint32(4, 36 + count, true); string(8, 'WAVE'); string(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); string(36, 'data'); view.setUint32(40, count, true)
  let offset = 44
  chunks.forEach(chunk => { new Uint8Array(bytes, offset, chunk.byteLength).set(new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength)); offset += chunk.byteLength })
  return new Blob([bytes], { type: 'audio/wav' })
}

export class Microphone {
  constructor(onChunk, onLevel, onLimit = () => {}) { this.onChunk = onChunk; this.onLevel = onLevel; this.onLimit = onLimit; this.running = false }
  async prepare() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
    this.context = new AudioContext({ sampleRate: 16000 })
    await this.context.audioWorklet.addModule('/microphone.js')
    this.source = this.context.createMediaStreamSource(this.stream)
    this.worklet = new AudioWorkletNode(this.context, 'covis-microphone')
    this.worklet.port.onmessage = event => {
      if (event.data.type === 'paused') { this.paused(); return }
      if (event.data.type === 'limit_reached') { this.onLimit(); return }
      this.onChunk(encodePCM(event.data.buffer))
      this.onLevel(event.data.level || 0)
    }
    this.gain = this.context.createGain(); this.gain.gain.value = 0
    this.source.connect(this.worklet); this.worklet.connect(this.gain); this.gain.connect(this.context.destination)
    await this.context.resume()
  }
  start(limitSeconds = null) {
    this.running = true
    this.worklet.port.postMessage({ type: 'start', limit_samples: limitSeconds === null ? null : limitSeconds * this.context.sampleRate })
  }
  async pause() {
    if (!this.running) return this.pausing
    this.running = false
    this.pausing = new Promise(resolve => { this.paused = resolve; this.worklet.port.postMessage({ type: 'pause' }) })
    await this.pausing
    this.onLevel(0)
  }
  async close() {
    await this.pause()
    this.stream?.getTracks().forEach(track => track.stop())
    this.source?.disconnect(); this.worklet?.disconnect(); this.gain?.disconnect()
    await this.context?.close()
    this.stream = null
  }
}

export class Speaker {
  constructor(onEvent, onRecording) {
    this.onEvent = onEvent; this.onRecording = onRecording
    this.responses = new Map(); this.blocked = new Set(); this.generation = 0
  }
  async prepare() {
    if (!this.ready) this.ready = (async () => {
      this.context ||= new AudioContext({ sampleRate: 24000 })
      await this.context.audioWorklet.addModule('/playback-worklet.js')
      this.worklet = new AudioWorkletNode(this.context, 'covis-playback', { numberOfInputs: 0, outputChannelCount: [1] })
      this.worklet.port.onmessage = event => this.receipt(event.data)
      this.worklet.connect(this.context.destination)
      this.worklet.port.postMessage({ type: 'clear', generation_epoch: this.generation })
      if (this.context.state !== 'running') await this.context.resume()
    })()
    await this.ready
  }
  chunkPosition(chunk) {
    return { ...chunk.metadata, chunk_id: chunk.id, generation_epoch: chunk.generation,
      sample_start: chunk.start, sample_end: chunk.end,
      played_samples_in_chunk: chunk.played, chunk_played_sample_end: chunk.start + chunk.played }
  }
  details(response) {
    const played = response.chunks.reduce((sum, chunk) => sum + chunk.played, 0)
    return { ...response.metadata, generation_epoch: response.generation, timing_basis: 'audio_worklet_source_cursor',
      audio_context_time: response.contextTime ?? null, sample_rate: response.rate,
      received_samples: response.received, played_samples: played,
      queued_samples: response.stopped ? 0 : response.received - played,
      pending_chunks: response.pending, queue_empty: response.pending === 0,
      chunks: response.chunks.map(chunk => this.chunkPosition(chunk)) }
  }
  emit(name, response, extra = {}) { this.onEvent(name, { ...this.details(response), ...extra }) }
  receipt(message) {
    if (message.type === 'cleared') {
      for (const [id, response] of this.responses) {
        if (!response.stopped || response.published || response.clearGeneration > message.generation_epoch) continue
        response.pending = 0
        this.emit('playback_stopped', response); this.finish(id)
      }
      if (message.generation_epoch === this.generation) { this.clearResolve?.(); this.clearResolve = null }
      return
    }
    const response = this.responses.get(message.response_id)
    if (!response || response.published || message.generation_epoch !== response.generation) return
    const chunk = response.chunks.find(chunk => chunk.id === message.chunk_id)
    if (!chunk || chunk.done) return
    chunk.played = message.played_samples; response.contextTime = message.context_time
    if (message.type === 'started' && !response.started) {
      response.started = true; this.emit('playback_start', response)
    }
    if (message.type === 'progress') this.emit('playback_progress', response)
    if (message.type === 'ended') {
      chunk.done = true; response.pending -= 1
      this.emit('playback_chunk_ended', response, { ...this.chunkPosition(chunk), interrupted: message.interrupted })
      if (!response.stopped) this.finish(message.response_id)
    }
  }
  async append(input) {
    const { data, response_id, sample_rate = 24000 } = input
    if (this.blocked.has(response_id)) return
    const generation = this.generation, pcm = decodePCM(data)
    const metadata = Object.fromEntries(['request_id', 'epoch', 'response_id', 'item_id', 'content_index', 'context_id'].filter(key => input[key] !== undefined).map(key => [key, input[key]]))
    if (!this.responses.has(response_id)) this.responses.set(response_id, { metadata, generation, chunks: [], pending: 0, received: 0, started: false, ended: false, rate: sample_rate })
    const response = this.responses.get(response_id)
    const chunk = { id: input.chunk_id ?? `${response_id}:${response.chunks.length + 1}`, metadata, pcm, generation,
      start: input.sample_start ?? response.received, end: input.sample_end ?? response.received + pcm.length, played: 0 }
    response.chunks.push(chunk); response.pending += 1; response.received += pcm.length
    await this.prepare()
    if (generation !== this.generation) return
    chunk.sent = true
    this.worklet.port.postMessage({ type: 'audio', generation_epoch: generation, response_id, chunk_id: chunk.id, pcm, sample_rate })
    this.emit('playback_chunk_scheduled', response, this.chunkPosition(chunk))
  }
  end(responseId) {
    const response = this.responses.get(responseId)
    if (!response) return
    response.ended = true; this.finish(responseId)
  }
  finish(responseId) {
    const response = this.responses.get(responseId)
    if (!response.ended || response.pending || response.published) return
    response.published = true
    this.onRecording(responseId, URL.createObjectURL(wavBlob(response.chunks.map(chunk => chunk.pcm), response.rate)),
      { ...response.metadata, label: 'received_audio', received_samples: response.received, sample_rate: response.rate })
    this.emit('playback_end', response, { interrupted: !!response.stopped, started: response.started })
  }
  stop() {
    this.generation += 1
    for (const [id, response] of this.responses) {
      if (response.published || response.stopped) continue
      this.blocked.add(id); response.ended = true; response.stopped = true; response.clearGeneration = this.generation
      for (const chunk of response.chunks) if (!chunk.sent && !chunk.done) { chunk.done = true; response.pending -= 1 }
      if (!response.pending) { this.emit('playback_stopped', response); this.finish(id) }
    }
    if (this.worklet) {
      this.clearing = new Promise(resolve => { this.clearResolve = resolve })
      this.worklet.port.postMessage({ type: 'clear', generation_epoch: this.generation })
    }
  }
  async close() {
    this.stop(); await this.ready
    if (this.worklet) { this.stop(); await this.clearing }
    this.worklet?.disconnect(); await this.context?.close()
  }
}
