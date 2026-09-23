<script setup>
import { toRefs } from 'vue';
import { tr } from '../../shared/i18n/index.js';

import UsageSummary from './components/UsageSummary.vue';
import AISetup from './components/AISetup.vue';
import SourceSetup from './components/SourceSetup.vue';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const { state } = toRefs(props.model);
</script>
<template>
  <section class="narrow">
    <div class="page-heading compact">
      <div>
        <h1>{{ tr('Connexions') }}</h1>
        <p>{{ tr('Ton IA et tes sources, configurées séparément.') }}</p>
      </div>
    </div>
    <div class="card">
      <h2>{{ tr('Fournisseur IA') }}</h2>
      <AISetup :token="state.token" />
    </div>
    <div class="card">
      <h2>{{ tr('Sources de recherche') }}</h2>
      <SourceSetup :token="state.token" :criteria="state.criteria" />
    </div>
    <UsageSummary :budget="state.bright_budget" :usage="state.agent_usage" />
  </section>
</template>
