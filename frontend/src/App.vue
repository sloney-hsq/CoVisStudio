<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ArrowUp, ArrowUpRight, ArrowLeft, AudioLines, BarChart3, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, Clock3, Copy, Download, FileCheck2, GitBranch, History, LayoutDashboard, Link2, Loader2, Mic, MicOff, MoreHorizontal, Plus, Radio, RotateCcw, Settings2, SlidersHorizontal, Square, TextCursorInput, Trash2, Unlink, Volume2, VolumeX, X } from 'lucide-vue-next'
import ChartCard from './components/ChartCard.vue'
import RevisionPanel from './components/RevisionPanel.vue'
import RevisionSupport from './components/RevisionSupport.vue'
import SavedSetsPanel from './components/SavedSetsPanel.vue'
import TaskBrief from './components/TaskBrief.vue'
import ToolFeedback from './components/ToolFeedback.vue'
const ExperimentPanel = defineAsyncComponent(() => import('./components/ExperimentPanel.vue'))
const ArchiveReview = defineAsyncComponent(() => import('./components/ArchiveReview.vue'))
const TrialReview = defineAsyncComponent(() => import('./components/TrialReview.vue'))
const DeliveryReview = defineAsyncComponent(() => import('./components/DeliveryReview.vue'))
const ReviewObservations = defineAsyncComponent(() => import('./components/ReviewObservations.vue'))
const TaskResponseReview = defineAsyncComponent(() => import('./components/TaskResponseReview.vue'))
import './review.css'
import { trialTimeLeft, clockLabel, nextTrialIndex } from './experiment.js'
import './experiment.css'
import { humanize, metricNames, formatRange } from './chart.js'
import { Microphone, Speaker } from './audio.js'
import { ClockSync } from './clockSync.js'
import { visualContextLabel, referenceKey } from './visualContext.js'
import { toolFeedback, recordReceipt, markReceiptDisplayed } from './toolFeedback.js'
import { revisionSeed } from './revision.js'

const emptyEntities = Object.freeze([])
const state = ref({ revision: 0, title: 'Untitled dashboard', views: [] })
const catalog = ref({ states: [], categories: [], metrics: [] })
const settings = ref({ configured: false })
const tasks = ref([]), diagnosticTasks = ref([]), nodes = ref([]), session = ref({ mode: 'text' })
const experimentTasks = ref([]), formalTasks = ref([]), experimentPlan = ref(null), experimentAggregate = ref(null), archivePacket = ref(null)
const experimentProtocol = ref('formal'), voiceWindowUsed = ref(false)
const allocationSlot = ref(1), experimentEvidenceKind = ref('local_authored'), now = ref(Date.now())
let trialClock
const categorySets = ref([]), setSeed = ref(null)
const taskResponse = reactive({ conclusion: '', rationale: '', object_origin: '', calculation_scope: '', target_views: '', kept_released: '' }), taskResponseSaved = ref(false), taskResponseRevision = ref(null)
const conditions = ref([]), condition = ref('bound_revision'), evidence = ref(null), proposal = ref(null)
const revisionEditSeed = ref(null), authoredRevision = ref(null)
const selected = ref([]), entities = reactive({}), messages = ref([])
const mode = ref('text'), draft = ref(''), panel = ref(''), selectedTask = ref('starter')
const journeyTrack = ref(null)
const journeyOpen = ref(true), busy = ref(false), status = ref('ready'), error = ref('')
watch([() => nodes.value.length, journeyOpen], async () => {
  await nextTick()
  if (journeyTrack.value) journeyTrack.value.scrollLeft = journeyTrack.value.scrollWidth
})
const connected = ref(false), voiceConnected = ref(false), voiceConnecting = ref(false), recording = ref(false)
const microphoneLevel = ref(0), speechSeconds = ref(0), playing = ref(false)
const visualReceipt = ref(null)
const toolReceipt = ref(null), requestReceipts = reactive({}), currentRequestId = ref(null)
const historyDetail = ref(null), report = ref(null), expanded = ref(null), conversation = ref(null)
const historyMembers = ref({})
const media = ref([]), reportTab = ref('outcome')
const renderWaiters = []
const humanNotes = ref(''), humanClass = ref('pending'), reviewSaved = ref(false), participant = ref('')
const editId = ref(null), editor = reactive({}), editorInitial = ref({}), rendered = new Map(), cards = new Map(), emptyPresentedRevision = ref(null)
let socket, microphone, segmentTimer, speechClock, contextTimer
const clockSync = new ClockSync(send)
let clientEventSequence = 0
const speaker = new Speaker((name, details) => {
  playing.value = name === 'playback_start' ? true : name === 'playback_end' ? false : playing.value
  log(name, details)
}, (responseId, url) => {
  const message = messages.value.find(item => item.id === responseId)
  if (message) message.audio = url
})
const modeItems = [{ id: 'text', title: 'Text', icon: TextCursorInput }, { id: 'push_to_talk', title: 'Push to talk', icon: Mic }, { id: 'live_voice', title: 'Live voice', icon: AudioLines }]
const currentMode = computed(() => modeItems.find(item => item.id === mode.value))
const currentTask = computed(() => [...tasks.value, ...diagnosticTasks.value, ...experimentTasks.value, ...formalTasks.value].find(task => task.id === session.value.task_id))
const assignment = computed(() => session.value.assignment)
const formalSession = computed(() => assignment.value?.protocol === 'covis-formal-study-0.1')
const participantSession = computed(() => !!assignment.value && session.value.evidence_kind === 'participant')
const trialLocked = computed(() => assignment.value && session.value.trial_status !== 'running')
const trialRunning = computed(() => assignment.value && session.value.trial_status === 'running')
const preparingTrial = computed(() => !!assignment.value && session.value.trial_status === 'ready')
const timeLeft = computed(() => assignment.value ? trialTimeLeft(assignment.value, session.value.trial_started_at, now.value) : 0)
const nextAssigned = computed(() => assignment.value ? nextTrialIndex(assignment.value) : null)
const selectedViews = computed(() => state.value.views.filter(view => selected.value.includes(view.id)))
const revisionAvailable = computed(() => session.value.condition !== 'direct')
const activeEvidence = computed(() => proposal.value ? proposal.value.card.evidence : revisionEditSeed.value?.evidence || evidence.value)
const sharedScope = computed(() => {
  const views = state.value.views
  if (!views.length) return []
  const source = views[0].source
  const result = []
  if (views.every(view => view.source.region === source.region)) result.push(source.region ? `${source.region} region` : 'All regions')
  if (views.every(view => view.source.start === source.start && view.source.end === source.end)) result.push(formatRange(source.start, source.end))
  if (views.every(view => view.source.status === source.status)) result.push(`${humanize(source.status)} orders`)
  if (source.categories && views.every(view => JSON.stringify(view.source.categories) === JSON.stringify(source.categories))) result.push(`${source.categories.length} shared categories`)
  return result
})
const canSend = computed(() => draft.value.trim() && connected.value && !voiceConnected.value && !voiceConnecting.value && !trialLocked.value)
const visualLabel = computed(() => visualContextLabel(reference(), visualReceipt.value, state.value.views.length))
const connectionLabel = computed(() => settings.value.connection_mode === 'disabled' ? 'Local review · model calls disabled' : voiceConnected.value ? 'Qwen voice connected' : voiceConnecting.value ? 'Connecting Qwen voice' : settings.value.configured ? 'Qwen configured · not connected' : 'Qwen key not configured')
const chartTypes = ['bar', 'line', 'area', 'pie', 'scatter', 'heatmap']
const editorChanged = computed(() => !editId.value || JSON.stringify(editor) !== JSON.stringify(editorInitial.value))
const palette = ['#238579', '#547caa', '#c28753', '#806b9c', '#b66870', '#3d5664']
const fieldOptions = computed(() => catalog.value.categories.map(value => typeof value === 'string' ? { id: value, label: humanize(value) } : { id: value.id || value.value, label: value.label || humanize(value.id || value.value) }))

