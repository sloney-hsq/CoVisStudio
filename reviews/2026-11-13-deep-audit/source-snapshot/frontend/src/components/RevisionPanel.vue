<script setup>
import { computed, reactive } from 'vue'
import { ArrowRight, Check, GitBranch, Link2, RotateCcw } from 'lucide-vue-next'
import { humanize, metricNames, formatRange } from '../chart.js'
import { revisionDefaults, revisionPayload } from '../revision.js'
import RevisionObservation from './RevisionObservation.vue'

const props = defineProps({ state: Object, evidence: Object, condition: String, proposal: Object, catalog: Object, selected: Array, busy: Boolean, observationsEnabled: Boolean })
const emit = defineEmits(['preview', 'apply', 'dismiss', 'observation'])
const form = reactive(revisionDefaults(props.selected, !!props.evidence))
const card = computed(() => props.proposal?.card)
const pending = computed(() => props.proposal?.status === 'pending')
const currentRegions = computed(() => {
  const targets = props.proposal ? props.proposal.card.view_ids : form.view_ids
  return [...new Set(props.state.views.filter(view => targets.includes(view.id)).map(view => view.source.region || 'All regions'))].join(' / ')
})
const canPreview = computed(() => form.view_ids.length && (form.member_action !== 'use_evidence' || props.evidence && (props.condition !== 'unbound_preview' || form.categories.length)))
function toggleTarget(id) { form.view_ids = form.view_ids.includes(id) ? form.view_ids.filter(value => value !== id) : [...form.view_ids, id] }
const sourceLabels = { metric: 'Measure', dimension: 'Group by', region: 'Region', start: 'From', end: 'Until (exclusive)', status: 'Order status', categories: 'Comparison set', top_n: 'Ranking size', rank_by: 'Ranking measure' }
function sourceValue(source, field) {
  const value = source[field]
  if (value === undefined) return 'Not specified'
  if (field === 'region' && value === null) return 'All regions'
  if (field === 'categories') return value === null ? 'No fixed set' : value.length ? value.map(humanize).join(', ') : 'Empty set'
  if (field === 'top_n') return value === null ? 'No top-N limit' : `Top ${value}`
  if (field === 'metric' || field === 'rank_by') return metricNames[value] || valueText(value)
  if (field === 'start' || field === 'end') return value === null ? 'Not specified' : value
  return valueText(value)
}
function keptConditions(change) {
  const source = change.after_source, fields = change.kept_fields
  const entries = []
  for (const field of fields) {
    if (field === 'end' && fields.includes('start') && source.start && source.end) continue
    if (field === 'start' && fields.includes('end') && source.start && source.end) entries.push({ field: 'period', label: 'Period', value: formatRange(source.start, source.end) })
    else entries.push({ field, label: sourceLabels[field] || humanize(field), value: sourceValue(source, field) })
  }
  return entries
}
function valueText(value) {
  if (value == null) return 'None'
  if (Array.isArray(value)) return value.map(humanize).join(', ')
  return humanize(String(value))
}
</script>

