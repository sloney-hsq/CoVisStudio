<script setup>
import { computed } from 'vue'
const props = defineProps({ delivery: Object })
const commits = computed(() => props.delivery.requests.flatMap(request => request.commits).map(commit => {
  const targets = commit.view_ids
  const surfaces = props.delivery.chart_surfaces.filter(surface => surface.revision === commit.revision)
  return { ...commit, targets,
    rendered: targets.filter(id => surfaces.some(surface => surface.view_id === id && surface.renders.length)).length,
    visible: targets.filter(id => surfaces.some(surface => surface.view_id === id && surface.exposures.length)).length }
}))
const speech = computed(() => props.delivery.responses.filter(response => response.received_audio_samples || response.playback))
function samples(value) { return new Intl.NumberFormat('en-US').format(value || 0) }
</script>

<template>
  <section class="delivery-review" aria-label="Execution and delivery">
    <div class="section-label">Execution & delivery</div>
    <p>A committed change, a visible chart and a played explanation are separate observations.</p>
    <table v-if="commits.length"><thead><tr><th>Commit</th><th>Targets</th><th>Rendered</th><th>Visible</th></tr></thead>
      <tbody><tr v-for="commit in commits" :key="commit.event_id || commit.index">
        <td>Version {{ commit.revision }}</td><td>{{ commit.targets.join(', ') || 'Dashboard' }}</td>
        <td>{{ commit.rendered }} / {{ commit.targets.length }}</td><td>{{ commit.visible }} / {{ commit.targets.length }}</td>
      </tr></tbody></table>
    <p v-else>No chart commit recorded.</p>
    <article v-for="response in speech" :key="response.response_id" class="delivery-speech">
      <div><strong>{{ response.playback_status.replaceAll('_', ' ') }}</strong><code>{{ response.response_id }}</code></div>
      <p>{{ samples(response.playback?.played_samples) }} / {{ samples(response.received_audio_samples) }} source samples output</p>
      <small>{{ response.playback?.measurement === 'source_cursor' ? 'AudioWorklet receipt' : response.playback?.measurement === 'estimate' ? 'Earlier audio-clock estimate' : 'Playback receipt pending' }} · Word alignment unknown</small>
    </article>
    <p class="delivery-note">Human listening and semantic consistency: pending review. Output samples do not establish hearing or understanding.</p>
  </section>
</template>

<style scoped>
.delivery-review { margin: 22px 0; padding: 18px; border: 1px solid #dce5df; border-radius: 14px; background: #fafcf9; }
p { color: #64756e; font-size: 12px; line-height: 1.6; }
table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
th, td { padding: 9px 5px; border-bottom: 1px solid #e3eae4; }
th { color: #61776e; font-weight: 600; }
.delivery-speech { margin-top: 14px; padding-top: 12px; border-top: 1px solid #e3eae4; }
.delivery-speech > div { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
strong { text-transform: capitalize; color: #285f53; font-size: 13px; }
code { color: #6b7871; font-size: 10px; overflow-wrap: anywhere; }
small { font-size: 11px; color: #718176; }
.delivery-note { margin-bottom: 0; }
</style>
