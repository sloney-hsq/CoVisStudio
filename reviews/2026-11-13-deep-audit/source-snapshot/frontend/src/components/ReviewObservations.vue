<script setup>
defineProps({ interaction: Object })
</script>

<template>
  <section class="review-observations">
    <div class="section-label">Recorded interaction</div>
    <dl class="observation-counts">
      <div><dt>Saved sets</dt><dd>{{ interaction.category_sets.saved_count }}</dd></div>
      <div><dt>Set applications</dt><dd>{{ interaction.category_sets.application_count }}</dd></div>
      <div><dt>Cards generated</dt><dd>{{ interaction.revision_cards.generated_count }}</dd></div>
      <div><dt>Cards displayed</dt><dd>{{ interaction.revision_cards.displayed_count }}</dd></div>
      <div><dt>Details opened</dt><dd>{{ interaction.revision_cards.detail_opened_count }}</dd></div>
      <div><dt>User confirmed</dt><dd>{{ interaction.revision_cards.user_confirmed_count }}</dd></div>
      <div><dt>Model applied</dt><dd>{{ interaction.revision_cards.model_applied_count }}</dd></div>
    </dl>
    <p class="field-help">Displayed means on screen in a visible page. It does not show that a person read or understood the card. User confirmation is recorded after a successful Apply action.</p>
    <details v-if="interaction.revision_cards.proposals.length" class="observed-intervals">
      <summary>Summary and detail exposure</summary>
      <div v-for="(item, index) in interaction.revision_cards.proposals" :key="item.proposal_id" class="observed-proposal">
        <strong>Proposal {{ index + 1 }}</strong>
        <span>Summary: {{ (item.closed_visible_ms_by_surface.summary / 1000).toFixed(2) }}s</span>
        <span>Detail: {{ (item.closed_visible_ms_by_surface.detail / 1000).toFixed(2) }}s</span>
        <small v-if="item.open_visible_interval_count">{{ item.open_visible_interval_count }} ongoing {{ item.open_visible_interval_count === 1 ? 'interval' : 'intervals' }} · Duration pending</small>
      </div>
      <p class="field-help">Durations cover completed browser visibility intervals. Surfaces are reported separately; these are not reading times.</p>
    </details>
  </section>
</template>
