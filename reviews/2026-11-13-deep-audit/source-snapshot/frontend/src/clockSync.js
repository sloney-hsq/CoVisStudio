// The browser collects timestamps; Trace owns the clock conversion.
export class ClockSync {
  constructor(send, { now = () => performance.now(), newId = () => crypto.randomUUID(),
    schedule = (callback, interval) => setInterval(callback, interval),
    unschedule = timer => clearInterval(timer) } = {}) {
    this.send = send
    this.now = now
    this.newId = newId
    this.schedule = schedule
    this.unschedule = unschedule
    this.clockId = newId()
    this.active = false
    this.timer = null
    this.pending = null
  }

  start(sessionId) {
    this.stop()
    this.sessionId = sessionId
    this.active = true
    this.beginRound()
    this.timer = this.schedule(() => this.beginRound(), 30000)
  }

  reset(sessionId) {
    if (this.active && sessionId !== this.sessionId) this.start(sessionId)
  }

  beginRound() {
    this.samples = []
    this.sendProbe()
  }

  sendProbe() {
    this.pending = { sync_id: this.newId(), client_send_ms: this.now() }
    this.send({ type: 'clock_ping', client_clock_id: this.clockId,
      session_id: this.sessionId, ...this.pending })
  }

  acceptPong(message) {
    const received = this.now()
    // A task change starts a new server clock; a previous round cannot calibrate it.
    if (!this.active || message.session_id !== this.sessionId ||
        message.sync_id !== this.pending?.sync_id) return
    this.samples.push({ ...this.pending, client_receive_ms: received,
      server_receive_ms: message.server_receive_ms, server_send_ms: message.server_send_ms })
    this.pending = null
    if (this.samples.length === 3) {
      this.send({ type: 'clock_sample', client_clock_id: this.clockId,
        session_id: this.sessionId, samples: this.samples })
    } else this.sendProbe()
  }

  stop() {
    this.active = false
    if (this.timer !== null) this.unschedule(this.timer)
    this.timer = null
    this.pending = null
  }
}
