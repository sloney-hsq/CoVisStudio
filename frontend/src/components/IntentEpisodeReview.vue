<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Download, LockKeyhole, Plus, RefreshCw } from 'lucide-vue-next'
import { eventText } from '../review.js'
import { blankCodingFiles, episodeBoundariesValid, episodeControls, outcomeLabel, understandingLabels } from '../intentReview.js'

const props = defineProps({ packet: { type: Object, required: true } })
const episodes = ref([]), selectedId = ref(''), blinded = ref(null)
const busy = ref(false), error = ref(''), notice = ref('')
const files = reactive({ coder_a: null, coder_b: null, adjudication: null })
const fileNames = reactive({ coder_a: '', coder_b: '', adjudication: '' })
const boundary = reactive({ onset_index: null, utterance_end_index: null, end_event_index: null })
const endpoint = reactive({ reviewer_id: '', reason: '' })
const understanding = reactive({ reviewer_id: '', reason: '', labels: Object.fromEntries(Object.keys(understandingLabels).map(key => [key, null])) })
const terminal = computed(() => props.packet.events.find(event => event.name === 'trial_finished'))
const selected = computed(() => episodes.value.find(item => item.packet_id === selectedId.value))
const base = computed(() => `/api/experiment/attempts/${props.packet.session.id}`)
const episodePath = computed(() => `${base.value}/intent-episodes/${selectedId.value}`)
const controls = computed(() => episodeControls(selected.value, episodes.value, terminal.value?.index))
const validBoundaries = computed(() => episodeBoundariesValid(props.packet.events, boundary))
const onsetEvents = computed(() => props.packet.events.filter(event =>
  ['speech_start', 'user_input', 'request_accepted', 'manual_edit_requested'].includes(event.name) && event.index <= (terminal.value?.index ?? -1)))
const inputEvents = computed(() => props.packet.events.filter(event =>
  ['user_transcript', 'request_accepted', 'user_input', 'speech_end', 'manual_edit_requested'].includes(event.name)))
const locked = computed(() => selected.value?.locked)
const canLock = computed(() => blinded.value && !locked.value && Object.values(files).every(Boolean))

watch(() => props.packet.session.id, () => {
  episodes.value = props.packet.intent_episodes || []
  selectedId.value = ''; blinded.value = null
  boundary.onset_index = null; boundary.utterance_end_index = null
  boundary.end_event_index = terminal.value?.index ?? null
  error.value = ''; notice.value = ''
}, { immediate: true })

async function api(path, body) {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  return data
}
async function action(fn) {
  busy.value = true; error.value = ''; notice.value = ''
  try { await fn() } catch (failure) { error.value = failure.message } finally { busy.value = false }
}
async function refresh() {
  episodes.value = (await api(base.value)).intent_episodes
}
async function load(id) {
  selectedId.value = id
  blinded.value = await api(`${base.value}/intent-episodes/${id}`)
  for (const key of Object.keys(files)) { files[key] = null; fileNames[key] = '' }
  endpoint.reviewer_id = ''; endpoint.reason = ''
  understanding.reviewer_id = ''; understanding.reason = ''
  for (const key of Object.keys(understanding.labels)) understanding.labels[key] = null
}
async function prepare() {
  const result = await api(`${base.value}/intent-episodes`, { ...boundary })
  await refresh(); await load(result.packet_id)
  notice.value = 'Blinded packet prepared. Independent coding remains pending.'
}
function download(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url)
}
function downloadTemplate(kind) {
  download(`${selectedId.value}-${kind}.json`, blankCodingFiles(selectedId.value)[kind])
}
async function loadFile(kind, event) {
  const file = event.target.files[0]
  if (!file) return
  files[kind] = null; fileNames[kind] = ''
  await action(async () => {
    files[kind] = JSON.parse(await file.text()); fileNames[kind] = file.name
    notice.value = `${file.name} loaded locally; no coding has been locked.`
  })
}
async function lock() {
  await api(`${episodePath.value}/lock`, { ...files })
  await refresh(); notice.value = 'Independent coding locked. Outcome scoring has not run.'
}
async function designate() {
  await api(`${episodePath.value}/primary`, { ...endpoint })
  await refresh(); notice.value = 'Final task endpoint designated before scoring.'
}
async function score() {
  await api(`${episodePath.value}/score`, {})
  await refresh(); notice.value = 'Analytical score recorded. Human understanding and listening remain separate.'
}
async function saveUnderstanding() {
  await api(`${episodePath.value}/understanding`, understanding)
  await refresh(); notice.value = 'Explicit human understanding assessment recorded.'
}
function describe(index) {
  const event = props.packet.events.find(item => item.index === index)
  return event ? `#${index} · ${event.name.replaceAll('_', ' ')}${eventText(event) ? ` · ${eventText(event)}` : ''}` : 'Choose a recorded event.'
}
</script>

