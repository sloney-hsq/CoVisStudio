<script setup>
import { humanize } from '../chart.js'
defineProps({ report: Object })
</script>

<template>
  <section class="experiment-summary">
    <div class="report-stats"><div><span>Attempts</span><strong>{{ report.attempt_count }}</strong></div><div><span>Assigned trials</span><strong>{{ report.assigned_trial_count }}</strong></div><div><span>Human review</span><strong class="pending-label">Pending</strong></div></div>
    <div v-for="participant in report.participants" :key="`${participant.participant_id}-${participant.participant_slot}-${participant.evidence_kind}`" class="participant-summary">
      <strong>{{ participant.participant_id }} · Slot {{ participant.participant_slot }}</strong><small>{{ humanize(participant.evidence_kind) }}</small>
      <div class="participant-condition" v-for="(result, condition) in participant.conditions" :key="condition"><span>{{ condition === 'direct' ? 'Direct editing' : 'Evidence-linked revision' }}</span><div><b>{{ result.technical_correct }} / {{ result.assigned }}</b> technically correct <small>{{ result.observed }} observed · {{ result.missing }} missing</small></div></div>
    </div>
    <p class="field-help">{{ report.selection_rule }}. All attempts remain in the export. Technical correctness does not approve business reasoning or spoken responses.</p>
  </section>
</template>
