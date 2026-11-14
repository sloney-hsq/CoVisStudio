<script setup>
defineProps({ task: Object })
</script>

<template>
  <section class="analysis-brief">
    <span class="eyebrow">ANALYSIS TASK</span>
    <h3>{{ task.title }}</h3>
    <p class="task-goal">{{ task.business_goal || task.goal || task.description }}</p>
    <template v-if="task.context"><h4>Context</h4><p>{{ task.context }}</p></template>
    <template v-if="task.initial"><h4>Starting context</h4><p>{{ task.initial }}</p></template>
    <template v-if="(task.mandatory_outcomes || task.deliverables)?.length"><h4>Required outcomes</h4><ul><li v-for="item in task.mandatory_outcomes || task.deliverables" :key="item">{{ item }}</li></ul></template>
    <template v-if="task.constraints?.length"><h4>Constraints</h4><ul><li v-for="item in task.constraints" :key="item">{{ item }}</li></ul></template>
    <template v-if="task.response_prompt"><h4>Your response</h4><p>{{ task.response_prompt }}</p></template>
  </section>
</template>
