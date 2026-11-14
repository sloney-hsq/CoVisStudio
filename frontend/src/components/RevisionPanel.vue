<script setup>
import { computed, reactive } from 'vue'
import { ArrowRight, Check, GitBranch, Link2 } from 'lucide-vue-next'
import { humanize, metricNames, formatRange } from '../chart.js'
import { revisionDefaults, revisionPayload } from '../revision.js'
import RevisionSupport from './RevisionSupport.vue'

const props = defineProps({ state: Object, evidence: Object, condition: String, proposal: Object, catalog: Object, selected: Array, seed: Object, sets: Array, busy: Boolean, observationsEnabled: Boolean })
const emit = defineEmits(['preview', 'apply', 'revise', 'close', 'observation'])
const form = reactive(props.seed ? JSON.parse(JSON.stringify(props.seed.form)) : revisionDefaults(props.selected, !!props.evidence))
const selectedEvidence = computed(() => {
  const saved = props.sets.find(item => `set:${item.id}` === form.candidate_id)
  return saved ? { ...saved.evidence, members: saved.members, set_name: saved.name } : props.evidence
})
const currentRegions = computed(() => {
  const targets = props.proposal ? props.proposal.card.view_ids : form.view_ids
  return [...new Set(props.state.views.filter(view => targets.includes(view.id)).map(view => view.source.region || 'All regions'))].join(' / ')
})
const canPreview = computed(() => form.view_ids.length && (form.member_action !== 'use_evidence' || selectedEvidence.value && (props.condition !== 'unbound_preview' || form.categories.length)))
function toggleTarget(id) { form.view_ids = form.view_ids.includes(id) ? form.view_ids.filter(value => value !== id) : [...form.view_ids, id] }
function chooseSource() {
  form.member_action = 'use_evidence'
  form.categories = [...selectedEvidence.value.members]
  delete form.extra_patch.categories; delete form.extra_patch.top_n
}
</script>