async function api(path, body) {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  return data
}
async function action(fn) {
  error.value = ''; busy.value = true
  try { return await fn() } catch (e) { error.value = e.message } finally { busy.value = false }
}
function send(event) { socket.send(JSON.stringify(event)) }
function log(name, details = {}, clientMs = performance.now()) {
  if (connected.value) send({ type: 'event', name, client_ms: clientMs,
    client_clock_id: clockSync.clockId, client_event_id: `${clockSync.clockId}:${++clientEventSequence}`,
    session_id: session.value.id, details })
}
function chartTelemetry(event) { log(event.name, event.details, event.client_ms) }
function chartRenderTelemetry(details) { log('chart_rendered', details, details.render_completed_client_ms) }
function reference() {
  return { revision: state.value.revision, view_ids: [...selected.value], entities: JSON.parse(JSON.stringify(entities)) }
}
function hydrate(data) {
  if (session.value.id !== data.session.id) { expanded.value = null; visualReceipt.value = null; toolReceipt.value = null; currentRequestId.value = null; revisionEditSeed.value = null; authoredRevision.value = null; emptyPresentedRevision.value = null; Object.keys(requestReceipts).forEach(key => delete requestReceipts[key]) }
  state.value = data.state; catalog.value = data.catalog; settings.value = data.settings
  tasks.value = data.tasks; diagnosticTasks.value = data.diagnostic_tasks || []; session.value = data.session; nodes.value = data.nodes
  clockSync.reset(data.session.id)
  experimentTasks.value = data.experiment_tasks || []
  formalTasks.value = data.formal_tasks || []
  voiceWindowUsed.value = !!data.session.voice_window_used
  if (data.session.assignment) {
    allocationSlot.value = data.session.assignment.participant_slot
    participant.value = data.session.participant_id
    experimentEvidenceKind.value = data.session.evidence_kind
    experimentProtocol.value = data.session.assignment.protocol === 'covis-formal-study-0.1' ? 'formal' : 'authored'
  }
  categorySets.value = data.category_sets || []
  for (const field of Object.keys(taskResponse)) taskResponse[field] = data.task_response?.[field] || ''
  taskResponseSaved.value = !!data.task_response
  taskResponseRevision.value = data.task_response?.revision ?? null
  mode.value = data.session.mode
  conditions.value = data.conditions; condition.value = data.session.condition
  evidence.value = data.evidence; proposal.value = data.proposal
  report.value = data.report || null
}
function applyState(data) {
  if (data.state.revision < state.value.revision) return
  if (report.value?.revision !== data.state.revision) report.value = null
  state.value = data.state
  if (expanded.value && !state.value.views.some(view => view.id === expanded.value)) expanded.value = null
  if (data.node && !nodes.value.some(node => node.id === data.node.id)) nodes.value.push(data.node)
  selected.value = selected.value.filter(id => state.value.views.some(view => view.id === id))
  for (const id of Object.keys(entities)) {
    const view = state.value.views.find(v => v.id === id)
    if (!view) delete entities[id]
    else entities[id] = entities[id].filter(label => view.data.rows.some(row => row.label === label))
  }
  if (!state.value.views.length) presentEmptyCanvas(data.state.revision)
}
async function presentEmptyCanvas(revision) {
  await nextTick()
  if (state.value.revision !== revision || state.value.views.length || emptyPresentedRevision.value === revision) return
  emptyPresentedRevision.value = revision
  log('canvas_rendered', { revision, empty: true })
  markReceiptDisplayed(requestReceipts, revision)
  if (toolReceipt.value?.revision === revision) toolReceipt.value.displayed = true
  renderWaiters.splice(0).forEach(resolve => resolve())
  queueContext()
}
function appendMessage(role, text, id) {
  messages.value.push({ id: id || crypto.randomUUID(), role, text, created: Date.now() })
  scrollConversation()
}
function acceptRequest(event) {
  currentRequestId.value = event.request_id; toolReceipt.value = null
  let turn = messages.value.find(item => item.role === 'user' && item.request_id === event.request_id)
  if (!turn) turn = [...messages.value].reverse().find(item => item.role === 'user' && !item.request_id)
  if (turn) turn.request_id = event.request_id
  else if (event.text) messages.value.push({ id: crypto.randomUUID(), role: 'user', text: event.text, request_id: event.request_id, created: Date.now() })
}
function receiptForMessage(message) {
  if (!message.request_id) return null
  const turns = messages.value.filter(item => item.request_id === message.request_id)
  return turns.at(-1)?.id === message.id ? requestReceipts[message.request_id] : null
}
function receiveReceipt(event) {
  if (!toolFeedback(event)) return
  const displayed = event.revision === state.value.revision && (state.value.views.length ? state.value.views.every(view => rendered.get(view.id) === event.revision) : emptyPresentedRevision.value === event.revision)
  if (event.request_id) {
    recordReceipt(requestReceipts, event)
    if (displayed) markReceiptDisplayed(requestReceipts, event.revision)
  } else toolReceipt.value = { ...event, displayed: !!event.committed && displayed }
}
function assistant(event, done) {
  if (done && !event.text) return
  let message = messages.value.find(item => item.id === event.response_id)
  if (!message) { message = { id: event.response_id, role: 'assistant', text: '', request_id: event.request_id || currentRequestId.value, created: Date.now() }; messages.value.push(message) }
  message.text = done ? event.text : message.text + event.text
  scrollConversation()
}
async function scrollConversation() { await nextTick(); conversation.value?.scrollTo({ top: conversation.value.scrollHeight, behavior: 'smooth' }) }
async function showRevision() {
  await nextTick()
  const container = conversation.value, support = container?.querySelector('.revision-support')
  if (support) container.scrollTop += support.getBoundingClientRect().top - container.getBoundingClientRect().top
}
async function receive(event) {
  switch (event.type) {
    case 'clock_pong': clockSync.acceptPong(event); break
    case 'bootstrap': hydrate(event); break
    case 'state': applyState(event); break
    case 'trial_finished': recordResponseDraft(); session.value = event.session; report.value = event.report; panel.value = participantSession.value ? 'complete' : 'report'; reportTab.value = 'outcome'; break
    case 'evidence': evidence.value = event.evidence; break
    case 'category_sets': categorySets.value = event.category_sets; break
    case 'proposal': proposal.value = event.proposal; if (event.proposal) showRevision(); break
    case 'status': status.value = event.status; break
    case 'request_accepted': acceptRequest(event); break
    case 'request_outcome': receiveReceipt(event); break
    case 'tool_result': receiveReceipt(event); break
    case 'tool_failed': receiveReceipt({ ...event, status: 'failed' }); break
    case 'visual_context':
      if (referenceKey(event.reference) === referenceKey(reference())) visualReceipt.value = event
      break
    case 'assistant_delta': assistant(event, false); break
    case 'assistant_done': assistant(event, true); break
    case 'user_transcript': {
      const turn = messages.value.find(item => item.role === 'user' && item.request_id === event.request_id)
      if (turn) turn.text = event.text
      else { appendMessage('user', event.text, event.item_id); messages.value.at(-1).request_id = event.request_id || currentRequestId.value }
      break
    }
    case 'audio': await speaker.append(event); break
    case 'audio_end': speaker.end(event.response_id); break
    case 'response_end': speaker.end(event.response_id); status.value = voiceConnected.value ? 'listening' : 'ready'; break
    case 'stop_audio': speaker.stop(); playing.value = false; break
    case 'voice_ready':
      voiceConnecting.value = false; voiceConnected.value = true
      if (event.session) session.value = event.session
      if (formalSession.value) voiceWindowUsed.value = event.voice_window_used ?? true
      microphone.start(mode.value === 'push_to_talk' ? 10 : null); recording.value = true; startSegmentClock()
      log('recording_start', { mode: mode.value, reference: reference() })
      break
    case 'voice_closed':
      await closeMicrophone(); voiceConnected.value = false; voiceConnecting.value = false; status.value = 'ready'
      if (event.session) { session.value = event.session; voiceWindowUsed.value = !!event.session.voice_window_used }
      if (event.voice_window_used !== undefined) voiceWindowUsed.value = event.voice_window_used
      break
    case 'speech_start':
      toolReceipt.value = null; currentRequestId.value = null
      speechSeconds.value = 0; clearInterval(speechClock)
      speechClock = setInterval(() => speechSeconds.value += 0.1, 100)
      log('speech_reference', reference()); await updateContext()
      break
    case 'speech_end': clearInterval(speechClock); speechSeconds.value = 0; break
    case 'error': error.value = event.message; voiceConnecting.value = false; status.value = 'ready'; if (!voiceConnected.value) await closeMicrophone(); break
  }
}
function selectView(id) {
  selected.value = selected.value.includes(id) ? selected.value.filter(value => value !== id) : [...selected.value, id]
  if (!selected.value.includes(id) && entities[id]) { rendered.delete(id); delete entities[id] }
  log('selection', reference()); queueContext()
}
function selectEntity(id, label) {
  if (!selected.value.includes(id)) selected.value.push(id)
  rendered.delete(id)
  const values = entities[id] || []
  entities[id] = values.includes(label) ? values.filter(value => value !== label) : [...values, label]
  log('selection', reference()); queueContext()
}
function clearSelection() { selected.value = []; Object.keys(entities).forEach(key => { rendered.delete(key); delete entities[key] }); log('selection', reference()); queueContext() }
function chartRendered(details) {
  if (details.revision !== state.value.revision) return
  rendered.set(details.view_id, details.revision)
  chartRenderTelemetry(details)
  if (state.value.views.every(view => rendered.get(view.id) === state.value.revision)) {
    markReceiptDisplayed(requestReceipts, details.revision)
    if (toolReceipt.value?.revision === details.revision) toolReceipt.value.displayed = true
    renderWaiters.splice(0).forEach(resolve => resolve())
    queueContext()
  }
}
function queueContext() { clearTimeout(contextTimer); contextTimer = setTimeout(updateContext, 100) }
function captureCanvas(refSnapshot) {
  const views = [...state.value.views]
  const selectedIds = refSnapshot.view_ids
  if (!views.length) return ''
  const grid = document.querySelector('.chart-grid')
  const gridBox = grid.getBoundingClientRect(), scale = Math.min(1, 1360 / gridBox.width)
  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(gridBox.width * scale); canvas.height = Math.ceil(gridBox.height * scale + 52)
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#f4f5f1'; ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#183541'; ctx.font = '18px Segoe UI'; ctx.fillText(`${state.value.title} · Version ${state.value.revision}`, 16, 32)
  const frames = views.map(view => {
    const card = grid.querySelector(`[data-view-id="${view.id}"]`), box = card.getBoundingClientRect(), plot = card.querySelector('.chart-plot').getBoundingClientRect()
    return { view, canvas: cards.get(view.id).canvas(), x: (box.x - gridBox.x) * scale, y: (box.y - gridBox.y) * scale + 52, width: box.width * scale, height: box.height * scale, px: (plot.x - gridBox.x) * scale, py: (plot.y - gridBox.y) * scale + 52, pw: plot.width * scale, ph: plot.height * scale }
  })
  for (const frame of frames) {
      const { view, x, y, width, height, px, py, pw, ph } = frame
      ctx.fillStyle = '#fff'; ctx.fillRect(x, y, width, height)
      ctx.strokeStyle = selectedIds.includes(view.id) ? '#238579' : '#e0e7dc'; ctx.lineWidth = selectedIds.includes(view.id) ? 2 : 1
      ctx.strokeRect(x + 1, y + 1, width - 2, height - 2)
      ctx.fillStyle = '#183541'; ctx.font = `bold ${Math.max(12, 16 * scale)}px Segoe UI`; ctx.fillText(`${view.number}. ${view.title}`, x + 15, y + 27, width - 30)
      ctx.font = `${Math.max(10, 12 * scale)}px Segoe UI`; ctx.fillStyle = '#66747d'; ctx.fillText(`${view.source.region || 'All regions'} · ${formatRange(view.source.start, view.source.end)}`, x + 15, y + 47, width - 30)
      ctx.drawImage(frame.canvas, px, py, pw, ph)
      ctx.fillText(view.source.categories ? 'Fixed categories' : `Ranked by ${metricNames[view.source.rank_by]}`, x + 15, y + height - 14, width - 30)
  }
  let encoded = canvas.toDataURL('image/jpeg', .68)
  if (encoded.length > 250 * 1024) {
    const smaller = document.createElement('canvas'); smaller.width = canvas.width * .7; smaller.height = canvas.height * .7
    smaller.getContext('2d').drawImage(canvas, 0, 0, smaller.width, smaller.height)
    encoded = smaller.toDataURL('image/jpeg', .6)
  }
  return encoded.split(',')[1]
}
async function waitForRendered() {
  await nextTick()
  if (state.value.views.every(view => rendered.get(view.id) === state.value.revision)) return
  await new Promise(resolve => renderWaiters.push(resolve))
}
async function updateContext() {
  if (!connected.value) return
  await waitForRendered()
  const refSnapshot = reference()
  const image = captureCanvas(refSnapshot)
  const context = { reference: refSnapshot, image, captured_client_ms: performance.now(),
    client_clock_id: clockSync.clockId }
  send({ type: 'context', ...context })
  return context
}
async function sendText() {
  if (!canSend.value) return
  if (!settings.value.configured) { showConnectionIssue(); return }
  await speaker.prepare(); const context = await updateContext()
  const text = draft.value.trim(); draft.value = ''
  toolReceipt.value = null; currentRequestId.value = null
  appendMessage('user', text)
  send({ type: 'text', text, ...context })
  status.value = 'thinking'; log('text_submit', { characters: text.length })
}
function onComposerKey(event) { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); action(sendText) } }
async function setMode(value) {
  if (voiceConnected.value || voiceConnecting.value) await stopVoice()
  mode.value = value
  log('mode_selected', { mode: value })
}
async function startVoice() {
  if (!settings.value.configured) { showConnectionIssue(); return }
  voiceConnecting.value = true
  try {
    await speaker.prepare()
    microphone = new Microphone((data, meta) => send({ type: 'audio', data, ...meta }), level => { microphoneLevel.value = level }, () => action(submitVoice), clockSync.clockId)
    await microphone.prepare(); const context = await updateContext()
    send({ type: 'voice_start', mode: mode.value, ...context })
  } catch (error) {
    await closeMicrophone(); voiceConnecting.value = false
    throw error
  }
}
function showConnectionIssue() {
  if (participantSession.value) error.value = 'The assistant is unavailable. Please ask the researcher for help.'
  else panel.value = 'settings'
}
function startSegmentClock() {
  clearInterval(segmentTimer); speechSeconds.value = 0
  if (mode.value !== 'push_to_talk') return
  const started = performance.now()
  segmentTimer = setInterval(() => {
    speechSeconds.value = (performance.now() - started) / 1000
  }, 100)
}
async function submitVoice() {
  clearInterval(segmentTimer)
  await microphone.pause(); recording.value = false; speechSeconds.value = 0
  send({ type: 'voice_commit' }); status.value = 'thinking'; log('recording_end', { mode: mode.value })
}
async function resumeVoice() {
  await updateContext(); microphone.start(10); recording.value = true; startSegmentClock()
  log('recording_start', { mode: mode.value, reference: reference() })
}
async function closeMicrophone() {
  clearInterval(segmentTimer); clearInterval(speechClock)
  const current = microphone; microphone = null
  recording.value = false; speechSeconds.value = 0
  await current?.close()
}
async function stopVoice() {
  await closeMicrophone(); send({ type: 'voice_stop' }); speaker.stop(); playing.value = false
  voiceConnected.value = false; voiceConnecting.value = false; status.value = 'ready'
}
async function voiceClick() {
  if (!voiceConnected.value) await startVoice()
  else if (mode.value === 'push_to_talk') recording.value ? await submitVoice() : await resumeVoice()
  else await stopVoice()
}
function stopSpeaking() { speaker.stop(); playing.value = false; send({ type: 'stop_speaking' }) }
function cancel() { speaker.stop(); playing.value = false; send({ type: 'cancel' }); status.value = voiceConnected.value ? 'listening' : 'ready' }
async function openSession(taskId = selectedTask.value) {
  await stopIfConnected()
  const data = await api('/api/session', { mode: mode.value, condition: condition.value, task_id: taskId, participant_id: participant.value })
  clearSelection(); messages.value = []; historyDetail.value = null; report.value = null; rendered.clear()
  hydrate(data); panel.value = ''; error.value = ''
}
async function tool(name, args) {
  const data = await api('/api/tools', { name, arguments: args, reference: reference() })
  applyState(data); return data
}
function openEditor(id = null) {
  editId.value = id
  if (id && !selected.value.includes(id)) { selected.value = [id]; Object.keys(entities).forEach(key => delete entities[key]) }
  const view = state.value.views.find(view => view.id === id)
  const values = view ? { title: view.title, chart_type: view.chart_type, ...view.source, ...view.style, membership: view.source.categories ? 'fixed' : 'ranked' } : {
    title: 'Orders by category', chart_type: 'bar', metric: 'orders', dimension: 'category', region: 'SP', start: '2017-01-01', end: '2018-01-01', status: 'delivered', categories: null, top_n: 5, rank_by: 'orders', color: '#238579', show_labels: false, sort: 'source', membership: 'ranked'
  }
  Object.keys(editor).forEach(key => delete editor[key])
  Object.assign(editor, JSON.parse(JSON.stringify(values))); editorInitial.value = JSON.parse(JSON.stringify(values))
  panel.value = 'edit'; log('inspector_open', { view_id: id })
}
function fixCurrentMembers() {
  const view = state.value.views.find(view => view.id === editId.value)
  editor.categories = [...(view.source.dimension === 'category' ? (entities[editId.value]?.length ? entities[editId.value] : view.data.rows.map(row => row.label)) : (view.source.categories || []))]
  editor.membership = 'fixed'; editor.top_n = null
}
async function applyEditor() {
  const sourceKeys = ['metric', 'dimension', 'region', 'start', 'end', 'status', 'categories', 'top_n', 'rank_by']
  const styleKeys = ['color', 'show_labels', 'sort']
  const value = JSON.parse(JSON.stringify(editor))
  if (value.membership === 'ranked') value.categories = null
  if (value.membership === 'fixed') value.top_n = null
  value.region ||= null
  const changed = key => JSON.stringify(value[key]) !== JSON.stringify(editorInitial.value[key])
  const source = Object.fromEntries(sourceKeys.filter(key => !editId.value || changed(key)).map(key => [key, value[key]]))
  const style = Object.fromEntries(styleKeys.filter(key => !editId.value || changed(key)).map(key => [key, value[key]]))
  if (!editId.value) await tool('create_chart', { title: value.title, chart_type: value.chart_type, source, style })
  else {
    const patch = {}
    if (changed('title')) patch.title = value.title
    if (changed('chart_type')) patch.chart_type = value.chart_type
    if (Object.keys(source).length) patch.source = source
    if (Object.keys(style).length) patch.style = style
    await tool('edit_charts', { view_ids: [...selected.value], patch })
  }
  panel.value = ''
}
async function removeSelected() { await tool('remove_charts', { view_ids: [...selected.value] }); clearSelection(); panel.value = '' }
async function arrange(columns = state.value.layout?.columns || 3, ids = state.value.views.map(view => view.id)) { await tool('arrange_charts', { view_ids: ids, columns }) }
async function moveChart(id, direction) {
  const ids = state.value.views.map(view => view.id), index = ids.indexOf(id), target = index + direction
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  await arrange(state.value.layout?.columns || 3, ids)
}
async function undo() { applyState(await api('/api/undo', {})) }
async function inspectNode(node) {
  historyDetail.value = await api(`/api/nodes/${node.id}`)
  historyMembers.value = Object.fromEntries(historyDetail.value.state.views.map(view => [view.id, view.data.rows.map(row => row.label)]))
  panel.value = 'history'; log('history_open', { node_id: node.id })
}
function toggleHistoryMember(viewId, member) {
  const members = historyMembers.value[viewId]
  historyMembers.value[viewId] = members.includes(member) ? members.filter(value => value !== member) : [...members, member]
}
async function restoreNode() { applyState(await api(`/api/nodes/${historyDetail.value.node.id}/restore`, {})); panel.value = '' }
async function useEvidence(view) {
  const data = await api('/api/evidence', { revision: historyDetail.value.state.revision, view_id: view.id, members: historyMembers.value[view.id] })
  evidence.value = data.evidence; proposal.value = data.proposal
  if (revisionEditSeed.value) { revisionEditSeed.value.evidence = data.evidence; revisionEditSeed.value.form.candidate_id = ''; revisionEditSeed.value.form.member_action = 'use_evidence' }
  panel.value = ''; log('evidence_selected_ui', { revision: evidence.value.revision, view_id: view.id })
}
async function clearEvidence() {
  const data = await api('/api/evidence', { clear: true })
  evidence.value = data.evidence; proposal.value = data.proposal
  report.value = data.report || null
}
function openRevision() {
  panel.value = 'revision'
  log('revision_panel_open', { evidence: evidence.value, target_view_ids: [...selected.value] })
  if (proposal.value) log('revision_card_opened', { proposal_id: proposal.value.id, surface: 'detail' })
}
async function previewRevision(payload) {
  const data = await api('/api/revisions/preview', payload)
  proposal.value = data.proposal
  authoredRevision.value = { proposal_id: data.proposal.id, payload: JSON.parse(JSON.stringify(payload)) }
  revisionEditSeed.value = null
  panel.value = ''
  showRevision()
}
async function applyRevision() {
  log('revision_confirmation_clicked', { proposal_id: proposal.value.id })
  const data = await api(`/api/revisions/${proposal.value.id}/apply`, {})
  applyState(data); proposal.value = data.proposal
  log('revision_applied_ui', { proposal_id: proposal.value.id, revision: state.value.revision })
}
async function reviseProposal() {
  const current = proposal.value
  revisionEditSeed.value = revisionSeed(current, authoredRevision.value?.proposal_id === current.id ? authoredRevision.value.payload : null)
  log('revision_card_revision_requested', { proposal_id: current.id, proposal_status: current.status })
  const data = await api(`/api/revisions/${current.id}/dismiss`, {})
  proposal.value = data.proposal
  panel.value = 'revision'
}
async function closeProposal() {
  log('revision_panel_closed', { proposal_id: proposal.value.id, proposal_status: proposal.value.status })
  const data = await api(`/api/revisions/${proposal.value.id}/dismiss`, {})
  proposal.value = data.proposal
  revisionEditSeed.value = null
  if (panel.value === 'revision') panel.value = ''
}
function openSavedSets(view = null) {
  setSeed.value = view ? { revision: historyDetail.value.state.revision, view_id: view.id, number: view.number,
    title: view.title, source: view.source, members: [...historyMembers.value[view.id]] } : null
  panel.value = 'sets'
}
async function saveCategorySet(payload) {
  const data = await api('/api/category-sets', payload)
  categorySets.value = data.category_sets
}
async function applyCategorySet(id) {
  const data = await api(`/api/category-sets/${id}/apply`, { view_ids: [...selected.value] })
  applyState(data); panel.value = ''
}
async function saveTaskResponse() {
  const data = await api('/api/task-response', responsePayload())
  for (const field of Object.keys(data.response)) if (field in taskResponse) taskResponse[field] = data.response[field]
  taskResponseSaved.value = true; taskResponseRevision.value = data.response.revision; report.value = null
}
function responsePayload() {
  const fields = ['conclusion', 'rationale', 'object_origin', 'calculation_scope', ...(formalSession.value ? ['target_views', 'kept_released'] : [])]
  return Object.fromEntries(fields.map(field => [field, taskResponse[field]]))
}
function recordResponseDraft() { log('task_response_draft', { revision: state.value.revision, response: responsePayload(), submitted: false }) }
function responseEdited() { taskResponseSaved.value = false; recordResponseDraft() }
async function finish(reason = 'completed') {
  if (participantSession.value && trialRunning.value && reason === 'completed' && panel.value !== 'task') { panel.value = 'task'; return }
  await stopIfConnected()
  if (!assignment.value || session.value.trial_status !== 'finished') {
    if (reason === 'completed' && currentTask.value?.business_goal && (!assignment.value || trialRunning.value)) await saveTaskResponse()
    const result = await api('/api/finish', { reason })
    report.value = result.report
    if (assignment.value) session.value = result.session
  }
  if (participantSession.value) { panel.value = 'complete'; return }
  media.value = (await api('/api/media')).items
  reportTab.value = 'outcome'; panel.value = 'report'
}
async function loadExperiment() { experimentPlan.value = await api(`/api/experiment/plan?slot=${allocationSlot.value}&protocol=${experimentProtocol.value}`); await refreshExperimentReport() }
async function openExperiment() { panel.value = 'experiment'; await loadExperiment() }
async function prepareAssigned(trialIndex) {
  panel.value = participantSession.value ? '' : 'experiment'; await nextTick(); await stopIfConnected()
  const data = await api('/api/experiment/start', { participant_id: participant.value, slot: allocationSlot.value,
    trial_index: trialIndex, evidence_kind: experimentEvidenceKind.value, protocol: experimentProtocol.value })
  clearSelection(); messages.value = []; historyDetail.value = null; report.value = null; rendered.clear()
  hydrate(data); panel.value = ''; error.value = ''
}
async function beginAssigned() {
  hydrate(await api('/api/experiment/begin', {})); now.value = Date.now(); panel.value = ''
}
async function refreshExperimentReport() { experimentAggregate.value = await api(`/api/experiment/report?protocol=${experimentProtocol.value}`) }
async function inspectAttempt(id) { archivePacket.value = await api(`/api/experiment/attempts/${id}`); panel.value = 'archive' }
async function saveArchiveDraft(body) { archivePacket.value = await api(`/api/experiment/attempts/${archivePacket.value.session.id}/review-drafts`, body) }
async function stopIfConnected() { if (voiceConnected.value || voiceConnecting.value) await stopVoice() }
async function saveReview() { await api('/api/review', { notes: humanNotes.value, classification: humanClass.value }); reviewSaved.value = true }
function displayTime(value) { return value ? new Date(value).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '' }
function nodeName(node) { return node.title || node.summary || `Dashboard version ${node.revision}` }
function changeValue(value) {
  if (value === null) return 'Not set'
  if (Array.isArray(value)) return value.map(humanize).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return humanize(value)
}

