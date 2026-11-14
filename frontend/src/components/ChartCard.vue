<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, ScatterChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Check, Expand, SlidersHorizontal, LockKeyhole, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { chartOption, humanize, metricNames, formatRange } from '../chart.js'
import { observeChartVisibility } from '../chartVisibility.js'
echarts.use([BarChart, LineChart, PieChart, ScatterChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, CanvasRenderer])
const props = defineProps({ view: Object, selected: Boolean, entities: { type: Array, default: () => [] }, revision: Number, readonly: Boolean, telemetryActive: { type: Boolean, default: false } })
const emit = defineEmits(['select', 'edit', 'entity', 'rendered', 'expand', 'move', 'telemetry'])
const element = ref(null)
let chart, observer, visibility, completedIdentity = null, renderSequence = 0
const surfaceId = crypto.randomUUID()
const scope = computed(() => `${props.view.source.region || 'All regions'} · ${formatRange(props.view.source.start, props.view.source.end)}`)
const members = computed(() => props.view.source.categories ? 'Fixed categories' : props.view.source.top_n ? `Top ${props.view.source.top_n} by ${metricNames[props.view.source.rank_by]?.toLowerCase()}` : 'All matching groups')
function render() {
  const revision = props.revision, sequence = ++renderSequence
  const identity = { view_id: props.view.id, revision, render_generation: sequence, surface_id: surfaceId }
  completedIdentity = null
  visibility.beginRender(identity)
  const finished = () => {
    chart.off('finished', finished)
    requestAnimationFrame(() => {
      if (sequence === renderSequence) {
        completedIdentity = { ...identity, render_completed_client_ms: performance.now() }
        emit('rendered', { ...completedIdentity, notification_kind: 'render_completed' })
        visibility.rendered(identity)
      }
    })
  }
  chart.on('finished', finished)
  chart.setOption(chartOption(props.view, props.entities), true)
}
onMounted(() => {
  chart = echarts.init(element.value)
  visibility = observeChartVisibility(element.value, { enabled: props.telemetryActive, surfaceId,
    emit: (name, details, client_ms) => emit('telemetry', { name, details, client_ms }) })
  chart.on('click', params => emit('entity', props.view.id, params.data.rawLabel))
  observer = new ResizeObserver(() => chart.resize())
  observer.observe(element.value)
  render()
})
watch(() => [props.view, props.entities, props.revision], render, { deep: true, flush: 'post' })
watch(() => props.telemetryActive, value => {
  if (value && completedIdentity) emit('rendered', { ...completedIdentity, notification_kind: 'existing_render' })
  visibility.setEnabled(value)
})
onBeforeUnmount(() => { ++renderSequence; visibility.dispose(); observer.disconnect(); chart.dispose() })
defineExpose({
  image: () => chart.getDataURL({ type: 'jpeg', pixelRatio: 1, backgroundColor: '#fff' }),
  canvas: () => chart.renderToCanvas({ pixelRatio: 1, backgroundColor: '#fff' }),
})
</script>
<template>
  <article class="chart-card" :class="{ selected }" :data-view-id="view.id">
    <header class="chart-header">
      <button class="view-number" :class="{ active: selected }" :aria-label="`${selected ? 'Deselect' : 'Select'} chart ${view.number}`" :aria-pressed="selected" @click="emit('select', view.id)"><Check v-if="selected" :size="15"/><span v-else>{{ String(view.number).padStart(2, '0') }}</span></button>
      <div class="chart-heading"><h3>{{ view.title }}</h3><p>{{ metricNames[view.source.metric] }} <span>by {{ view.source.dimension }}</span></p></div>
      <div class="chart-actions"><button v-if="selected && !readonly" class="icon-button" aria-label="Move chart left" @click="emit('move', view.id, -1)"><ChevronLeft :size="15"/></button><button v-if="selected && !readonly" class="icon-button" aria-label="Move chart right" @click="emit('move', view.id, 1)"><ChevronRight :size="15"/></button><button class="icon-button" aria-label="Expand chart" @click="emit('expand', view.id)"><Expand :size="16"/></button><button v-if="!readonly" class="icon-button" aria-label="Edit chart" @click="emit('edit', view.id)"><SlidersHorizontal :size="17"/></button></div>
    </header>
    <div class="chart-scope"><span>{{ scope }}</span><span class="scope-status">{{ humanize(view.source.status) }}</span></div>
    <div ref="element" class="chart-plot" role="img" :aria-label="`${view.title}, ${view.data.rows.length} data groups`"></div>
    <div v-if="entities.length" class="entity-selection"><span>Referenced</span><button v-for="label in entities" :key="label" @click="emit('entity', view.id, label)">{{ humanize(label) }} <span>×</span></button></div>
    <footer class="chart-footer"><span><LockKeyhole v-if="view.source.categories" :size="12"/>{{ members }}</span><span>{{ view.data.rows.length }} groups · v{{ revision }}</span></footer>
  </article>
</template>