<template>
  <section class="intent-review" aria-label="Independent intent review">
    <div class="archive-section-heading"><h3>Independent intent review</h3><button class="text-button" :disabled="busy" @click="action(refresh)"><RefreshCw :size="14"/> Refresh</button></div>
    <p class="field-help">Researcher workflow: distribute only the downloaded blinded packet and blank templates to two independent coders. Import their completed files here, lock the interpretation, then score the declared final task endpoint.</p>
    <p v-if="error" class="intent-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="intent-notice" role="status">{{ notice }}</p>

    <details :open="!episodes.length" class="intent-step">
      <summary>1. Prepare an episode from recorded events</summary>
      <div class="intent-fields">
        <label class="field"><span>Speech onset, text request or manual edit</span><select v-model="boundary.onset_index" aria-label="Intent onset event"><option :value="null">Choose actual input</option><option v-for="event in onsetEvents" :key="event.index" :value="event.index">{{ describe(event.index) }}</option></select></label>
        <label class="field"><span>Last input arrival event</span><input v-model.number="boundary.utterance_end_index" type="number" list="intent-input-events" aria-label="Intent input end event"/><small>{{ describe(boundary.utterance_end_index) }}</small></label>
        <datalist id="intent-input-events"><option v-for="event in inputEvents" :key="event.index" :value="event.index">{{ describe(event.index) }}</option></datalist>
        <label class="field"><span>Episode end event</span><input v-model.number="boundary.end_event_index" type="number" aria-label="Intent episode end event"/><small>{{ describe(boundary.end_event_index) }}</small></label>
      </div>
      <p class="field-help">The episode end defaults to task completion. A primary task endpoint must include that terminal event; the input boundary ends with the user's recorded words.</p>
      <button class="button subtle" :disabled="busy || !validBoundaries" @click="action(prepare)"><Plus :size="16"/> Prepare blinded packet</button>
    </details>

    <label v-if="episodes.length" class="field intent-chooser"><span>Prepared episode</span><select :value="selectedId" :disabled="busy" aria-label="Prepared intent episode" @change="action(() => load($event.target.value))"><option value="" disabled>Choose an episode</option><option v-for="episode in episodes" :key="episode.packet_id" :value="episode.packet_id">{{ episode.packet_id }} · {{ episode.intent_status.replaceAll('_', ' ') }}{{ episode.primary ? ' · final task endpoint' : '' }}</option></select></label>
    <p v-else class="field-help">No independent intent episodes have been prepared.</p>

    <template v-if="selected && blinded">
      <section class="intent-step">
        <h4>2. Distribute blinded materials and lock independent coding</h4>
        <p class="field-help">Input #{{ blinded.boundary.onset.index }}–#{{ blinded.boundary.utterance_arrival_end.index }} · Episode ends at #{{ selected.end_event_index }}. The packet excludes this request's model proposal, resulting charts and scores.</p>
        <button class="button subtle" @click="download(`${selectedId}-blinded-packet.json`, blinded)"><Download :size="16"/> Download blinded packet</button>
        <div class="intent-imports">
          <div v-for="(label, kind) in { coder_a: 'Coder A', coder_b: 'Coder B', adjudication: 'Adjudication' }" :key="kind" class="intent-import">
            <label class="field"><span>{{ label }} JSON</span><input :key="`${selectedId}-${kind}`" type="file" accept=".json,application/json" :disabled="busy || locked" :aria-label="`${label} JSON file`" @change="loadFile(kind, $event)"/><small v-if="fileNames[kind]">{{ fileNames[kind] }}</small></label>
            <button class="text-button" @click="downloadTemplate(kind)">Download blank {{ label.toLowerCase() }} template</button>
          </div>
        </div>
        <button class="button primary" :disabled="busy || !canLock" @click="action(lock)"><LockKeyhole :size="16"/> {{ locked ? 'Independent coding locked' : 'Lock imported coding' }}</button>
        <p class="field-help">Locking preserves both original codings and the adjudicator's stated interpretation. Unknown intent remains unknown.</p>
      </section>

      <section class="intent-step">
        <h4>3. Designate the final task endpoint, then score</h4>
        <p v-if="selected.primary" class="intent-notice">This is the designated final task endpoint.</p>
        <template v-else-if="!selected.scored">
          <div class="field-row"><label class="field"><span>Endpoint reviewer</span><input v-model="endpoint.reviewer_id" aria-label="Endpoint reviewer"/></label><label class="field"><span>Boundary rationale</span><input v-model="endpoint.reason" aria-label="Endpoint rationale"/></label></div>
          <button class="button subtle" :disabled="busy || !controls.designate || !endpoint.reviewer_id.trim() || !endpoint.reason.trim()" @click="action(designate)">Designate final task endpoint</button>
          <p class="field-help">Designation requires locked intent, task-terminal event #{{ terminal?.index }}, and no prior score or designated endpoint.</p>
        </template>
        <div class="intent-score-action"><button class="button primary" :disabled="busy || !controls.score" @click="action(score)">Score against locked intent</button><span>{{ selected.scored ? 'Score recorded' : 'Not scored' }}</span></div>
        <dl class="intent-outcomes"><div><dt>Intent</dt><dd>{{ selected.intent_status.replaceAll('_', ' ') }}</dd></div><div><dt>First committed revision</dt><dd>{{ outcomeLabel(selected.first_commit_correct) }}</dd></div><div><dt>Final revision</dt><dd>{{ outcomeLabel(selected.final_correct) }}</dd></div><div><dt>Human listening</dt><dd>{{ selected.human_listening || 'pending' }}</dd></div><div><dt>Repair cost</dt><dd>{{ selected.repair_cost ?? 'Unknown / pending' }}</dd></div></dl>
        <details v-if="selected.scored"><summary>Recorded analytical checks</summary><pre>{{ JSON.stringify(selected, null, 2) }}</pre></details>
      </section>

      <details class="intent-step">
        <summary>4. Record a separate human understanding assessment</summary>
        <p class="field-help">Use the participant's written response and stated evidence. A correct chart or played audio does not fill these labels.</p>
        <dl v-if="packet.task_response" class="intent-response"><div v-for="field in ['conclusion', 'rationale', 'object_origin', 'target_views', 'calculation_scope', 'kept_released']" :key="field"><dt>{{ field.replaceAll('_', ' ') }}</dt><dd>{{ packet.task_response[field] || 'Not provided' }}</dd></div></dl>
        <p v-else class="field-help">No participant response was saved. Understanding is unknown.</p>
        <template v-if="!selected.understanding_review">
          <label class="field"><span>Understanding reviewer</span><input v-model="understanding.reviewer_id" aria-label="Understanding reviewer"/></label>
          <div class="intent-labels"><label v-for="(label, field) in understandingLabels" :key="field" class="field"><span>{{ label }}</span><select v-model="understanding.labels[field]" :aria-label="`Understanding: ${label}`"><option :value="null">Unknown / unresolved</option><option :value="true">Correct</option><option :value="false">Incorrect</option></select></label></div>
          <label class="field"><span>Evidence and rationale</span><textarea v-model="understanding.reason" rows="3" aria-label="Understanding rationale"/></label>
          <button class="button subtle" :disabled="busy || !understanding.reviewer_id.trim() || !understanding.reason.trim()" @click="action(saveUnderstanding)">Record human assessment</button>
        </template>
        <template v-else><p>Reviewed by {{ selected.understanding_review.reviewer_id }} · {{ selected.understanding_review.reason }}</p><dl class="intent-outcomes"><div v-for="(label, field) in understandingLabels" :key="field"><dt>{{ label }}</dt><dd>{{ outcomeLabel(selected.understanding_review.labels[field]) }}</dd></div></dl></template>
      </details>
    </template>
  </section>