<template>
  <div class="drawer-body revision-body">
    <p class="drawer-intro">{{ evidence ? 'Bring categories from an earlier chart into the current analysis. Its filters stay in the past.' : 'Refine your current analysis. Conditions stay in place unless you explicitly change them.' }} Choose exactly which views should change.</p>
    <div v-if="condition !== 'direct' && !proposal" class="revision-reference-map">
      <div class="revision-reference-block">
        <span class="eyebrow"><Link2 :size="13"/> EVIDENCE FROM</span>
        <template v-if="selectedEvidence"><strong>{{ selectedEvidence.set_name ? `Saved set: ${selectedEvidence.set_name} · ` : '' }}{{ selectedEvidence.source.region || 'All regions' }} · Chart {{ selectedEvidence.number }} · v{{ selectedEvidence.revision }}</strong><p>{{ formatRange(selectedEvidence.source.start, selectedEvidence.source.end) }}</p><div class="member-tags"><span v-for="member in selectedEvidence.members" :key="member">{{ humanize(member) }}</span></div></template>
        <template v-else><strong>No historical evidence selected</strong><p>Open a Journey version to reference its categories.</p></template>
      </div>
      <ArrowRight :size="19" class="reference-arrow"/>
      <div class="revision-reference-block current-reference"><span class="eyebrow">APPLY TO</span><strong>{{ currentRegions || 'Choose target views' }} · Current v{{ state.revision }}</strong><p>Keep each view's current conditions unless you change them below.</p></div>
    </div>

    <template v-if="!proposal">
      <div class="section-label">Views to update</div>
      <div class="revision-targets"><button v-for="view in state.views" :key="view.id" :class="{ active: form.view_ids.includes(view.id) }" :aria-pressed="form.view_ids.includes(view.id)" @click="toggleTarget(view.id)"><span class="target-number">{{ String(view.number).padStart(2, '0') }}</span><span><strong>{{ view.title }}</strong><small>{{ view.source.region || 'All regions' }} · {{ metricNames[view.source.metric] }}</small></span><Check v-if="form.view_ids.includes(view.id)" :size="16"/></button></div>
      <div class="section-label">Comparison objects</div>
      <label v-if="evidence || sets.length" class="field"><span>Category source</span><select v-model="form.candidate_id" @change="chooseSource" aria-label="Revision category source"><option v-if="evidence" :value="seed?.form.candidate_id || ''">{{ evidence.title }} · v{{ evidence.revision }} · {{ evidence.members.length }} categories</option><option v-for="saved in sets.filter(item => `set:${item.id}` !== seed?.form.candidate_id)" :key="saved.id" :value="`set:${saved.id}`">Saved set: {{ saved.name }}</option></select><small>Choose a saved set, or reference another chart from Journey.</small></label>
      <div class="revision-membership">
        <label><input type="radio" v-model="form.member_action" value="keep_current"/><span><strong>Keep each view's selection</strong><small>Retain its current fixed members or ranking rule.</small></span></label>
        <label :class="{ unavailable: !selectedEvidence }"><input type="radio" v-model="form.member_action" value="use_evidence" :disabled="!selectedEvidence"/><span><strong>Use the referenced categories</strong><small>Take the objects from the earlier chart, not its filters.</small></span></label>
        <label><input type="radio" v-model="form.member_action" value="rerank"/><span><strong>Choose a new ranking</strong><small>Release the fixed set and calculate a new selection.</small></span></label>
      </div>
      <label v-if="condition === 'unbound_preview' && form.member_action === 'use_evidence'" class="field explicit-members"><span>Categories to apply</span><select multiple v-model="form.categories" aria-label="Explicit categories to apply"><option v-for="member in selectedEvidence.members" :key="member" :value="member">{{ humanize(member) }}</option></select><small>Select the exact categories to apply. Use Ctrl / Command for multiple selections.</small></label>
      <div v-if="form.member_action === 'rerank'" class="field-row"><label class="field"><span>Number of groups</span><input type="number" min="1" max="30" v-model.number="form.top_n"/></label><label class="field"><span>Rank by</span><select v-model="form.rank_by"><option v-for="(label, id) in metricNames" :key="id" :value="id">{{ label }}</option></select></label></div>
      <div class="section-label">Changes to current conditions</div>
      <div class="field-row"><label class="field"><span>Region</span><select v-model="form.region" aria-label="Revision region"><option value="">Keep current</option><option value="__all__">All regions</option><option v-for="region in catalog.states" :key="region" :value="region">{{ region }}</option></select></label><label class="field"><span>Measure</span><select v-model="form.metric" aria-label="Revision measure"><option value="">Keep current</option><option v-for="(label, id) in metricNames" :key="id" :value="id">{{ label }}</option></select></label></div>
      <div class="field-row"><label class="field"><span>From · blank keeps current</span><input type="date" v-model="form.start" aria-label="Revision start date"/></label><label class="field"><span>Until · exclusive</span><input type="date" v-model="form.end" aria-label="Revision end date"/></label></div>
      <label class="field"><span>Group by</span><select v-model="form.dimension" aria-label="Revision grouping"><option value="">Keep current</option><option value="category">Product category</option><option value="month">Purchase month</option><option value="state">Customer state</option></select></label><label class="field"><span>Order status</span><select v-model="form.status"><option value="">Keep current</option><option value="delivered">Delivered</option><option value="shipped">Shipped</option><option value="canceled">Canceled</option></select></label>
      <div class="data-note"><GitBranch :size="17"/><span>Preview calculates the proposed changes using Olist. Your current charts stay in place until you apply the revision.</span></div>
      <div class="revision-preview-footer"><span>Charts {{ state.views.filter(view => form.view_ids.includes(view.id)).map(view => view.number).join(', ') || '—' }} · {{ form.member_action === 'rerank' ? 'New ranking' : form.member_action === 'use_evidence' ? (selectedEvidence?.set_name || `Source v${selectedEvidence?.revision ?? '—'}`) : 'Keep current selection' }}</span><button class="button primary revision-preview-button" :disabled="busy || !canPreview" @click="emit('preview', revisionPayload(form, selectedEvidence, condition))">Preview revision <ArrowRight :size="16"/></button></div>
    </template>

    <RevisionSupport v-else :proposal="proposal" :state="state" :structured="condition !== 'direct'" :active="observationsEnabled" :busy="busy" @apply="emit('apply')" @revise="emit('revise')" @close="emit('close')" @observation="(name, details, clientMs) => emit('observation', name, details, clientMs)"/>
  </div>
</template>
