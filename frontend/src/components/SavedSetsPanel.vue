<script setup>
import { computed, ref } from 'vue'
import { Check, Layers, Save } from 'lucide-vue-next'
import { humanize, formatRange, metricNames } from '../chart.js'

const props = defineProps({ sets: Array, state: Object, selected: Array, entities: Object, seed: Object, busy: Boolean })
const emit = defineEmits(['save', 'apply'])
const name = ref('')
const currentSources = computed(() => props.state.views.filter(view => props.selected.includes(view.id) && view.source.dimension === 'category'))
const sourceId = ref(props.seed?.view_id || currentSources.value[0]?.id || '')
const source = computed(() => {
  if (props.seed) return props.seed
  const view = currentSources.value.find(view => view.id === sourceId.value)
  if (!view) return null
  return { revision: props.state.revision, view_id: view.id, number: view.number, title: view.title,
    source: view.source, members: props.entities[view.id]?.length ? [...props.entities[view.id]] : view.data.rows.map(row => row.label) }
})
const targets = computed(() => props.state.views.filter(view => props.selected.includes(view.id)))
function save() {
  emit('save', { name: name.value.trim(), revision: source.value.revision, view_id: source.value.view_id, members: [...source.value.members] })
  name.value = ''
}
</script>

<template>
  <div class="drawer-body saved-sets-body">
    <p class="drawer-intro">Reuse exact category members while keeping each target chart's current region, dates and measure.</p>
    <div class="set-session-note"><Layers :size="16"/><span>Saved in this session. Included in your session export.</span></div>
    <div class="section-label">Save categories</div>
    <template v-if="source">
      <label v-if="!seed && currentSources.length > 1" class="field"><span>Selected source chart</span><select v-model="sourceId" aria-label="Set source chart"><option v-for="view in currentSources" :value="view.id" :key="view.id">Chart {{ view.number }} · {{ view.title }}</option></select></label>
      <div class="set-origin"><strong>{{ seed ? 'Journey' : 'Current canvas' }} · Chart {{ source.number }} · v{{ source.revision }}</strong><p>{{ source.source.region || 'All regions' }} · {{ formatRange(source.source.start, source.source.end) }} · {{ metricNames[source.source.metric] }}</p><div class="member-tags"><span v-for="member in source.members" :key="member">{{ humanize(member) }}</span></div><small>{{ source.members.length }} exact members{{ !seed && entities[source.view_id]?.length ? ' · Selected chart marks' : '' }}</small></div>
      <label class="field"><span>Set name</span><input v-model="name" aria-label="Set name" placeholder="e.g. Earlier service categories" maxlength="100"/></label>
      <button class="button primary" :disabled="busy || !name.trim() || !source.members.length" @click="save"><Save :size="16"/> Save category set</button>
    </template>
    <p v-else class="field-help">Select a category chart on the canvas, or choose Save set in a Journey version. Select individual marks to save a subset.</p>
    <div class="section-label">Saved sets · {{ sets.length }}</div>
    <div class="set-targets"><strong>Apply to current selection</strong><p v-if="targets.length">Charts {{ targets.map(view => view.number).join(', ') }} · v{{ state.revision }}</p><p v-else>Select the current charts you want to update.</p><small>Only category membership changes. Other conditions stay as they are.</small></div>
    <p v-if="!sets.length" class="field-help">No saved sets in this session yet.</p>
    <article v-for="item in sets" :key="item.id" class="saved-set-card">
      <h3>{{ item.name }}</h3>
      <p class="set-provenance">Chart {{ item.evidence.number }} · v{{ item.evidence.revision }} · {{ item.evidence.source.region || 'All regions' }}<br>{{ formatRange(item.evidence.source.start, item.evidence.source.end) }} · {{ metricNames[item.evidence.source.metric] }}</p>
      <div class="member-tags"><span v-for="member in item.members" :key="member">{{ humanize(member) }}</span></div>
      <details class="set-identities"><summary>{{ item.members.length }} exact category IDs</summary><code>{{ item.members.join(', ') }}</code></details>
      <button class="button subtle" :aria-label="`Apply ${item.name} to selected charts`" :disabled="busy || !targets.length" @click="emit('apply', item.id)"><Check :size="15"/> Apply to {{ targets.length }} selected {{ targets.length === 1 ? 'chart' : 'charts' }}</button>
    </article>
  </div>
</template>
