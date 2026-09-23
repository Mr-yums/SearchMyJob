<script setup>
import { toRefs } from 'vue';
import AppIcon from '../../shared/components/AppIcon.vue';
import { tr } from '../../shared/i18n/index.js';
import LanguageSwitcher from '../../shared/components/LanguageSwitcher.vue';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const {
  state,
  selected,
  modes,
  themes,
  theme,
  pageWidth,
  agentWidth,
  layoutMode,
  changeLayout,
  showTasks,
  showLayouts,
  forceSidebar,
  sidebarHidden,
  navigate,
  busy,
  memoryStatus,
} = toRefs(props.model);
</script>
<template>
  <header class="app-header">
    <div class="app-identity">
      <button
        v-if="sidebarHidden"
        class="icon-button sidebar-reveal"
        :aria-label="tr('Afficher la navigation')"
        @click="forceSidebar = true"
      >
        <AppIcon name="menu" :size="18" /></button
      ><span class="header-spark"><AppIcon name="spark" :size="18" /></span
      ><strong>SearchMyJob</strong><span class="header-divider"></span
      ><span class="connection-label"><i></i>{{ busy ? tr('En cours') : tr('Connecté') }}</span>
    </div>
    <div class="header-actions">
      <LanguageSwitcher />
      <div class="layout-control">
        <button
          class="icon-button"
          :aria-label="tr('Choisir la disposition')"
          :aria-expanded="showLayouts"
          @click="showLayouts = !showLayouts"
        >
          <AppIcon name="sliders" :size="18" />
        </button>
        <div v-if="showLayouts" class="prefs-menu">
          <span class="prefs-label">{{ tr('Disposition') }}</span>
          <div class="layout-switch" role="group" :aria-label="tr('Nombre de fenêtres')">
            <button
              v-for="mode in modes"
              :key="mode"
              :aria-pressed="layoutMode === mode"
              @click="changeLayout(mode)"
            >
              {{ mode }} {{ mode === 1 ? tr('fenêtre') : tr('fenêtres') }}
            </button>
          </div>
          <span class="prefs-label">{{ tr('Thème') }}</span>
          <div
            class="layout-switch theme-switch"
            role="group"
            :aria-label="tr('Thème d’affichage')"
          >
            <button
              v-for="t in themes"
              :key="t[0]"
              :aria-pressed="theme === t[0]"
              @click="
                theme = t[0];
                showLayouts = false;
              "
            >
              <i class="theme-dot" :class="t[0]"></i>{{ tr(t[1]) }}
            </button>
          </div>
          <span class="prefs-label">{{ tr('Largeur des pages') }}</span>
          <div class="layout-switch" role="group" :aria-label="tr('Largeur des pages')">
            <button :aria-pressed="pageWidth === 'centered'" @click="pageWidth = 'centered'">
              {{ tr('Centrées') }}
            </button>
            <button :aria-pressed="pageWidth === 'full'" @click="pageWidth = 'full'">
              {{ tr('Pleine largeur') }}
            </button>
          </div>
          <span class="prefs-label">{{ tr('Affichage de l’agent') }}</span>
          <div class="layout-switch" role="group" :aria-label="tr('Affichage de l’agent')">
            <button :aria-pressed="agentWidth === 'normal'" @click="agentWidth = 'normal'">
              {{ tr('Normal') }}
            </button>
            <button :aria-pressed="agentWidth === 'full'" @click="agentWidth = 'full'">
              {{ tr('Pleine largeur') }}
            </button>
          </div>
          <small class="prefs-label" role="status">{{ tr(memoryStatus) }}</small
          ><UsageSummary :budget="state?.bright_budget" :usage="state?.agent_usage" />
        </div>
      </div>
      <button
        class="budget-mini"
        @click="navigate('connections')"
        :class="{ exhausted: state?.bright_budget?.blocked }"
        :aria-label="tr('Voir le budget Bright Data')"
      >
        <span class="budget-dot"></span>{{ state?.bright_budget?.used ?? '—'
        }}<span>/ {{ state?.bright_budget?.limit ?? '—' }}</span></button
      ><button
        class="icon-button task-toggle"
        :class="{ selected: showTasks }"
        :aria-expanded="showTasks"
        :aria-label="tr('Afficher ou masquer les tâches')"
        @click="showTasks = !showTasks"
      >
        <AppIcon name="heartbeat" :size="18" />
      </button>
    </div>
  </header>
</template>
