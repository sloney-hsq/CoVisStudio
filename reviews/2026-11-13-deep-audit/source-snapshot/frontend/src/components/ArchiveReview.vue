<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ArrowLeft, Check, FileText, Headphones, Image, Plus, Save, Trash2 } from 'lucide-vue-next'
import ChartCard from './ChartCard.vue'
import TaskBrief from './TaskBrief.vue'
import { humanize, metricNames, formatRange } from '../chart.js'
import { eventText, measuredEvents, nodeAtEvent, relativeEventTime } from '../review.js'

const props = defineProps({ packet: Object, busy: Boolean })
const emit = defineEmits(['back', 'save'])
const tab = ref('evidence'), allEvents = ref(false), selectedEvent = ref(null)
const selectedNodeId = ref(props.packet.nodes.at(-1)?.id || '')
const selectedImage = ref(''), saved = ref(false)
const draft = reactive({ reviewer_id: '', notes: '', interpretation: 'pending', spoken_consistency: 'pending', segments: [] })
const segment = reactive({ start_event_index: null, end_event_index: null, kind: 'unclear', reason: '' })
const measured = computed(() => measuredEvents(props.packet.events))
const timeline = computed(() => allEvents.value ? props.packet.events : measured.value)
const node = computed(() => props.packet.nodes.find(item => item.id === selectedNodeId.value))
const snapshot = computed(() => node.value ? props.packet.node_states[node.value.id] : null)
const audio = computed(() => props.packet.media.filter(item => item.kind === 'audio'))
const images = computed(() => props.packet.media.filter(item => item.kind === 'image'))
const image = computed(() => images.value.find(item => item.name === selectedImage.value))
const canAdd = computed(() => segment.start_event_index !== null && segment.end_event_index !== null && segment.end_event_index >= segment.start_event_index && segment.reason.trim())
const trial = computed(() => props.packet.trial_report)
const responseLabels = { conclusion: 'Conclusion', rationale: 'Evidence and rationale', object_origin: 'Category origin', calculation_scope: 'Calculation scope' }
watch(() => props.packet.review_drafts.length, () => { saved.value = true })
function inspect(event) {
  selectedEvent.value = event
  selectedNodeId.value = nodeAtEvent(props.packet.nodes, event)?.id || ''
}
function addSegment() {
  draft.segments.push({ ...segment, reason: segment.reason.trim() })
  segment.reason = ''; saved.value = false
}
function markBoundary(which) {
  segment[which] = selectedEvent.value.index
  tab.value = 'coding'
}
function save() {
  saved.value = false
  emit('save', JSON.parse(JSON.stringify(draft)))
}
</script>

