<script setup>
import { computed } from 'vue'
import { CheckCheck, CircleHelp, TriangleAlert } from 'lucide-vue-next'
import { toolFeedback } from '../toolFeedback.js'
const props = defineProps({ result: Object })
const feedback = computed(() => props.result && toolFeedback(props.result))
</script>

<template>
  <div v-if="feedback" class="tool-feedback" :class="feedback.tone" role="status" aria-label="Actual chart action">
    <TriangleAlert v-if="feedback.tone === 'failed'" :size="17"/>
    <CircleHelp v-else-if="feedback.tone === 'pending' || feedback.tone === 'neutral'" :size="17"/>
    <CheckCheck v-else :size="17"/>
    <div><strong>{{ feedback.title }}</strong><span>{{ feedback.detail }}</span></div>
  </div>
</template>

<style scoped>
.tool-feedback { display:flex; gap:10px; padding:11px 14px; margin:0 20px 12px; border:1px solid #d8e7e2; border-radius:10px; background:#f0f7f4; color:#296958; }
.tool-feedback > svg { flex:none; margin-top:2px; }
.tool-feedback strong,.tool-feedback span { display:block; font-size:12px; line-height:1.55; }
.tool-feedback span { color:#5e736d; }
.tool-feedback.pending { background:#faf7ee; border-color:#e8dfc9; color:#766130; }
.tool-feedback.failed { background:#fbf1ef; border-color:#eedbd5; color:#934f3e; }
</style>
