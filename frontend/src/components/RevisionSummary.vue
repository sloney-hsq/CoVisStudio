<script setup>
import { computed } from 'vue'
import { humanize, formatRange } from '../chart.js'
import { sourceLabels, sourceValue, computationScope, membershipRule, untouchedNumbers, provenanceNotice } from '../revisionDisplay.js'
const props = defineProps({ card: Object, state: Object })
function groupDescriptions(describe) {
  const groups = new Map()
  for (const change of props.card.changes) {
    const description = describe(change)
    if (!groups.has(description)) groups.set(description, [])
    groups.get(description).push(change.number)
  }
  return [...groups].map(([description, numbers]) => ({ description, numbers: numbers.join(', ') }))
}
const scopes = computed(() => groupDescriptions(change => computationScope(change.after_source)))
const membership = computed(() => groupDescriptions(change => membershipRule(change.after_source)))
const changes = computed(() => groupDescriptions(change => change.changed_fields.map(field => `${sourceLabels[field]}: ${sourceValue(change.after_source, field)}`).join(' · ') || 'No source conditions changed.'))
const released = computed(() => groupDescriptions(change => change.released_fields.map(field => sourceLabels[field]).join(', ') || 'None'))
const untouched = computed(() => untouchedNumbers(props.card).join(', '))
</script>

<template>
  <div class="revision-brief">
    <p v-if="provenanceNotice(card)" class="provenance-notice" :class="{ 'provenance-context': !card.execution_provenance.executed_source }" aria-label="Selected and used evidence">{{ provenanceNotice(card) }}</p>
    <section class="revision-summary-section" aria-label="Sources"><h3>Object origin</h3><template v-if="card.member_action === 'use_evidence' && card.evidence"><p><strong>{{ card.origin?.label || `Chart ${card.evidence.number} · v${card.evidence.revision}` }}</strong> · {{ card.evidence.source.region || 'All regions' }} · {{ formatRange(card.evidence.source.start, card.evidence.source.end) }}</p><p>{{ card.evidence.members.map(humanize).join(', ') }}</p><small>These category identities carry forward; computation uses the scope below.</small></template><p v-else>{{ card.member_action === 'rerank' ? 'New ranking from the current computation scope.' : `Each target’s current selection or ranking rule · v${card.base_revision}` }}</p></section>
    <section class="revision-summary-section" aria-label="Current computation"><h3>Current computation</h3><p v-for="item in scopes" :key="item.numbers"><strong>Charts {{ item.numbers }}</strong> · {{ item.description }}</p><p v-for="item in membership" :key="item.numbers"><strong>Charts {{ item.numbers }}</strong> · {{ item.description }}</p></section>
    <section class="revision-summary-section" aria-label="Change"><h3>Change &amp; keep</h3><p v-for="item in changes" :key="item.numbers"><strong>Charts {{ item.numbers }}</strong> · {{ item.description }}</p><p v-for="item in released" :key="`release-${item.numbers}`"><strong>Charts {{ item.numbers }} · Release:</strong> {{ item.description }}</p><p v-if="untouched"><strong>Outside this edit:</strong> Charts {{ untouched }} stay unchanged.</p><small>Other conditions on each target are retained. Details show before → after and released conditions.</small></section>
  </div>
</template>

<style scoped>
.revision-brief{display:grid;gap:8px;min-width:0}.revision-summary-section{padding-top:8px;border-top:1px solid #dce6dd}.revision-summary-section h3{font:650 13px/1.4 'DM Sans','Segoe UI',sans-serif;color:#376757;margin-bottom:4px}.revision-summary-section p{font-size:13px;line-height:1.5;color:#385448;overflow-wrap:anywhere}.revision-summary-section p+p{margin-top:4px}.revision-summary-section strong{font-weight:600}.revision-summary-section small{display:block;font-size:12px;line-height:1.5;color:#647a6c;margin-top:4px}
@media(min-width:2300px){.revision-summary-section p,.revision-summary-section h3{font-size:14px}}
</style>
