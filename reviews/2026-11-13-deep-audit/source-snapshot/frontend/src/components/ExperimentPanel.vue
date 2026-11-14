<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowUpRight, Check, ClipboardList, Download } from 'lucide-vue-next'
import TaskBrief from './TaskBrief.vue'
import ExperimentSummary from './ExperimentSummary.vue'

const props = defineProps({ participant: String, slot: Number, evidenceKind: String, plan: Object,
  assignment: Object, trialStatus: String, tasks: Array, aggregate: Object, busy: Boolean })
const emit = defineEmits(['update:participant', 'update:slot', 'update:evidenceKind', 'load', 'start', 'refresh', 'inspect'])
const selected = ref(1)
watch(() => props.assignment?.trial_index, index => { selected.value = index || 1 })
const trial = computed(() => props.plan?.trials.find(item => item.trial_index === selected.value))
const active = computed(() => props.trialStatus === 'running' || props.trialStatus === 'ready')
const conditionName = id => id === 'direct' ? 'Direct editing' : 'Evidence-linked revision'
</script>

<template>
  <div class="drawer-body experiment-body">
    <p class="drawer-intro">Prepare a participant's four assigned tasks. Each task keeps its assigned version and editing support; the task clock begins only after <strong>Begin task</strong>.</p>
    <div class="field-row">
      <label class="field"><span>Participant label</span><input :value="participant" @input="emit('update:participant', $event.target.value)" :disabled="active" placeholder="e.g. P01" aria-label="Experiment participant"/></label>
      <label class="field"><span>Allocation slot</span><input type="number" min="1" max="30" :value="slot" @input="emit('update:slot', Number($event.target.value))" :disabled="active" aria-label="Allocation slot"/></label>
    </div>
    <label class="field"><span>Record type</span><select :value="evidenceKind" @change="emit('update:evidenceKind', $event.target.value)" :disabled="active" aria-label="Experiment record type"><option value="local_authored">Local authored check</option><option value="participant">Participant session</option></select></label>
    <button class="button subtle" :disabled="busy || active" @click="emit('load')"><ClipboardList :size="16"/> Load assignment</button>
    <template v-if="plan">
      <div class="assignment-caption"><span>Slot {{ plan.slot }}</span><span>4 tasks · 2 per condition</span></div>
      <div class="assignment-list">
        <button v-for="item in plan.trials" :key="item.trial_index" :class="{ selected: selected === item.trial_index }" :aria-label="`Assigned task ${item.trial_index}`" @click="selected = item.trial_index">
          <span class="assignment-number">{{ item.trial_index }}</span><div><strong>{{ item.task.title }}</strong><small>{{ conditionName(item.condition) }} · Version {{ item.variant_id.toUpperCase() }}</small></div><Check v-if="selected === item.trial_index" :size="16"/>
        </button>
      </div>
      <TaskBrief v-if="trial" :task="trial.task"/>
      <button class="button primary" :disabled="busy || !participant.trim() || active" @click="emit('start', selected)">Prepare assigned task {{ selected }} <ArrowUpRight :size="16"/></button>
      <p v-if="active" class="field-help">Finish or end the current task before preparing another. Its record is retained.</p>
    </template>
    <details class="diagnostic-tasks matched-library"><summary>Matched task materials · {{ tasks.length }} versions</summary><p>Pairs match the editing structure and data requirements. Participant difficulty has not yet been established.</p><div v-for="task in tasks" :key="task.id" class="matched-task-row"><span>{{ task.family_id }} · {{ task.variant_id.toUpperCase() }}</span><strong>{{ task.title }}</strong></div></details>
    <div class="section-label">Experiment records</div>
    <p class="field-help">The unified exports retain unfinished tasks and repeated attempts. Local authored checks remain separate from participant evidence. Human interpretation and repair coding stay pending.</p>
    <div class="experiment-export-actions"><button class="button subtle" :disabled="busy" @click="emit('refresh')">Refresh records</button><a href="/api/experiment/export?format=json" download class="button ghost"><Download :size="14"/> JSON</a><a href="/api/experiment/export?format=csv" download class="button ghost"><Download :size="14"/> CSV</a></div>
    <ExperimentSummary v-if="aggregate" :report="aggregate"/>
    <section v-if="aggregate" class="archive-attempts">
      <div class="section-label">Inspect individual attempts</div>
      <p class="field-help">Researcher review opens a saved record without changing the active workspace. Coding drafts remain separate from scores.</p>
      <button v-for="attempt in [...aggregate.attempt_rows].reverse()" :key="attempt.session_id" class="archive-attempt" :aria-label="`Inspect attempt ${attempt.session_id}`" @click="emit('inspect', attempt.session_id)">
        <div><strong>{{ attempt.participant_id }} · Task {{ attempt.trial_index }}</strong><small>{{ conditionName(attempt.condition) }} · {{ attempt.task_id }} · {{ attempt.evidence_kind === 'participant' ? 'Participant record' : 'Local authored check' }}</small></div><span>{{ attempt.status.replaceAll('_', ' ') }}</span><ArrowUpRight :size="16"/>
      </button>
      <p v-if="!aggregate.attempt_rows.length" class="field-help">No assigned attempts have been recorded.</p>
    </section>
    <details v-if="aggregate" class="report-raw"><summary>View unified experiment records</summary><pre>{{ JSON.stringify(aggregate, null, 2) }}</pre></details>
  </div>
</template>