onMounted(async () => {
  trialClock = setInterval(() => { now.value = Date.now() }, 1000)
  await action(async () => {
    hydrate(await api('/api/bootstrap'))
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
    socket.onopen = () => { connected.value = true; clockSync.start(session.value.id); queueContext() }
    socket.onmessage = event => receive(JSON.parse(event.data)).catch(e => { error.value = e.message })
    socket.onclose = () => { connected.value = false; clockSync.stop(); voiceConnected.value = false; voiceConnecting.value = false; closeMicrophone(); speaker.stop() }
  })
})
onBeforeUnmount(() => { clearInterval(trialClock); clearTimeout(contextTimer); clockSync.stop(); closeMicrophone(); speaker.close(); socket?.close() })
</script>

<template>
  <div class="studio-shell">
    <aside class="nav-rail" aria-label="Workspace navigation">
      <a class="brand-symbol" href="/" aria-label="CoVis Studio"><span></span><span></span><span></span></a>
      <button class="rail-button active" aria-label="Dashboard workspace" @click="panel = ''"><LayoutDashboard :size="22"/></button>
      <button v-if="!participantSession" class="rail-button" :disabled="voiceConnecting || busy || (!!assignment && session.trial_status !== 'finished')" :class="{ active: panel === 'tasks' }" aria-label="Open tasks" @click="panel = 'tasks'"><GitBranch :size="21"/></button>
      <button class="rail-button" aria-label="Toggle journey" @click="journeyOpen = !journeyOpen"><History :size="21"/></button>
      <div class="rail-bottom"><button v-if="!participantSession" class="rail-button" aria-label="Connection settings" @click="panel = 'settings'"><Settings2 :size="21"/></button><div class="user-avatar" title="Local research workspace">CV</div></div>
    </aside>

    <div class="studio-body">
      <header class="topbar">
        <div class="wordmark">CoVis <span>Studio</span><span class="wordmark-divider"></span><span class="workspace-label">Shared workspace</span></div>
        <div class="topbar-actions"><span class="local-status"><i :class="{ online: connected }"></i>{{ connected ? 'Local workspace' : 'Connecting' }}</span><button class="button ghost" :disabled="trialLocked" @click="openSavedSets()"><Copy :size="15"/> Saved sets <span v-if="categorySets.length" class="button-count">{{ categorySets.length }}</span></button><button v-if="!participantSession" class="button ghost" :disabled="voiceConnecting || busy || (!!assignment && session.trial_status !== 'finished')" @click="panel = 'tasks'"><Plus :size="15"/> New session</button><button v-if="!participantSession" class="button ghost" @click="action(openExperiment)"><GitBranch :size="15"/> Experiment</button><button class="button subtle" :disabled="voiceConnecting || busy || (assignment && session.trial_status === 'ready')" @click="action(finish)"><FileCheck2 :size="16"/>{{ trialRunning ? 'Finish task' : participantSession ? 'View submission' : 'Review & export' }}</button></div>
      </header>

      <div v-if="assignment" class="assigned-task-strip">
        <div><span class="eyebrow">ASSIGNED TASK {{ assignment.trial_index }} / 4</span><strong>{{ participant }} · {{ participantSession ? 'Analysis workspace' : session.condition === 'direct' ? 'Direct editing' : 'Evidence-linked revision' }}</strong><span>Version {{ assignment.variant_id.toUpperCase() }} · {{ humanize(session.trial_status) }}</span></div>
        <div v-if="trialRunning" class="task-clock"><Clock3 :size="16"/><strong>{{ clockLabel(timeLeft) }}</strong><span>remaining</span><button class="text-button" @click="action(() => finish('abandoned'))">End unfinished</button></div>
        <span v-else-if="session.trial_status === 'ready'" class="muted">The task clock has not started.</span>
        <div v-else class="trial-finished-controls"><span>Task saved · Read-only canvas</span><button class="button subtle" @click="action(finish)">Review task</button><button v-if="nextAssigned" class="button primary" :disabled="busy" @click="action(() => prepareAssigned(nextAssigned))">Prepare next task <ArrowUpRight :size="15"/></button><button v-else-if="!participantSession" class="button primary" @click="action(openExperiment)">Experiment records</button></div>
      </div>
      <main class="main-layout" :inert="trialLocked" :class="{ 'trial-canvas-locked': assignment && session.trial_status === 'ready' }">
        <section class="canvas-column">
          <div class="workspace-heading"><div><div class="eyebrow">OLIST / EXPLORATION</div><h1>{{ state.views.length ? state.title : 'A clearer picture, together.' }}</h1><p>{{ state.views.length ? 'Explore the evidence. Refine the question. Keep what matters.' : 'Build a dashboard through conversation and direct editing.' }}</p></div><button v-if="state.views.length" class="button primary" @click="openEditor()"><Plus :size="17"/> Add chart</button></div>

          <div v-if="currentTask && currentTask.id !== 'starter'" class="task-banner"><div class="task-badge"><GitBranch :size="17"/></div><div><span class="eyebrow">CURRENT TASK</span><strong>{{ currentTask.title }}</strong><p>{{ currentTask.business_goal || currentTask.goal || currentTask.description }}</p></div><button class="text-button" @click="panel = 'task'">View task <ArrowUpRight :size="14"/></button></div>

          <div v-if="state.views.length" class="canvas-toolbar"><div class="scope-chips"><span v-for="scope in sharedScope" :key="scope"><span class="chip-dot"></span>{{ scope }}</span><span v-if="!sharedScope.length" class="muted">Independent chart scopes</span></div><div class="canvas-controls"><div class="column-controls" aria-label="Canvas columns"><button v-for="columns in [2,3]" :key="columns" :class="{ active: (state.layout?.columns || 3) === columns }" :aria-label="`${columns} column layout`" @click="action(() => arrange(columns))">{{ columns }} <span>col</span></button></div><button class="icon-button" :disabled="!nodes.length" aria-label="Undo last change" @click="action(undo)"><RotateCcw :size="17"/></button><span class="toolbar-divider"></span><span class="version-label">v{{ state.revision }}</span></div></div>

          <div v-if="evidence" class="evidence-strip"><div class="evidence-symbol"><Link2 :size="18"/></div><div class="evidence-strip-copy"><span class="eyebrow">REFERENCED EVIDENCE</span><strong>{{ evidence.source.region || 'All regions' }} · Chart {{ evidence.number }} · Version {{ evidence.revision }}</strong><p>{{ evidence.members.map(humanize).join(' · ') }}</p></div><span class="evidence-current">Current canvas stays at v{{ state.revision }}</span><button v-if="revisionAvailable" class="button subtle" @click="openRevision">Use in a revision <ArrowUpRight :size="15"/></button><button class="icon-button" aria-label="Clear evidence reference" @click="action(clearEvidence)"><X :size="17"/></button></div>

          <div v-if="selected.length" class="selection-bar"><div><CheckCheck :size="17"/><strong>{{ selected.length }} {{ selected.length === 1 ? 'chart' : 'charts' }} selected</strong><span>Referenced in your next request</span></div><div><button v-if="revisionAvailable" class="text-button" @click="openRevision">Plan a revision <GitBranch :size="14"/></button><button class="text-button" @click="openEditor(selected[0])">Edit selection <SlidersHorizontal :size="14"/></button><button class="icon-button" aria-label="Clear selection" @click="clearSelection"><X :size="16"/></button></div></div>

          <div v-if="!state.views.length" class="empty-canvas">
            <div class="canvas-illustration" aria-hidden="true"><div class="illustration-grid"></div><div class="illustration-card card-one"><span class="illus-dot"></span><div class="illus-bars"><i></i><i></i><i></i><i></i></div></div><div class="illustration-card card-two"><span class="illus-dot"></span><svg viewBox="0 0 160 70"><path d="M8 56L37 40L65 45L98 17L126 28L153 8" fill="none" stroke="#238579" stroke-width="3"/><path d="M8 56L37 40L65 45L98 17L126 28L153 8V70H8Z" fill="#e7f1ec"/></svg></div><div class="illustration-link"><Link2 :size="20"/></div></div>
            <span class="eyebrow">YOUR NEXT QUESTION STARTS HERE</span><h2>Make room for an insight.</h2><p>Start with three connected views of service quality,<br>or create a chart and follow your own question.</p>
            <div class="empty-actions"><button class="button primary large" :disabled="busy" @click="action(() => openSession('starter'))"><LayoutDashboard :size="18"/> Start with Olist <ArrowUpRight :size="17"/></button><button class="button ghost large" @click="openEditor()"><Plus :size="17"/> Blank canvas</button></div>
            <div class="starter-caption"><span class="small-dot"></span>Real order data · Three linked views · Explicit starter</div>
            <div class="getting-started"><div><span>01</span><strong>Choose a view</strong><p>Click a chart number or a data mark.</p></div><div><span>02</span><strong>Shape the question</strong><p>Speak, type, or edit directly.</p></div><div><span>03</span><strong>Follow the changes</strong><p>Revisit every committed version.</p></div></div>
          </div>

          <div v-else class="chart-grid" :style="{ '--columns': state.layout?.columns || 3 }">
            <ChartCard v-for="view in state.views" :key="view.id" :ref="el => el ? cards.set(view.id, el) : cards.delete(view.id)" :view="view" :revision="state.revision" :selected="selected.includes(view.id)" :entities="entities[view.id] || emptyEntities" @select="selectView" @entity="selectEntity" @edit="openEditor" :telemetry-active="connected && !panel && !expanded && !preparingTrial" @telemetry="chartTelemetry" @rendered="chartRendered" @expand="expanded = $event" @move="(id, direction) => action(() => moveChart(id, direction))"/>
            <button v-if="state.views.length < 3" class="add-chart-tile" @click="openEditor()"><Plus :size="24"/><strong>Add another perspective</strong><span>Create a chart using the same Olist data</span></button>
          </div>

          <div v-if="state.views.length" class="canvas-note"><span><span class="small-dot"></span>Values computed from Olist. Click a mark to reference its category.</span><span>{{ state.views.length }} {{ state.views.length === 1 ? 'view' : 'views' }} on canvas</span></div>

          <section class="journey" :class="{ collapsed: !journeyOpen }">
            <button class="journey-heading" @click="journeyOpen = !journeyOpen"><div><History :size="18"/><strong>Your journey</strong><span>{{ nodes.length }} {{ nodes.length === 1 ? 'step' : 'steps' }}</span></div><span class="journey-hint">Every change has a place <ChevronDown :size="16" :class="{ rotated: journeyOpen }"/></span></button>
            <div v-if="journeyOpen" ref="journeyTrack" class="journey-track"><div v-if="!nodes.length" class="journey-empty"><span class="journey-origin"></span>Your first chart will start the story. Committed changes appear here.</div><button v-for="(node, index) in nodes" :key="node.id" class="journey-node" :class="{ latest: index === nodes.length - 1 }" @click="action(() => inspectNode(node))"><div class="node-top"><span class="node-circle">{{ index + 1 }}</span><span>{{ displayTime(node.created_at) }}</span><span class="node-version">v{{ node.revision }}</span></div><strong>{{ nodeName(node) }}</strong><p>{{ node.summary || `${node.view_ids?.length || state.views.length} views · ${humanize(node.actor || 'Workspace')}` }}</p><span v-if="index === nodes.length - 1" class="current-node">Current canvas <Check :size="12"/></span><span v-else class="past-node">View this step <ArrowUpRight :size="12"/></span></button></div>
          </section>
        </section>

        <aside class="collaboration-panel">
          <header class="collaboration-header"><div class="assistant-symbol"><AudioLines :size="21"/></div><div><h2>Think together</h2><span>{{ connectionLabel }}</span></div><button v-if="!participantSession" class="icon-button" aria-label="Assistant settings" @click="panel = 'settings'"><MoreHorizontal :size="20"/></button></header>
          <div class="mode-switch" role="group" aria-label="Interaction mode"><button v-for="item in modeItems" :key="item.id" :class="{ active: mode === item.id }" :disabled="busy || voiceConnecting || formalSession" @click="action(() => setMode(item.id))"><component :is="item.icon" :size="15"/>{{ item.title }}</button></div>
          <div ref="conversation" class="conversation">
            <div v-if="!messages.length" class="conversation-empty"><div class="collaboration-mark"><span></span><span></span><span></span><span></span></div><h3>What would you like<br>to understand?</h3><p>Select a chart, then describe what you want to change or explore next.</p><div class="conversation-prompts"><span class="eyebrow">WAYS TO BEGIN</span><button @click="draft = 'Compare the same categories using average delivery time.'">Compare another perspective <ArrowUpRight :size="15"/></button><button @click="draft = 'Keep these categories and change the region to RJ.'">Keep the context, change the scope <ArrowUpRight :size="15"/></button></div><div class="conversation-footnote"><Link2 :size="15"/><span>Your selected views and current chart image accompany each request.</span></div></div>
            <article v-for="message in messages" :key="message.id" class="message" :class="message.role"><div class="message-label"><span>{{ message.role === 'user' ? 'You' : 'CoVis' }}</span><span>{{ displayTime(message.created) }}</span></div><div class="message-text">{{ message.text || '…' }}</div><audio v-if="message.audio" controls :src="message.audio" @play="log('replay_start', { response_id: message.id })" @ended="log('replay_end', { response_id: message.id })"></audio><div v-if="receiptForMessage(message)" class="turn-receipt"><ToolFeedback :result="receiptForMessage(message)"/><button v-if="['no_changes', 'failed'].includes(receiptForMessage(message).status) && message.request_id === currentRequestId && selected.length && !trialLocked" class="text-button" @click="revisionAvailable ? openRevision() : openEditor(selected[0])">Review edit <ArrowUpRight :size="14"/></button></div></article>
            <RevisionSupport v-if="proposal" :key="proposal.id" :proposal="proposal" :state="state" :structured="revisionAvailable" :active="connected && !panel && !expanded && !preparingTrial" :busy="busy" :readonly="!!trialLocked" @apply="action(applyRevision)" @revise="action(reviseProposal)" @close="action(closeProposal)" @observation="log"/>
            <div v-if="['thinking','working'].includes(status)" class="working-indicator"><Loader2 :size="14" class="spin"/><span>{{ status === 'working' ? 'Updating your canvas' : 'Considering your request' }}</span><button @click="cancel">Cancel</button></div>
          </div>
          <ToolFeedback :result="toolReceipt"/>
          <div v-if="error" class="error-notice" role="alert"><span>{{ error }}</span><button class="icon-button" aria-label="Dismiss error" @click="error = ''"><X :size="14"/></button></div>
          <div class="composer-area">
            <div v-if="evidence" class="composer-evidence"><Link2 :size="13"/><span>Evidence: {{ evidence.source.region || 'All regions' }} · Chart {{ evidence.number }} · v{{ evidence.revision }}</span><button class="icon-button" aria-label="Remove historical evidence" @click="action(clearEvidence)"><X :size="12"/></button></div>
            <div v-if="selected.length" class="composer-references"><span>Referring to</span><button v-for="view in selectedViews" :key="view.id" @click="selectView(view.id)">{{ String(view.number).padStart(2,'0') }} <X :size="11"/></button></div>
            <div v-if="mode === 'text'" class="text-composer"><textarea v-model="draft" placeholder="Ask a question or describe a change…" rows="3" aria-label="Message to CoVis" @keydown="onComposerKey" @focus="log('text_focus')" @blur="log('text_blur')"></textarea><div class="composer-bottom"><span><span class="small-dot"></span>{{ visualLabel }}</span><button class="send-button" :disabled="!canSend || busy" aria-label="Send message" @click="action(sendText)"><ArrowUp :size="20"/></button></div></div>
            <div v-else-if="formalSession && voiceWindowUsed && !voiceConnected && !voiceConnecting" class="voice-composer"><strong>Voice window complete.</strong><p>Continue with chart controls.</p></div><div v-else class="voice-composer" :class="{ recording }"><div class="voice-visual"><span v-for="i in 15" :key="i" :style="{ height: `${recording ? 6 + (Math.sin(i * 2.1) ** 2) * (8 + microphoneLevel * 250) : 4 + Math.sin(i * 1.1) ** 2 * 6}px` }"></span></div><strong>{{ voiceConnecting ? 'Connecting to Qwen…' : recording ? (mode === 'live_voice' ? 'Listening — you can speak over playback' : 'Recording your request') : voiceConnected ? 'Ready for your next request' : mode === 'live_voice' ? 'A continuous conversation' : 'One thought at a time' }}</strong><p>{{ recording ? `${speechSeconds.toFixed(1)}s${mode === 'push_to_talk' ? ' / 10s' : speechSeconds >= 10 ? ' · A shorter request is easier to follow' : ''}` : mode === 'live_voice' ? 'Speak while you explore. A session lasts up to 60 seconds.' : 'Record up to 10 seconds, then send your request.' }}</p><button class="button voice-button" :class="{ live: recording }" :disabled="busy || voiceConnecting || !connected || (formalSession && voiceWindowUsed && !voiceConnected)" @click="action(voiceClick)"><Loader2 v-if="voiceConnecting" :size="17" class="spin"/><Square v-else-if="recording" :size="14"/><Mic v-else :size="17"/>{{ recording ? (mode === 'live_voice' ? 'End voice session' : 'Send recording') : voiceConnected ? 'Record next request' : 'Start speaking' }}</button><button v-if="voiceConnected && mode === 'push_to_talk'" class="text-button end-voice" @click="action(stopVoice)">End session</button></div>
            <div v-if="mode !== 'text'" class="visual-delivery-status"><Link2 :size="12"/><span>{{ visualLabel }}</span></div><div class="composer-help"><span>{{ mode === 'text' ? 'Enter to send · Shift + Enter for a new line' : 'Audio connects only when you choose to start.' }}</span><button v-if="playing" class="text-button" @click="stopSpeaking"><VolumeX :size="14"/> Stop speaking</button></div>
          </div>
          <footer class="collaboration-footer"><span><span class="small-dot"></span>{{ connectionLabel }}</span><button v-if="!participantSession" @click="panel = 'settings'">{{ settings.configured ? 'Connection' : 'Set up assistant' }} <ArrowUpRight :size="12"/></button></footer>
        </aside>
      </main>
      <div v-if="assignment && session.trial_status === 'ready'" class="trial-curtain">
        <section class="trial-ready-card">
          <span class="eyebrow">TASK {{ assignment.trial_index }} OF 4 · READY</span>
          <h2>Read the goal. Begin when ready.</h2>
          <TaskBrief :task="currentTask"/><p class="field-help">You have eight minutes from Begin task. The chart workspace opens at that point. Starting the task does not connect the assistant.</p><div class="trial-ready-actions"><button class="button primary" :disabled="busy" @click="action(beginAssigned)">Begin task <ArrowUpRight :size="17"/></button><button class="text-button" :disabled="busy" @click="action(() => finish('abandoned'))">End unfinished</button></div>
        </section>
      </div>
    </div>

    <div v-if="panel" class="drawer-backdrop" @click.self="panel = ''">
      <section class="drawer" :class="{ wide: panel === 'history' || panel === 'report' || panel === 'revision' || panel === 'task' || panel === 'experiment', 'archive-drawer': panel === 'archive' }" role="dialog" aria-modal="true" :aria-label="panel === 'edit' ? 'Chart editor' : humanize(panel)">
        <header class="drawer-heading"><div><span class="eyebrow">COVIS STUDIO</span><h2>{{ { edit: editId ? 'Refine your selection' : 'A new perspective', tasks: 'Analysis tasks', task: 'Your analysis task', sets: 'Saved sets', settings: 'Your connection', history: 'A moment in the journey', report: 'Session review', revision: activeEvidence ? 'Carry the evidence forward' : 'Refine the current analysis', experiment: 'Assigned analysis tasks', archive: 'Review the evidence', complete: 'Your task is saved' }[panel] }}</h2></div><button class="icon-button" aria-label="Close panel" @click="panel = ''"><X :size="22"/></button></header>
        <ExperimentPanel v-if="panel === 'experiment' && !participantSession" v-model:protocol="experimentProtocol" v-model:participant="participant" v-model:slot="allocationSlot" v-model:evidence-kind="experimentEvidenceKind" :plan="experimentPlan" :assignment="assignment" :trial-status="session.trial_status" :tasks="experimentProtocol === 'formal' ? formalTasks : experimentTasks" :aggregate="experimentAggregate" :busy="busy" @load="action(loadExperiment)" @start="index => action(() => prepareAssigned(index))" @refresh="action(refreshExperimentReport)" @inspect="id => action(() => inspectAttempt(id))"/>
        <ArchiveReview v-if="panel === 'archive' && !participantSession" :key="archivePacket.session.id" :packet="archivePacket" :busy="busy" @back="panel = 'experiment'" @save="body => action(() => saveArchiveDraft(body))"/>
        <RevisionPanel v-if="panel === 'revision'" :key="proposal?.id || 'new-revision'" :state="state" :evidence="activeEvidence" :condition="session.condition" :proposal="proposal" :catalog="catalog" :selected="selected" :seed="revisionEditSeed" :sets="categorySets" :busy="busy" :observations-enabled="connected && !preparingTrial" @preview="payload => action(() => previewRevision(payload))" @apply="action(applyRevision)" @revise="action(reviseProposal)" @close="action(closeProposal)" @observation="log"/>
        <SavedSetsPanel v-if="panel === 'sets'" :state="state" :sets="categorySets" :selected="selected" :entities="entities" :seed="setSeed" :busy="busy" @save="payload => action(() => saveCategorySet(payload))" @apply="id => action(() => applyCategorySet(id))"/>
        <div v-if="panel === 'edit'" class="drawer-body editor-body"><div v-if="editId" class="editor-scope"><CheckCheck :size="16"/><span>Changes apply to {{ selected.length }} selected {{ selected.length === 1 ? 'chart' : 'charts' }}. Unchanged fields stay as they are.</span></div><label class="field"><span>Chart title</span><input v-model="editor.title"/></label><label class="field"><span>Chart type</span><div class="chart-type-options"><button v-for="type in chartTypes" :key="type" :class="{ active: editor.chart_type === type }" @click="editor.chart_type = type">{{ humanize(type) }}</button></div></label><div class="field-row"><label class="field"><span>Measure</span><select v-model="editor.metric" aria-label="Measure"><option v-for="(label, value) in metricNames" :key="value" :value="value">{{ label }}</option></select></label><label class="field"><span>Group by</span><select v-model="editor.dimension"><option value="category">Product category</option><option value="month">Purchase month</option><option value="state">Customer state</option></select></label></div><div class="section-label">Analysis scope</div><div class="field-row"><label class="field"><span>Region</span><select v-model="editor.region"><option :value="null">All regions</option><option v-for="region in catalog.states" :key="region" :value="region">{{ region }}</option></select></label><label class="field"><span>Order status</span><select v-model="editor.status"><option value="delivered">Delivered</option><option value="shipped">Shipped</option><option value="canceled">Canceled</option></select></label></div><div class="field-row"><label class="field"><span>From · inclusive</span><input type="date" v-model="editor.start"/></label><label class="field"><span>Until · exclusive</span><input type="date" v-model="editor.end"/></label></div><div class="section-label">Comparison objects</div><div class="membership-switch"><button :class="{ active: editor.membership === 'ranked' }" @click="editor.membership = 'ranked'; editor.categories = null; editor.top_n = 5">Dynamic ranking</button><button :class="{ active: editor.membership === 'fixed' }" @click="editId ? fixCurrentMembers() : (editor.membership = 'fixed', editor.categories = [])">Fixed categories</button></div><p class="field-help">{{ editor.membership === 'fixed' ? 'Keep these exact categories when the metric or region changes.' : 'Recompute the leading groups when the scope changes.' }}</p><div v-if="editor.membership === 'ranked'" class="field-row"><label class="field"><span>Number of groups</span><input type="number" min="1" max="30" v-model.number="editor.top_n"/></label><label class="field"><span>Rank by</span><select v-model="editor.rank_by" aria-label="Rank by"><option v-for="(label, value) in metricNames" :key="value" :value="value">{{ label }}</option></select></label></div><label v-else class="field"><span>Choose categories</span><select multiple class="category-select" v-model="editor.categories"><option v-for="item in fieldOptions" :key="item.id" :value="item.id">{{ item.label }}</option></select><small>Use Ctrl / Command to select more than one category.</small></label><div class="section-label">Presentation</div><div class="field"><span>Accent color</span><div class="color-options"><button v-for="color in palette" :key="color" :style="{ background: color }" :aria-label="`Use ${color}`" :class="{ active: editor.color === color }" @click="editor.color = color"><Check v-if="editor.color === color" :size="17"/></button><input type="color" v-model="editor.color" aria-label="Custom accent color"/></div></div><div class="field-row"><label class="field"><span>Display order</span><select v-model="editor.sort"><option value="source">Query order</option><option value="descending">Value: high to low</option><option value="ascending">Value: low to high</option></select></label><label class="check-field"><input type="checkbox" v-model="editor.show_labels"/><span>Show value labels</span></label></div><div class="data-note"><BarChart3 :size="17"/><span>Values are recomputed from Olist. Presentation changes never overwrite source data.</span></div></div>
        <footer v-if="panel === 'edit'" class="drawer-footer"><button v-if="editId" class="button danger-ghost" @click="action(removeSelected)"><Trash2 :size="16"/> Remove</button><button v-else class="button ghost" @click="panel = ''">Cancel</button><button class="button primary" :disabled="busy || !editorChanged" @click="action(applyEditor)"><Loader2 v-if="busy" class="spin" :size="16"/><Check v-else :size="17"/>{{ editId ? 'Apply changes' : 'Create chart' }}</button></footer>

        <div v-if="panel === 'tasks'" class="drawer-body">
          <p class="drawer-intro">Choose an analysis goal, then use charts and conversation to develop your answer. A new session preserves the previous record on disk.</p>
          <div class="section-label first-section">Analysis tasks</div>
          <button v-for="task in tasks.filter(task => task.id !== 'starter')" :key="task.id" class="task-card" :class="{ selected: selectedTask === task.id }" @click="selectedTask = task.id"><div><GitBranch :size="20"/><span class="task-kind">{{ humanize(task.kind || 'Analysis task') }}</span></div><h3>{{ task.title }}</h3><p>{{ task.business_goal || task.goal || task.description }}</p></button>
          <TaskBrief v-if="tasks.find(task => task.id === selectedTask && task.business_goal)" :task="tasks.find(task => task.id === selectedTask)"/>
          <div class="section-label">Explore freely</div>
          <button class="task-card" :class="{ selected: selectedTask === 'starter' }" @click="selectedTask = 'starter'"><div><LayoutDashboard :size="22"/><span class="task-kind">STARTER</span></div><h3>Service quality, three perspectives</h3><p>Orders, low-review rates and delivery time, for the same product categories.</p><span class="task-card-bottom">SP · 2017 · Delivered orders <Check v-if="selectedTask === 'starter'" :size="17"/></span></button>
          <button class="task-card" :class="{ selected: selectedTask === '' }" @click="selectedTask = ''"><div><Plus :size="21"/><span class="task-kind">OPEN EXPLORATION</span></div><h3>A blank canvas</h3><p>Start with your own analysis question.</p></button>
          <details v-if="diagnosticTasks.length" class="diagnostic-tasks"><summary>Technical diagnostic tasks</summary><p>Controlled mechanism checks for development.</p><label class="field"><span>Diagnostic case</span><select v-model="selectedTask" aria-label="Diagnostic task"><option disabled value="">Choose a diagnostic case</option><option v-for="task in diagnosticTasks" :key="task.id" :value="task.id">{{ task.title }}</option></select></label><TaskBrief v-if="diagnosticTasks.find(task => task.id === selectedTask)" :task="diagnosticTasks.find(task => task.id === selectedTask)"/></details>
          <details class="study-configuration"><summary>Study configuration</summary><label class="field"><span>Participant label · optional</span><input v-model="participant" placeholder="e.g. P01"/></label><label class="field"><span>Input</span><select v-model="mode"><option v-for="item in modeItems" :key="item.id" :value="item.id">{{ item.title }}</option></select></label><label class="field"><span>Revision support</span><select v-model="condition" aria-label="Study condition"><option v-for="item in conditions" :key="item.id" :value="item.id">{{ item.label }}</option></select></label><p>{{ conditions.find(item => item.id === condition)?.description }}</p></details>
        </div>
        <footer v-if="panel === 'tasks'" class="drawer-footer"><span class="muted">No model connection is opened.</span><button class="button primary" :disabled="busy" @click="action(() => openSession())">Start session <ArrowUpRight :size="17"/></button></footer>
        <div v-if="panel === 'task' && currentTask" class="drawer-body">
          <TaskBrief :task="currentTask"/>
          <template v-if="currentTask.business_goal && !trialLocked">
            <div class="section-label">Your response</div><p class="field-help">Explain your conclusion and the evidence behind it. Your answers are saved when you finish.</p>
            <label class="field"><span>Conclusion</span><textarea v-model="taskResponse.conclusion" @input="responseEdited" rows="3" placeholder="What would you recommend?"/></label>
            <label class="field"><span>Evidence and rationale</span><textarea v-model="taskResponse.rationale" @input="responseEdited" rows="4" placeholder="Cite the charts, values and limits behind your conclusion."/></label>
            <div class="section-label">Explain the comparison</div>
            <label class="field"><span>Where did the compared categories come from?</span><textarea v-model="taskResponse.object_origin" @input="responseEdited" rows="2" placeholder="Explain how the objects were chosen and the evidence version used."/></label>
            <label class="field"><span>Which region, dates and measure produced the displayed values?</span><textarea v-model="taskResponse.calculation_scope" @input="responseEdited" rows="3" placeholder="Describe the current calculation scope and relevant denominator."/></label>
            <template v-if="formalSession"><label class="field"><span>Which charts did the revision affect?</span><textarea v-model="taskResponse.target_views" @input="responseEdited" rows="2" placeholder="Name the chart numbers and what changed."/></label><label class="field"><span>What stayed in place, and what was released?</span><textarea v-model="taskResponse.kept_released" @input="responseEdited" rows="3" placeholder="Describe retained conditions and any selection or condition you let go."/></label></template>
            <p v-if="taskResponseRevision !== null && taskResponseRevision !== state.revision" class="response-stale" role="status">Charts changed — review and save again. Your response was saved for v{{ taskResponseRevision }}; the canvas is now v{{ state.revision }}.</p><div v-if="!participantSession" class="task-response-status"><span>Human review</span><strong class="pending-label">Pending</strong></div>
            <button class="button primary" :disabled="busy || !taskResponse.conclusion.trim()" @click="action(saveTaskResponse)"><Check :size="16"/>{{ taskResponseSaved && taskResponseRevision === state.revision ? 'Response saved' : 'Save response' }}</button><button v-if="trialRunning" class="button primary finish-response" :disabled="busy" @click="action(() => finish('completed'))">Save response and finish <Check :size="16"/></button>
          </template>
        </div>

        <div v-if="panel === 'settings' && !participantSession" class="drawer-body"><div class="connection-card"><div class="connection-icon"><Radio :size="25"/></div><h3>{{ settings.connection_mode === 'disabled' ? 'Local review mode' : settings.configured ? 'Your assistant is configured.' : 'Connect your assistant.' }}</h3><p>{{ settings.connection_mode === 'disabled' ? 'This review service keeps model calls disabled. Use the main app for live conversation.' : settings.configured ? 'Models connect only when you send a message or explicitly start a voice session.' : 'The canvas, chart editor and version journey already work locally. Add your Qwen key to enable conversation.' }}</p><span class="connection-state"><i :class="{ online: settings.configured }"></i>{{ settings.connection_mode === 'disabled' ? 'Model calls disabled in this service' : settings.configured ? 'Configured · not a live API check' : 'API key not configured' }}</span></div><div class="section-label">Local configuration</div><p v-if="settings.connection_mode !== 'disabled'" class="settings-copy">Add your key to <code>{{ settings.credential_file }}</code>, then restart the local server. Your key stays on this computer and is never shown in the interface.</p><div class="model-row"><TextCursorInput :size="19"/><div><span>Text conversation</span><strong>{{ settings.text_model || 'Qwen text model' }}</strong></div></div><div class="model-row"><AudioLines :size="19"/><div><span>Voice conversation</span><strong>{{ settings.realtime_model || 'Qwen Realtime' }}</strong></div></div><div class="section-label">A deliberate connection</div><ul class="settings-list"><li>Same visual context and chart tools in every mode.</li><li>Push-to-talk recordings stop after 10 seconds.</li><li>Live voice remains open during assistant playback.</li><li>Voice sessions end after 60 seconds. No automatic reconnect.</li></ul><div class="data-note"><CircleHelp :size="17"/><span>Local protocol checks do not establish real model performance or human listening quality.</span></div></div>

        <div v-if="panel === 'history' && historyDetail" class="drawer-body"><div class="history-title"><span class="version-pill">Version {{ historyDetail.node.revision }}</span><span>{{ displayTime(historyDetail.node.created_at) }}</span></div><h3 class="history-node-title">{{ nodeName(historyDetail.node) }}</h3><p class="drawer-intro">{{ historyDetail.node.summary }}</p><p v-if="historyDetail.node.revision_card" class="history-reference-note"><Link2 :size="16"/><span>{{ historyDetail.node.evidence ? `Evidence from version ${historyDetail.node.evidence.revision}` : 'Current analysis' }} → Charts {{ historyDetail.node.revision_card.changes.map(change => change.number).join(', ') }} · Applied to version {{ historyDetail.node.revision }}</span></p><div v-if="historyDetail.node.changes?.length" class="node-changes"><div v-for="change in historyDetail.node.changes" :key="change.view_id"><p class="node-change-label">CHART {{ change.number }} · {{ change.view_id }}</p><div v-for="detail in change.details || []" :key="detail.field" class="node-change"><strong>{{ humanize(detail.field.replaceAll('.', ' ')) }}</strong><span>{{ changeValue(detail.before) }} <b>→</b> {{ changeValue(detail.after) }}</span></div></div></div><div v-if="historyDetail.node.dashboard_changes?.length" class="data-note">Dashboard changes: {{ historyDetail.node.dashboard_changes.map(humanize).join(', ') }}</div><div class="history-reference-note"><Link2 :size="17"/><span>Reference categories from this version without restoring its region, dates or chart state.</span></div><div class="history-previews"><div v-for="view in historyDetail.state.views" :key="`${historyDetail.node.id}-${view.id}`" class="history-evidence-chart"><ChartCard :view="view" :revision="historyDetail.state.revision" :telemetry-active="connected && panel === 'history' && !expanded" @telemetry="chartTelemetry" @rendered="chartRenderTelemetry" readonly/><div v-if="view.source.dimension === 'category'" class="history-member-selection"><span class="eyebrow">CATEGORIES TO REFERENCE</span><div><button v-for="row in view.data.rows" :key="row.label" :class="{ active: historyMembers[view.id].includes(row.label) }" :aria-pressed="historyMembers[view.id].includes(row.label)" :aria-label="`Reference ${humanize(row.label)} from chart ${view.number}`" @click="toggleHistoryMember(view.id, row.label)"><Check v-if="historyMembers[view.id].includes(row.label)" :size="12"/>{{ humanize(row.label) }}</button></div></div><div v-if="view.source.dimension === 'category'" class="history-evidence-action"><span>{{ historyMembers[view.id].length }} selected · {{ view.source.region || 'All regions' }}</span><button class="button ghost" :disabled="busy || !historyMembers[view.id].length" :aria-label="`Save set from chart ${view.number} version ${historyDetail.state.revision}`" @click="openSavedSets(view)"><Copy :size="14"/> Save set</button><button class="button subtle" :disabled="busy || !historyMembers[view.id].length" :aria-label="`Use chart ${view.number} version ${historyDetail.state.revision} as evidence`" @click="action(() => useEvidence(view))"><Link2 :size="14"/> Use as evidence</button></div></div></div><div class="section-label">Recorded events</div><div class="event-list"><div v-for="(event, index) in historyDetail.events" :key="index"><span class="event-dot"></span><div><strong>{{ humanize(event.name || event.type || event.event || 'Event') }}</strong><p>{{ event.text || event.message || event.details?.text || '' }}</p></div><span>{{ event.server_ms !== undefined ? `${(event.server_ms / 1000).toFixed(2)}s · server` : '' }}</span></div><p v-if="!historyDetail.events?.length" class="muted">This node contains the committed chart snapshot.</p></div></div><footer v-if="panel === 'history' && historyDetail" class="drawer-footer"><span class="muted">Restoring creates a new version.</span><button class="button primary" :disabled="busy" @click="action(restoreNode)"><RotateCcw :size="16"/> Restore this canvas</button></footer>

        <div v-if="panel === 'report' && report && !participantSession" class="drawer-body"><div class="review-tabs"><button :class="{ active: reportTab === 'outcome' }" @click="reportTab = 'outcome'">Outcome & notes</button><button :class="{ active: reportTab === 'audio' }" @click="reportTab = 'audio'">Saved audio</button></div><div v-if="reportTab === 'audio'" class="saved-audio"><p class="drawer-intro">These are recorded input and received output files. Actual browser playback is documented separately in the event log.</p><article v-for="item in media.filter(item => item.kind === 'audio')" :key="item.name"><div><Volume2 :size="17"/><strong>{{ item.name.includes('input') ? 'User recording' : 'Assistant audio' }}</strong><span>{{ item.duration_seconds ? `${item.duration_seconds.toFixed(1)}s` : '' }}</span></div><p>{{ item.name }}</p><audio controls :src="item.url" @play="log('review_audio_play', { file: item.name })"></audio></article><div v-if="!media.some(item => item.kind === 'audio')" class="data-note">No audio was recorded in this session.</div></div><template v-else><div class="report-intro"><FileCheck2 :size="28"/><h3>A record you can inspect.</h3><p>Automated checks describe the chart state. Human interpretation and listening are reviewed separately.</p></div><div class="report-stats"><div><span>Views</span><strong>{{ state.views.length }}</strong></div><div><span>Versions</span><strong>{{ state.revision }}</strong></div><div><span>Human review</span><strong class="pending-label">{{ humanize(report.review_status || 'pending') }}</strong></div></div><TrialReview v-if="report.trial_report" :trial="report.trial_report"/><div class="section-label">Outcome checks</div><div class="report-checks"><div v-for="(check, index) in report.checks || []" :key="index"><Check v-if="check.passed === true || check.pass === true" :size="16"/><CircleHelp v-else :size="16"/><span>{{ check.label || check.name || check.description }}</span><strong>{{ check.passed === true || check.pass === true ? 'Pass' : check.passed === false || check.pass === false ? 'Not met' : 'Review' }}</strong></div></div><TaskResponseReview v-if="report.task_response_status" :report="report"/><DeliveryReview v-if="report.delivery" :delivery="report.delivery"/><ReviewObservations v-if="report.interaction" :interaction="report.interaction"/><details class="report-raw"><summary>View the complete report</summary><pre>{{ JSON.stringify(report, null, 2) }}</pre></details><div class="section-label">Human review</div><label class="field"><span>Classification</span><select v-model="humanClass" @change="reviewSaved = false"><option value="pending">Pending review</option><option value="normal_exploration">Normal exploration</option><option value="intent_revision">Intent revision</option><option value="reference_error">Reference misunderstanding</option><option value="execution_error">Execution error</option></select></label><label class="field"><span>Review notes</span><textarea v-model="humanNotes" @input="reviewSaved = false" rows="4" placeholder="Describe the observed interaction. Do not infer intent from the final chart alone."></textarea></label><button class="button subtle" @click="action(saveReview)"><Check :size="15"/>{{ reviewSaved ? 'Notes saved' : 'Save review notes' }}</button></template></div><footer v-if="panel === 'report' && !participantSession" class="drawer-footer"><button v-if="assignment && session.trial_status === 'finished' && nextAssigned" class="button subtle" :disabled="busy" @click="action(() => prepareAssigned(nextAssigned))">Prepare next task <ArrowUpRight :size="15"/></button><span v-else class="muted">Includes chart states and event records.</span><a class="button primary" href="/api/export" download><Download :size="16"/> Export session</a></footer>
        <div v-if="panel === 'complete' && participantSession" class="drawer-body participant-complete"><p class="drawer-intro">Your task record is saved. The canvas remains available for inspection.</p><p v-if="!taskResponseSaved" class="response-stale">These draft answers were not submitted before the task ended.</p><dl class="response-fields"><div v-for="(value, field) in responsePayload()" :key="field"><dt>{{ { conclusion: 'Conclusion', rationale: 'Evidence and rationale', object_origin: 'Category origin', calculation_scope: 'Calculation scope', target_views: 'Affected charts', kept_released: 'Kept and released conditions' }[field] }}</dt><dd>{{ value || 'No answer recorded.' }}</dd></div></dl><div class="completion-actions"><button class="button subtle" @click="panel = ''">Inspect canvas</button><button v-if="nextAssigned" class="button primary" :disabled="busy" @click="action(() => prepareAssigned(nextAssigned))">Prepare next task <ArrowUpRight :size="15"/></button><p v-else>All four tasks are finished. Thank you.</p></div></div>
        <div v-if="error" class="drawer-error" role="alert">{{ error }}</div>
      </section>
    </div>

    <div v-if="expanded" class="expanded-overlay" @click.self="expanded = null"><div class="expanded-chart"><button class="icon-button expanded-close" aria-label="Close expanded chart" @click="expanded = null"><X :size="24"/></button><ChartCard :view="state.views.find(v => v.id === expanded)" :revision="state.revision" :telemetry-active="connected && !panel" @telemetry="chartTelemetry" @rendered="chartRenderTelemetry" :selected="selected.includes(expanded)" :entities="entities[expanded] || emptyEntities" @select="selectView" @entity="selectEntity" @edit="id => { expanded = null; openEditor(id) }"/></div></div>
  </div>
</template>
