<script setup>
import { computed } from 'vue'
import { humanize, formatRange } from '../chart.js'
import { sourceLabels, sourceValue, keptConditions, computationScope, membershipRule, untouchedNumbers, provenanceNotice } from '../revisionDisplay.js'
const props = defineProps({ card: Object, state: Object })
const untouched = computed(() => untouchedNumbers(props.card))
</script>

<template>
  <div class="revision-sections">
    <p v-if="provenanceNotice(card)" class="provenance-notice" :class="{ 'provenance-context': !card.execution_provenance.executed_source }" aria-label="Selected and used evidence">{{ provenanceNotice(card) }}</p>
    <section class="revision-section" aria-label="Sources">
      <h3>Object origin</h3>
      <template v-if="card.evidence && card.member_action === 'use_evidence'">
        <strong>{{ card.origin?.label || `Chart ${card.evidence.number} · v${card.evidence.revision}` }}</strong>
        <p>{{ card.evidence.source.region || 'All regions' }} · {{ formatRange(card.evidence.source.start, card.evidence.source.end) }}</p>
        <p>{{ card.evidence.members.map(humanize).join(', ') }}</p>
        <small>Only these category identities carry forward.</small>
      </template>
      <template v-else><strong>Current chart selections · v{{ card.base_revision }}</strong><p>{{ card.member_action === 'rerank' ? 'Calculate a new ranking in the requested scope.' : 'Retain each target’s current members or ranking rule.' }}</p></template>
    </section>
    <section class="revision-section" aria-label="Change">
      <h3>Current computation &amp; changes</h3>
      <article v-for="change in card.changes" :key="change.view_id">
        <strong>Chart {{ change.number }}</strong><p>{{ computationScope(change.after_source) }}</p><p>{{ membershipRule(change.after_source) }}</p>
        <p v-for="field in change.changed_fields" :key="field"><span class="revision-field-label">{{ sourceLabels[field] || humanize(field) }}:</span> {{ sourceValue(change.before_source, field) }} → {{ sourceValue(change.after_source, field) }}</p>
        <p v-if="!change.changed_fields.length">No source conditions changed.</p>
      </article>
    </section>
    <section class="revision-section" aria-label="Keep and release">
      <h3>Keep &amp; release</h3>
      <article v-for="change in card.changes" :key="change.view_id">
        <strong>Chart {{ change.number }} · Keep</strong>
        <p>{{ keptConditions(change).map(entry => `${entry.label}: ${entry.value}`).join(' · ') || 'No source conditions retained.' }}</p>
        <p><span class="revision-field-label">Release:</span> {{ change.released_fields?.length ? change.released_fields.map(field => `${sourceLabels[field] || humanize(field)} — ${sourceValue(change.before_source, field)}`).join(' · ') : 'None' }}</p>
      </article>
      <p v-if="untouched.length"><span class="revision-field-label">Outside this edit:</span> Charts {{ untouched.join(', ') }} stay unchanged.</p>
    </section>
  </div>
</template>

<style scoped>
.revision-sections{display:grid;gap:12px;min-width:0}.revision-section{border-top:1px solid #dce6dd;padding-top:12px}.revision-section h3{font:650 14px/1.5 'DM Sans','Segoe UI',sans-serif;color:#376757;margin:0 0 6px}.revision-section strong,.revision-section p{font-size:14px;line-height:1.6;color:#385448;overflow-wrap:anywhere}.revision-section p{margin-top:4px}.revision-section small{display:block;font-size:12px;line-height:1.5;color:#647a6c;margin-top:6px}.revision-section article+article{margin-top:10px}.revision-field-label{font-weight:550}
@media(min-width:2300px){.revision-section strong,.revision-section p,.revision-section h3{font-size:15px}.revision-section small{font-size:13px}}
</style>