<template>
  <div class="drawer-body revision-body">
    <p class="drawer-intro">{{ evidence ? 'Bring categories from an earlier chart into the current analysis. Its filters stay in the past.' : 'Refine your current analysis. Conditions stay in place unless you explicitly change them.' }} Choose exactly which views should change.</p>
    <div class="revision-reference-map">
      <div class="revision-reference-block">
        <span class="eyebrow"><Link2 :size="13"/> EVIDENCE FROM</span>
        <template v-if="evidence"><strong>{{ evidence.source.region || 'All regions' }} · Chart {{ evidence.number }} · v{{ evidence.revision }}</strong><p>{{ formatRange(evidence.source.start, evidence.source.end) }}</p><div class="member-tags"><span v-for="member in evidence.members" :key="member">{{ humanize(member) }}</span></div></template>
        <template v-else><strong>No historical evidence selected</strong><p>Open a Journey version to reference its categories.</p></template>
      </div>
      <ArrowRight :size="19" class="reference-arrow"/>
      <div class="revision-reference-block current-reference"><span class="eyebrow">APPLY TO</span><strong>{{ currentRegions || 'Choose target views' }} · Current v{{ state.revision }}</strong><p>Keep each view's current conditions unless you change them below.</p></div>
    </div>

    <template v-if="!proposal">
      <div class="section-label">Views to update</div>
      <div class="revision-targets"><button v-for="view in state.views" :key="view.id" :class="{ active: form.view_ids.includes(view.id) }" :aria-pressed="form.view_ids.includes(view.id)" @click="toggleTarget(view.id)"><span class="target-number">{{ String(view.number).padStart(2, '0') }}</span><span><strong>{{ view.title }}</strong><small>{{ view.source.region || 'All regions' }} · {{ metricNames[view.source.metric] }}</small></span><Check v-if="form.view_ids.includes(view.id)" :size="16"/></button></div>
      <div class="section-label">Comparison objects</div>
      <div class="revision-membership">
        <label><input type="radio" v-model="form.member_action" value="keep_current"/><span><strong>Keep each view's selection</strong><small>Retain its current fixed members or ranking rule.</small></span></label>
        <label :class="{ unavailable: !evidence }"><input type="radio" v-model="form.member_action" value="use_evidence" :disabled="!evidence"/><span><strong>Use the referenced categories</strong><small>Take the objects from the earlier chart, not its filters.</small></span></label>
        <label><input type="radio" v-model="form.member_action" value="rerank"/><span><strong>Choose a new ranking</strong><small>Release the fixed set and calculate a new selection.</small></span></label>
      </div>
      <label v-if="condition === 'unbound_preview' && form.member_action === 'use_evidence'" class="field explicit-members"><span>Categories to apply</span><select multiple v-model="form.categories" aria-label="Explicit categories to apply"><option v-for="member in evidence.members" :key="member" :value="member">{{ humanize(member) }}</option></select><small>Select the exact categories to apply. Use Ctrl / Command for multiple selections.</small></label>
      <div v-if="form.member_action === 'rerank'" class="field-row"><label class="field"><span>Number of groups</span><input type="number" min="1" max="30" v-model.number="form.top_n"/></label><label class="field"><span>Rank by</span><select v-model="form.rank_by"><option v-for="(label, id) in metricNames" :key="id" :value="id">{{ label }}</option></select></label></div>
      <div class="section-label">Changes to current conditions</div>
      <div class="field-row"><label class="field"><span>Region</span><select v-model="form.region" aria-label="Revision region"><option value="">Keep current</option><option value="__all__">All regions</option><option v-for="region in catalog.states" :key="region" :value="region">{{ region }}</option></select></label><label class="field"><span>Measure</span><select v-model="form.metric" aria-label="Revision measure"><option value="">Keep current</option><option v-for="(label, id) in metricNames" :key="id" :value="id">{{ label }}</option></select></label></div>
      <div class="field-row"><label class="field"><span>From · blank keeps current</span><input type="date" v-model="form.start" aria-label="Revision start date"/></label><label class="field"><span>Until · exclusive</span><input type="date" v-model="form.end" aria-label="Revision end date"/></label></div>
      <label class="field"><span>Order status</span><select v-model="form.status"><option value="">Keep current</option><option value="delivered">Delivered</option><option value="shipped">Shipped</option><option value="canceled">Canceled</option></select></label>
      <div class="data-note"><GitBranch :size="17"/><span>Preview calculates the proposed changes using Olist. Your current charts stay in place until you apply the revision.</span></div>
      <button class="button primary revision-preview-button" :disabled="busy || !canPreview" @click="emit('preview', revisionPayload(form, evidence, condition))">Preview revision <ArrowRight :size="16"/></button>
    </template>

    <RevisionObservation v-else :key="`${proposal.id}-${proposal.status}`" :proposal-id="proposal.id" :proposal-status="proposal.status" surface="detail" :active="observationsEnabled" @observation="(name, details, clientMs) => emit('observation', name, details, clientMs)">
      <div class="proposal-state" :class="{ committed: proposal.status === 'committed' }"><Check v-if="proposal.status === 'committed'" :size="17"/><GitBranch v-else :size="17"/><strong>{{ proposal.status === 'committed' ? 'Applied to the canvas' : proposal.status === 'superseded' ? 'A newer request replaced this proposal' : 'Review the proposed change' }}</strong><span>From v{{ card.base_revision }}</span></div>
      <p v-if="card.question" class="proposal-question">{{ card.question }}</p>
      <div v-if="card.origin" class="binding-caption"><Link2 :size="14"/><span>SOURCE ORIGIN  /  {{ card.origin.label }}</span></div>
      <div v-if="card.evidence" class="binding-caption"><Link2 :size="14"/><span>{{ card.binding_applied ? 'Category identities are bound to the referenced chart.' : 'This proposal uses the explicitly supplied category values.' }}</span></div>
      <article v-for="change in card.changes" :key="change.view_id" class="revision-change-card"><div class="revision-change-heading"><span class="target-number">{{ String(change.number).padStart(2, '0') }}</span><strong>Chart {{ change.number }}</strong><span>{{ change.after_source.region || 'All regions' }}</span></div><div class="revision-change-columns"><div><span class="eyebrow">TARGETS &amp; CHANGES</span><div v-for="field in change.changed_fields" :key="field" class="revision-field-change"><strong>{{ sourceLabels[field] || humanize(field) }}</strong><span>{{ sourceValue(change.before_source, field) }} <ArrowRight :size="12"/> {{ sourceValue(change.after_source, field) }}</span></div><p v-if="!change.changed_fields.length" class="unchanged-note">No source conditions changed.</p></div><div><span class="eyebrow">KEPT CONDITIONS</span><dl class="kept-condition-values"><div v-for="entry in keptConditions(change)" :key="entry.field"><dt><Check :size="11"/> {{ entry.label }}</dt><dd>{{ entry.value }}</dd></div></dl><div v-if="change.released_fields?.length"><span class="eyebrow">RELEASED CONDITIONS</span><div class="kept-fields"><span v-for="field in change.released_fields" :key="field">{{ sourceLabels[field] || humanize(field) }}</span></div></div></div></div><div class="revision-members"><span class="eyebrow">RESULTING CATEGORIES</span><div class="member-tags"><span v-for="member in change.after_members" :key="member">{{ humanize(member) }}</span></div></div></article>
      <div class="revision-proposal-actions"><button class="button ghost" :disabled="busy" @click="emit('dismiss')"><RotateCcw :size="15"/>{{ pending ? 'Revise proposal' : 'Close proposal' }}</button><button v-if="pending" class="button primary" :disabled="busy" @click="emit('apply')"><Check :size="16"/> Apply revision</button></div>
    </RevisionObservation>
  </div>
</template>
