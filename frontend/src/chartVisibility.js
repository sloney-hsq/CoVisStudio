// A rendered plot intersecting a visible page is candidate exposure, not reading.
export function observeChartVisibility(element, { emit, enabled = false, surfaceId,
  document: page = document, IntersectionObserver: Observer = IntersectionObserver,
  now = () => performance.now(), newId = () => crypto.randomUUID() }) {
  const surface = surfaceId ?? newId()
  let current = null, ready = false, ratio = 0, interval = null, disposed = false
  const same = identity => current && identity.view_id === current.view_id &&
    identity.revision === current.revision && identity.render_generation === current.render_generation
  function close(reason) {
    if (!interval) return
    const ended = now()
    emit('chart_hidden', { ...interval.details, intersection_ratio: ratio, visibility_reason: reason,
      ended_client_ms: ended, duration_ms: ended - interval.started }, ended)
    interval = null
  }
  function sync(reason) {
    const visible = !disposed && enabled && ready && ratio > 0 && page.visibilityState === 'visible'
    if (!visible) close(reason)
    else if (!interval) {
      const started = now()
      const details = { ...current, surface_id: surface, display_id: newId(),
        intersection_ratio: ratio, visibility_reason: reason, started_client_ms: started }
      interval = { details, started }
      emit('chart_visible', { ...details }, started)
    }
  }
  const observer = new Observer(entries => {
    const entry = entries[0]
    ratio = entry.isIntersecting ? entry.intersectionRatio : 0
    sync(ratio > 0 ? 'in_view' : 'outside_view')
  }, { threshold: 0 })
  const visibilityChanged = () => sync(page.visibilityState === 'visible' ? 'document_visible' : 'document_hidden')
  observer.observe(element)
  page.addEventListener('visibilitychange', visibilityChanged)
  return {
    beginRender(identity) {
      close('render_started')
      current = { ...identity }; ready = false
    },
    rendered(identity) {
      if (!same(identity) || disposed) return
      ready = true; sync('render_finished')
    },
    setEnabled(value) { enabled = value; sync(value ? 'surface_enabled' : 'surface_disabled') },
    dispose() {
      disposed = true; close('unmounted')
      observer.disconnect(); page.removeEventListener('visibilitychange', visibilityChanged)
    },
  }
}
