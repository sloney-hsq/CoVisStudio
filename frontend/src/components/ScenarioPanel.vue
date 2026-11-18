<script setup>
// Researcher-only: sets up a voice re-planning scenario and shows its private score.
// Ground truth never reaches this component; the server returns per-turn comparisons.
import { computed, onMounted, ref } from 'vue'
import { humanize } from '../chart.js'
import { causeLabel, timingLabel, viewSummary } from '../scenarios.js'

const props = defineProps({ session: Object, busy: Boolean })
const emit = defineEmits(['error', 'bootstrap'])
const scenarios = ref([])
const chosen = ref('S01')
const mode = ref('live_voice')
const condition = ref('bound_revision')
const score = ref(null)
const active = computed(() => scenarios.value.find(item => item.id === chosen.value))
const current = computed(() => props.session?.scenario?.id || null)

async function call(path, body) {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  return data
}
async function guarded(fn) { try { await fn() } catch (error) { emit('error', error.message) } }
onMounted(() => guarded(async () => { scenarios.value = (await call('/api/scenarios')).scenarios }))
const setup = () => guarded(async () => {
  score.value = null
  emit('bootstrap', await call(`/api/scenarios/${chosen.value}/setup`, { mode: mode.value, condition: condition.value }))
})
const evaluate = () => guarded(async () => { score.value = await call(`/api/scenarios/${current.value}/score`, {}) })
</script>

<template>
  <div class="drawer-body scenario-panel">
    <p class="drawer-intro">Diagnostic re-planning scenarios. Setup builds the history and current canvas; you then speak or type the scripted turns. Scores are researcher-only and never enter model context.</p>
    <div class="field-row">
      <label class="field"><span>Scenario</span><select v-model="chosen" aria-label="Scenario"><option v-for="item in scenarios" :key="item.id" :value="item.id">{{ item.id }} · {{ item.title }}</option></select></label>
      <label class="field"><span>Mode</span><select v-model="mode" aria-label="Scenario mode"><option value="live_voice">Live voice</option><option value="text">Text twin</option></select></label>
      <label class="field"><span>Condition</span><select v-model="condition" aria-label="Scenario condition"><option value="direct">Direct</option><option value="bound_revision">Bound revision</option></select></label>
    </div>
    <ol v-if="active" class="scenario-turns">
      <li v-for="turn in active.turns" :key="turn.turn" :class="turn.speaker">
        <span class="turn-label">T{{ turn.turn }} · {{ turn.speaker === 'user' ? timingLabel(turn.timing) : 'Assistant' }}</span>
        <p v-if="turn.speaker === 'user'">“{{ turn.text }}”</p>
        <p v-else class="muted">Assistant reply</p>
        <small v-if="turn.tags?.length">{{ turn.tags.join(' · ') }}</small>
      </li>
    </ol>
    <div class="scenario-actions">
      <button class="button primary" :disabled="busy || !active" @click="setup">Set up {{ chosen }}</button>
      <button class="button subtle" :disabled="busy || !current" @click="evaluate">Score current session{{ current ? ` (${current})` : '' }}</button>
    </div>
    <p class="field-help">Manual runs map turns in order of accepted requests. Driver runs supply exact turn windows. Spoken claims, clarifying questions and played-prefix members stay pending human coding.</p>
    <section v-if="score" class="scenario-score">
      <div class="section-label">Score · {{ score.scenario_id }} · {{ humanize(score.mapping) }}</div>
      <p><strong>{{ score.summary.correct }}</strong> of {{ score.summary.scored }} scored turns correct · terminal state {{ score.summary.terminal_state_correct === null ? 'unknown' : score.summary.terminal_state_correct ? 'correct' : 'incorrect' }}</p>
      <table>
        <thead><tr><th>Turn</th><th>Transcript</th><th>Action</th><th>Views</th><th>First cause</th></tr></thead>
        <tbody>
          <tr v-for="row in score.turns" :key="row.turn">
            <td>T{{ row.turn }}</td>
            <td>{{ row.transcript || '—' }}<small v-if="row.missing_critical_words?.length"> missing: {{ row.missing_critical_words.join(', ') }}</small></td>
            <td>{{ row.intermediate ? 'intermediate' : `${humanize(row.expected_action)} / ${humanize(row.observed_action || 'unknown')}` }}</td>
            <td>{{ viewSummary(row.views) }}</td>
            <td :class="{ ok: row.first_cause === null }">{{ causeLabel(row.first_cause) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.scenario-turns { list-style: none; padding: 0; margin: 12px 0; display: grid; gap: 6px; }
.scenario-turns li { padding: 8px 10px; border-radius: 8px; background: var(--surface-muted, #f4f6f5); }
.scenario-turns li.assistant { opacity: .75; }
.scenario-turns p { margin: 2px 0; }
.turn-label { font-size: 12px; font-weight: 600; letter-spacing: .02em; }
.scenario-actions { display: flex; gap: 8px; margin: 12px 0; }
.scenario-score table { width: 100%; border-collapse: collapse; font-size: 13px; }
.scenario-score th, .scenario-score td { text-align: left; padding: 6px; border-bottom: 1px solid #dfe5e2; vertical-align: top; }
.scenario-score td.ok { color: #1d6b4f; font-weight: 600; }
.scenario-score small { display: block; color: #8a3b12; }
</style>
