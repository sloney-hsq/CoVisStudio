// Receipts measure PCM handed to the output graph, not acoustic listening.
class Playback extends AudioWorkletProcessor {
  constructor() {
    super(); this.queue = []; this.generation = 0
    this.port.onmessage = ({ data }) => {
      if (data.type === 'clear' && data.generation_epoch >= this.generation) {
        for (const item of this.queue) this.report('ended', item, true, currentTime)
        this.queue = []; this.generation = data.generation_epoch
        this.port.postMessage({ type: 'cleared', generation_epoch: this.generation })
      } else if (data.type === 'audio' && data.generation_epoch === this.generation) {
        this.queue.push({ ...data, cursor: 0, reported: 0, started: false })
      }
    }
  }
  report(type, item, interrupted, contextTime) {
    item.reported = Math.min(item.pcm.length, Math.floor(item.cursor))
    this.port.postMessage({ type, response_id: item.response_id, chunk_id: item.chunk_id,
      generation_epoch: item.generation_epoch, played_samples: item.reported, interrupted, context_time: contextTime })
  }
  process(inputs, outputs) {
    const out = outputs[0][0]; out.fill(0)
    for (let i = 0; i < out.length; i++) {
      const item = this.queue[0]
      if (!item) break
      if (!item.started) { item.started = true; this.report('started', item, false, currentTime + i / sampleRate) }
      const index = Math.floor(item.cursor), fraction = item.cursor - index
      out[i] = (item.pcm[index] * (1 - fraction) + item.pcm[Math.min(index + 1, item.pcm.length - 1)] * fraction) / 32768
      item.cursor = Math.min(item.pcm.length, item.cursor + item.sample_rate / sampleRate)
      if (item.cursor >= item.pcm.length) {
        this.report('ended', item, false, currentTime + (i + 1) / sampleRate); this.queue.shift()
      } else if (item.cursor - item.reported >= 1200) this.report('progress', item, false, currentTime + (i + 1) / sampleRate)
    }
    return true
  }
}
registerProcessor('covis-playback', Playback)
