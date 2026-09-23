<script setup>
import { toRefs } from 'vue';
import { tr } from '../../shared/i18n/index.js';

import WatchPanel from './components/WatchPanel.vue';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const { state, settings, loading, navigate, busy, api, action, mail } = toRefs(props.model);
</script>
<template>
  <WatchPanel
    :state="state"
    :settings="settings"
    :busy="busy"
    :loading="loading"
    @save="action(() => api('settings', settings), tr('Réglages de veille enregistrés.'))"
    @checkup="action(() => api('checkup'), tr('Check-up lancé.'))"
    @mail="navigate('mail')"
  />
</template>
