<script setup>
import { computed } from 'vue'
import { humanize } from '../chart.js'
const props = defineProps({ trial: Object })
const counts = computed(() => props.trial.process.counts)
const time = computed(() => props.trial.timing.elapsed_seconds === null ? 'Not started' : `${props.trial.timing.elapsed_seconds.toFixed(1)} s`)
const timeLabels = { not_started: 'Not started', ongoing: 'In progress', observed_chart_submission: 'Correct chart submission observed', censored: 'Unfinished / censored' }
</script>

<template>
  <section class="trial-review">
    <div class="section-label">Assigned task record</div>
    <div class="trial-identity"><strong>{{ trial.identity.participant_id }} · Task {{ trial.identity.trial_index }} of 4</strong><span>{{ humanize(trial.identity.condition) }} · Version {{ trial.identity.variant_id.toUpperCase() }}</span><small>{{ humanize(trial.identity.evidence_kind) }} · {{ trial.identity.task_id }}</small></div>
    <dl class="trial-results">
      <div><dt>Task outcome</dt><dd>{{ humanize(trial.outcome.status) }}</dd></div>
      <div><dt>Technical requirements</dt><dd>{{ trial.outcome.technical_completed ? 'Met' : 'Not met' }}</dd></div>
      <div><dt>Current written response</dt><dd>{{ trial.outcome.response_complete_current ? 'Required answers saved' : 'Incomplete or outdated' }}</dd></div>
      <div><dt>Recorded task time</dt><dd>{{ time }}</dd></div>
      <div><dt>Time analysis</dt><dd>{{ timeLabels[trial.timing.time_analysis_status] }}</dd></div>
      <div><dt>Business interpretation</dt><dd class="pending-label">Pending human review</dd></div>
      <div><dt>Repair coding</dt><dd class="pending-label">Pending human review</dd></div>
    </dl>
    <div class="section-label">Recorded process</div>
    <dl class="observation-counts">
      <div><dt>Requests accepted</dt><dd>{{ counts.request_accepted }}</dd></div>
      <div><dt>Tool commits</dt><dd>{{ counts.tool_committed }}</dd></div>
      <div><dt>Tool failures</dt><dd>{{ counts.tool_failed }}</dd></div>
      <div><dt>Evidence selections</dt><dd>{{ counts.evidence_selected }}</dd></div>
      <div><dt>Undo / restore</dt><dd>{{ counts.undo }} / {{ counts.restore }}</dd></div>
      <div><dt>Playback starts / ends</dt><dd>{{ counts.playback_start }} / {{ counts.playback_end }}</dd></div>
    </dl>
    <p class="field-help">Counts cover the recorded task interval. They do not infer attention, misunderstanding or repair. Unfinished attempts are retained.</p>
  </section>
</template>