<template>
  <div class="archive-review">
    <header class="archive-context">
      <button class="button ghost" @click="emit('back')"><ArrowLeft :size="16"/> All attempts</button>
      <div><strong>{{ packet.session.participant_id }} · Task {{ packet.session.assignment.trial_index }} of 4</strong><span>{{ humanize(packet.session.condition) }} · {{ humanize(packet.session.evidence_kind) }} · {{ packet.session.task_id }}</span></div>
      <span class="archive-pending">Human review pending</span>
    </header>
    <nav class="archive-tabs" aria-label="Archive sections">
      <button :class="{ active: tab === 'evidence' }" @click="tab = 'evidence'"><FileText :size="16"/> Task & evidence</button>
      <button :class="{ active: tab === 'media' }" @click="tab = 'media'"><Headphones :size="16"/> Transcript & recordings</button>
      <button :class="{ active: tab === 'coding' }" @click="tab = 'coding'"><Save :size="16"/> Coding drafts <span>{{ packet.review_drafts.length }}</span></button>
    </nav>

    <div class="archive-body">
      <aside class="archive-timeline">
        <div class="archive-section-heading"><h3>Recorded events</h3><span>{{ timeline.length }}</span></div>
        <label class="archive-toggle"><input type="checkbox" v-model="allEvents"/> Include setup and later review</label>
        <p class="field-help">Times are relative to Begin on the server clock. Select an event to inspect the state already committed at that point.</p>
        <div class="archive-events" role="list" aria-label="Recorded event timeline">
          <button v-for="event in timeline" :key="event.index" :class="{ active: selectedEvent?.index === event.index }" @click="inspect(event)" :aria-label="`Inspect event ${event.index}: ${humanize(event.name)}`">
            <span class="archive-event-meta">#{{ event.index }} <time>{{ relativeEventTime(event, packet.events) }}</time></span>
            <strong>{{ humanize(event.name) }}</strong><small v-if="eventText(event)">{{ eventText(event) }}</small>
          </button>
        </div>
        <div v-if="selectedEvent" class="archive-event-detail">
          <strong>Event #{{ selectedEvent.index }}</strong>
          <div v-if="measured.some(event => event.index === selectedEvent.index)" class="archive-boundary-actions"><button class="text-button" @click="markBoundary('start_event_index')">Use as span start</button><button class="text-button" @click="markBoundary('end_event_index')">Use as span end</button></div>
          <details><summary>Original event</summary><pre>{{ JSON.stringify(selectedEvent, null, 2) }}</pre></details>
        </div>
      </aside>

      <main class="archive-content">
        <template v-if="tab === 'evidence'">
          <div class="archive-outcome"><div><span>Chart requirements</span><strong>{{ trial?.outcome.technical_completed ? 'Met' : 'Not met' }}</strong></div><div><span>Submitted response</span><strong>{{ humanize(trial?.response_status || 'none') }}</strong></div><div><span>Trial status</span><strong>{{ humanize(trial?.outcome.status || packet.session.trial_status) }}</strong></div></div>
          <details class="archive-task"><summary>Business goal and task instructions</summary><p class="field-help">{{ packet.task_source === 'archive' ? 'Instructions saved with this attempt.' : 'Older attempt: instructions retrieved from the matching task materials.' }}</p><TaskBrief :task="packet.task"/></details>
          <section class="archive-response"><h3>Participant's written response</h3><p class="field-help">{{ packet.task_response ? `Saved for canvas v${packet.task_response.revision}. This text has not been graded.` : 'No written response was saved.' }}</p><dl v-if="packet.task_response"><div v-for="(label, field) in responseLabels" :key="field"><dt>{{ label }}</dt><dd>{{ packet.task_response[field] || 'Not provided' }}</dd></div></dl></section>
          <div class="archive-section-heading"><h3>Committed chart evidence</h3><label class="archive-version">Version<select v-model="selectedNodeId" aria-label="Archived canvas version"><option v-if="!node" value="">No committed state at this event</option><option v-for="item in packet.nodes" :key="item.id" :value="item.id">v{{ item.revision }} · {{ item.title }}</option></select></label></div>
          <p class="field-help">This view reconstructs saved chart data. Captured images are listed separately. Inspecting an archive does not restore or change the active workspace.</p>
          <template v-if="snapshot">
            <div class="archive-chart-grid"><ChartCard v-for="view in snapshot.views" :key="view.id" :view="view" :revision="snapshot.revision" readonly/></div>
            <details class="archive-details"><summary>Sources and member sets · v{{ snapshot.revision }}</summary><div v-for="view in snapshot.views" :key="view.id" class="archive-source"><strong>Chart {{ view.number }} · {{ metricNames[view.source.metric] }}</strong><p>{{ view.source.region }} · {{ formatRange(view.source.start, view.source.end) }} · {{ humanize(view.source.status) }}</p><p>{{ view.source.categories ? view.source.categories.map(humanize).join(', ') : `Top ${view.source.top_n} by ${humanize(view.source.rank_by)}` }}</p></div></details>
            <details v-if="node?.revision_card" class="archive-details"><summary>Recorded revision card</summary><pre>{{ JSON.stringify(node.revision_card, null, 2) }}</pre></details>
          </template>
          <p v-else class="archive-empty">No chart had been committed at the selected event.</p>
          <details class="archive-details"><summary>Technical checks and process report</summary><pre>{{ JSON.stringify(trial, null, 2) }}</pre></details>
        </template>

        <template v-if="tab === 'media'">
          <div class="archive-section-heading"><h3>Recorded conversation</h3><span>{{ packet.transcripts.length }} messages</span></div>
          <p class="field-help">Provider transcripts and saved audio are evidence for review. They do not establish what a person heard or understood.</p>
          <div v-if="packet.transcripts.length" class="archive-transcripts"><article v-for="(message, index) in packet.transcripts" :key="index"><header><strong>{{ message.role === 'user' ? 'User' : 'Assistant' }}</strong><button class="text-button" @click="inspect(packet.events.find(event => event.index === message.event_index))">Event #{{ message.event_index }}</button></header><p>{{ message.text }}</p></article></div><p v-else class="archive-empty">No transcript is recorded for this attempt.</p>
          <div class="archive-section-heading"><h3>Audio recordings</h3><span>{{ audio.length }} files</span></div>
          <div v-if="audio.length" class="archive-audio"><article v-for="item in audio" :key="item.name"><strong>{{ item.name.startsWith('input-') ? 'Microphone input' : 'Assistant output' }}</strong><small>{{ item.name }} · {{ item.duration_seconds.toFixed(2) }} s</small><audio controls preload="none" :src="item.url" :aria-label="`Play ${item.name}`"></audio><a :href="item.url" download>Download recording</a></article></div><p v-else class="archive-empty">No audio was recorded. Listening remains pending.</p>
          <div class="archive-section-heading"><h3><Image :size="16"/> Captured visual input</h3><span>{{ images.length }} images</span></div>
          <label v-if="images.length" class="field"><span>Recorded image</span><select v-model="selectedImage" aria-label="Recorded image"><option value="">Choose a captured image</option><option v-for="item in images" :key="item.name" :value="item.name">{{ item.name }}</option></select></label>
          <figure v-if="image" class="archive-image"><img :src="image.url" :alt="`Saved visual input: ${image.name}`"/><figcaption>{{ image.name }} · {{ packet.session.id }}</figcaption></figure><p v-if="!images.length" class="archive-empty">No image was captured in this attempt.</p>
        </template>

        <template v-if="tab === 'coding'">
          <div class="archive-section-heading"><h3>Manual coding draft</h3><span class="archive-pending">Not an approved score</span></div>
          <p class="field-help">Link a judgment to recorded events. Normal exploration and a deliberate change of direction are separate from repairing a misunderstanding. Visibility does not establish reading. Saving a draft leaves every human score pending.</p>
          <label class="field"><span>Reviewer label</span><input v-model="draft.reviewer_id" aria-label="Reviewer label" placeholder="e.g. R01"/></label>
          <div class="field-row"><label class="field"><span>Business interpretation</span><select v-model="draft.interpretation" aria-label="Draft business interpretation"><option value="pending">Pending</option><option value="supported">Supported by evidence</option><option value="unsupported">Not supported by evidence</option><option value="unclear">Unclear</option></select></label><label class="field"><span>Spoken consistency</span><select v-model="draft.spoken_consistency" aria-label="Draft spoken consistency"><option value="pending">Pending</option><option value="consistent">Consistent</option><option value="inconsistent">Inconsistent</option><option value="not_available">No speech available</option><option value="unclear">Unclear</option></select></label></div>
          <section class="archive-segment-form"><h4>Code an event span</h4><div class="field-row"><label class="field"><span>Start event</span><select v-model="segment.start_event_index" aria-label="Coding start event"><option :value="null">Choose event</option><option v-for="event in measured" :key="event.index" :value="event.index">#{{ event.index }} · {{ humanize(event.name) }}</option></select></label><label class="field"><span>End event</span><select v-model="segment.end_event_index" aria-label="Coding end event"><option :value="null">Choose event</option><option v-for="event in measured" :key="event.index" :value="event.index">#{{ event.index }} · {{ humanize(event.name) }}</option></select></label></div><label class="field"><span>Activity</span><select v-model="segment.kind" aria-label="Coding activity"><option value="unclear">Unclear</option><option value="repair">Repair of an error or misunderstanding</option><option value="exploration">Normal exploration</option><option value="intent_change">Deliberate change of intent</option></select></label><label class="field"><span>Evidence for this judgment</span><textarea v-model="segment.reason" rows="3" aria-label="Coding rationale" placeholder="Describe what in this span supports the code."/></label><button class="button subtle" :disabled="!canAdd" @click="addSegment"><Plus :size="16"/> Add coded span</button></section>
          <div class="archive-coded-spans"><article v-for="(item, index) in draft.segments" :key="index"><div><strong>#{{ item.start_event_index }}–#{{ item.end_event_index }} · {{ humanize(item.kind) }}</strong><p>{{ item.reason }}</p></div><button class="icon-button" :aria-label="`Remove coded span ${index + 1}`" @click="draft.segments.splice(index, 1)"><Trash2 :size="15"/></button></article></div>
          <label class="field"><span>Review notes</span><textarea v-model="draft.notes" rows="4" aria-label="Review draft notes" placeholder="Uncertainty, interpretation and evidence still needed."/></label>
          <div class="archive-save"><button class="button primary" :disabled="busy || !draft.reviewer_id.trim() || (!draft.notes.trim() && !draft.segments.length)" @click="save"><Save :size="16"/> Save coding draft</button><span v-if="saved" role="status"><Check :size="15"/> Draft saved · review still pending</span></div>
          <div class="archive-section-heading"><h3>Saved drafts</h3><span>{{ packet.review_drafts.length }}</span></div>
          <article v-for="item in [...packet.review_drafts].reverse()" :key="item.id" class="archive-saved-draft"><header><strong>{{ item.reviewer_id }}</strong><span>Draft · {{ new Date(item.at).toLocaleString('en-GB') }}</span></header><p>{{ item.notes }}</p><small>{{ humanize(item.interpretation) }} interpretation · {{ humanize(item.spoken_consistency) }} speech · {{ item.segments.length }} coded spans</small><details v-if="item.segments.length"><summary>View coded spans</summary><div v-for="(span, index) in item.segments" :key="index"><strong>#{{ span.start_event_index }}–#{{ span.end_event_index }} · {{ humanize(span.kind) }}</strong><p>{{ span.reason }}</p></div></details></article>
          <p v-if="!packet.review_drafts.length" class="archive-empty">No coding drafts have been saved.</p>
        </template>
      </main>
    </div>
  </div>
</template>