</template>

<style scoped>
.intent-review { max-width: 1050px; }
.intent-step { border: 1px solid #d8e1df; border-radius: 10px; padding: 16px; margin: 16px 0; }
.intent-step summary, .intent-step h4 { font-weight: 650; margin: 0 0 12px; }
.intent-step summary { cursor: pointer; }
.intent-fields, .intent-labels { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }
.intent-fields > :first-child { grid-column: 1 / -1; }
.intent-chooser { margin: 20px 0; }
.intent-imports { display: grid; gap: 16px; margin: 18px 0; }
.intent-import { min-width: 0; }
.intent-import input { max-width: 100%; }
.intent-score-action { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 16px; }
.intent-outcomes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.intent-outcomes dt, .intent-response dt { color: #586864; font-size: 12px; text-transform: capitalize; }
.intent-outcomes dd, .intent-response dd { margin: 4px 0 0; overflow-wrap: anywhere; }
.intent-response { display: grid; gap: 12px; padding: 12px; background: #f5f8f7; border-radius: 8px; }
.intent-error { color: #a53636; background: #fff1f0; padding: 10px 12px; border-radius: 6px; }
.intent-notice { color: #246b50; }
.intent-review small { overflow-wrap: anywhere; }
.intent-review pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 380px; overflow: auto; }
@media (max-width: 700px) { .intent-fields, .intent-labels, .intent-outcomes { grid-template-columns: 1fr; } }
</style>
