class CoVisMicrophone extends AudioWorkletProcessor {
  constructor() {
    super()
    this.samples = new Int16Array(640)
    this.offset = 0
    this.running = false
    this.count = 0
    this.sequence = 0
    this.limit = null
    this.port.onmessage = event => {
      if (event.data.type === 'start') {
        this.offset = 0; this.count = 0; this.limit = event.data.limit_samples
        this.running = true
      } else if (event.data.type === 'pause') {
        this.running = false
        this.flush()
        this.port.postMessage({ type: 'paused' })
      }
    }
  }
  flush(level = 0) {
    if (!this.offset) return
    const buffer = this.samples.slice(0, this.offset).buffer
    this.port.postMessage({ type: 'pcm', buffer, level,
      sequence: this.sequence++, first_sample: this.count - this.offset, sample_count: this.offset }, [buffer])
    this.offset = 0
  }
  process(inputs) {
    if (!this.running) return true
    const channel = inputs[0][0]
    if (!channel) return true
    let energy = 0
    for (const value of channel) {
      const sample = Math.max(-1, Math.min(1, value))
      energy += sample * sample
      this.samples[this.offset++] = sample < 0 ? sample * 32768 : sample * 32767
      this.count += 1
      if (this.offset === this.samples.length) {
        this.flush(Math.sqrt(energy / channel.length))
      }
      if (this.count === this.limit) {
        this.running = false
        this.flush()
        this.port.postMessage({ type: 'limit_reached' })
        break
      }
    }
    return true
  }
}
registerProcessor('covis-microphone', CoVisMicrophone)
