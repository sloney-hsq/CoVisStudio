<script setup>
defineProps({ report: Object })
const labels = { none: 'No response saved', incomplete: 'Response incomplete', stale: 'Charts changed — review and save again', current: 'Response saved for the current canvas' }
</script>

<template>
  <section class="task-response-review">
    <div class="section-label">Analysis response</div>
    <p class="response-status" :class="{ 'response-stale': report.task_response_status === 'stale' }">{{ labels[report.task_response_status] }}</p>
    <p v-if="report.task_response" class="field-help">Saved for v{{ report.task_response_recorded_revision }} · Current canvas v{{ report.revision }}. Human interpretation remains pending.</p>
    <dl v-if="report.task_response" class="response-fields">
      <div><dt>Conclusion</dt><dd>{{ report.task_response.conclusion || 'Not provided' }}</dd></div>
      <div><dt>Evidence and rationale</dt><dd>{{ report.task_response.rationale || 'Not provided' }}</dd></div>
      <div><dt>Category origin</dt><dd>{{ report.task_response.object_origin || 'Not provided' }}</dd></div>
      <div><dt>Calculation scope</dt><dd>{{ report.task_response.calculation_scope || 'Not provided' }}</dd></div>
    </dl>
  </section>
</template>
