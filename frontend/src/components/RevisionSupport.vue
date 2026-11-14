<script setup>
import { computed, ref } from 'vue'
import { Check, ChevronDown, Pencil, X } from 'lucide-vue-next'
import RevisionObservation from './RevisionObservation.vue'
import RevisionDetails from './RevisionDetails.vue'
import RevisionSummary from './RevisionSummary.vue'
const props = defineProps({ proposal: Object, state: Object, structured: Boolean, active: Boolean, busy: Boolean, readonly: Boolean })
const emit = defineEmits(['apply', 'revise', 'close', 'observation'])
const expanded = ref(false)
const pending = computed(() => props.proposal.status === 'pending')
const title = computed(() => pending.value ? (props.proposal.card.needs_confirmation ? 'Clarification needed' : 'Revision ready to apply') : props.proposal.status === 'committed' ? 'Revision committed' : 'Proposal replaced')
function toggle() {
  expanded.value = !expanded.value
  if (expanded.value) emit('observation', 'revision_card_opened', { proposal_id: props.proposal.id, surface: 'detail' })
}
</script>

<template>
  <section class="revision-support" :class="{ compact: !structured }" aria-label="Revision support">
    <RevisionObservation v-if="structured" :key="`${proposal.id}-${proposal.status}`" :proposal-id="proposal.id" :proposal-status="proposal.status" surface="summary" :active="active" @observation="(name, details, time) => emit('observation', name, details, time)">
      <div class="revision-support-heading"><div><span class="revision-interpretation-label">System interpretation</span><strong>{{ title }}</strong></div><button class="text-button revision-detail-toggle" :aria-expanded="expanded" @click="toggle">{{ expanded ? 'Summary' : 'Details' }}<ChevronDown :size="15" :class="{ collapsed: expanded }"/></button></div>
      <p v-if="proposal.card.question" class="revision-question">{{ proposal.card.question }}</p>
      <RevisionSummary v-if="!expanded" :card="proposal.card" :state="state"/>
      <RevisionObservation v-if="expanded" :proposal-id="proposal.id" :proposal-status="proposal.status" surface="detail" :active="active" @observation="(name, details, time) => emit('observation', name, details, time)"><RevisionDetails :card="proposal.card" :state="state"/></RevisionObservation>
    </RevisionObservation>
    <template v-else><strong class="revision-simple-title">{{ title }}</strong><p v-if="proposal.card.question" class="revision-question">{{ proposal.card.question }}</p><p v-else-if="pending" class="revision-question">Apply this proposal or modify it before continuing.</p></template>
    <div class="revision-support-footer"><p class="revision-publication-note">Review this system interpretation. You can correct the source, target charts, or conditions.</p><div class="revision-support-actions"><button class="text-button" :disabled="busy || readonly" @click="emit('revise')"><Pencil :size="14"/> Correct interpretation</button><button class="text-button" :disabled="busy" @click="emit('close')"><X :size="14"/> Close</button><button v-if="pending" class="button primary" :disabled="busy || readonly" @click="emit('apply')"><Check :size="15"/> Apply revision</button></div></div>
  </section>
</template>

<style scoped>
.revision-support{margin:18px 0 8px;padding:14px;border:1px solid #ccded2;border-left:3px solid #238579;border-radius:10px;background:#f5f9f3}.revision-support-heading{width:100%;display:flex;justify-content:space-between;align-items:center;gap:10px;text-align:left;padding:0 0 10px}.revision-support-heading strong,.revision-simple-title{font-size:14px;line-height:1.5;color:#315d4e}.revision-support-heading svg.collapsed{transform:rotate(-90deg)}.revision-question{font-size:14px;line-height:1.6;color:#66562e;background:#f9f4e7;padding:10px;margin:0 0 12px;border-radius:6px}.revision-publication-note{font-size:12px;line-height:1.55;color:#6a7c6e;margin-top:12px}.revision-support-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}.revision-support-actions .button{font-size:12px;padding:8px 10px;margin-left:auto}.revision-support-actions .text-button{font-size:12px}.compact{background:#f7f8f5;border-left:1px solid #ccded2}.compact .revision-simple-title{display:block;margin-bottom:8px}
</style>

<style scoped>
.revision-interpretation-label{display:block;font-size:11px;line-height:1.5;color:#647a6c;margin-bottom:2px}.revision-support-footer{position:sticky;bottom:0;background:#f5f9f3;padding:8px 0 2px;border-top:1px solid #dce6dd;margin-top:9px;z-index:1}.revision-support-footer .revision-publication-note{margin-top:0}.revision-support-footer .revision-support-actions{margin-top:6px}.compact .revision-support-footer{background:#f7f8f5}.revision-question{padding:8px;margin-bottom:8px}.revision-detail-toggle{font-size:12px;flex:none}
</style>
