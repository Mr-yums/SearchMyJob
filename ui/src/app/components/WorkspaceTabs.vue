<script setup>
import { toRefs } from 'vue';
import AppIcon from '../../shared/components/AppIcon.vue';
import { tr } from '../../shared/i18n/index.js';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const { tab, selected, pages, openedTabs, sidebarHidden, navigate, closeTab, moveTab } = toRefs(
  props.model,
);
</script>
<template>
  <div v-if="sidebarHidden" class="workspace-tabs" role="tablist" :aria-label="tr('Vues ouvertes')">
    <div v-for="(id, i) in openedTabs" :key="id" class="tab-item" :class="{ selected: tab === id }">
      <button
        role="tab"
        :id="'tab-' + id"
        :aria-selected="tab === id"
        :tabindex="tab === id ? 0 : -1"
        :aria-controls="'workspace-content'"
        @click="navigate(id)"
        @keydown="moveTab($event, i)"
      >
        <AppIcon :name="id" :size="16" />{{ tr(pages.find((p) => p[0] === id)?.[2]) }}</button
      ><button
        v-if="id !== 'conversation'"
        class="tab-close"
        :aria-label="tr('Fermer l’onglet ') + tr(pages.find((p) => p[0] === id)?.[2])"
        @click="closeTab(id)"
      >
        <AppIcon name="close" :size="12" />
      </button>
    </div>
  </div>
</template>
