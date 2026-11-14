<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { observeRevisionVisibility } from '../revisionVisibility.js'
const props = defineProps({ proposalId: String, proposalStatus: String, surface: String, active: { type: Boolean, default: true } })
const emit = defineEmits(['observation'])
const element = ref(null)
let observation
onMounted(() => {
  observation = observeRevisionVisibility(element.value, { proposalId: props.proposalId, proposalStatus: props.proposalStatus,
    surface: props.surface, enabled: props.active,
    emit: (name, details, clientMs) => emit('observation', name, details, clientMs) })
})
watch(() => props.active, value => observation?.setEnabled(value))
onBeforeUnmount(() => observation?.dispose())
</script>

<template><div ref="element" :data-revision-surface="surface"><slot/></div></template>
