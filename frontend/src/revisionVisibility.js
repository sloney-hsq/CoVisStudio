// Visibility records a displayed DOM surface, never a claim that it was read.
export function observeRevisionVisibility(element, { proposalId, proposalStatus, surface, emit, enabled = true,
  document: page = document, IntersectionObserver: Observer = IntersectionObserver,
  now = () => performance.now(), newId = () => crypto.randomUUID() }) {
  let intersects = false, interval = null, disposed = false
  function sync(reason) {
    const visible = enabled && intersects && page.visibilityState === 'visible' && !disposed
    if (visible && !interval) {
      interval = { id: newId(), started: now() }
      emit('revision_card_visible', { proposal_id: proposalId, proposal_status: proposalStatus, surface, display_id: interval.id,
        visibility_reason: reason }, interval.started)
    } else if (!visible && interval) {
      const ended = now()
      emit('revision_card_hidden', { proposal_id: proposalId, surface, display_id: interval.id,
        visibility_reason: reason, duration_ms: ended - interval.started }, ended)
      interval = null
    }
  }
  const observer = new Observer(entries => {
    intersects = entries[0].isIntersecting && entries[0].intersectionRatio > 0
    sync(intersects ? 'in_view' : 'outside_view')
  }, { threshold: 0 })
  const visibilityChanged = () => sync(page.visibilityState === 'visible' ? 'document_visible' : 'document_hidden')
  observer.observe(element)
  page.addEventListener('visibilitychange', visibilityChanged)
  return {
    setEnabled(value) { enabled = value; sync(value ? 'surface_uncovered' : 'surface_covered') },
    dispose() {
      disposed = true; sync('unmounted')
      observer.disconnect(); page.removeEventListener('visibilitychange', visibilityChanged)
    },
  }
}
