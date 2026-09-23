import { tr } from '../../shared/i18n/index.js';

import { watch, nextTick } from 'vue';
export function registerLayout(ctx) {
  ctx.restoredPanels = function restoredPanels() {
    try {
      const value = JSON.parse(localStorage.getItem('smj-layout-panels'));
      return Array.isArray(value) &&
        value.length === 4 &&
        new Set(value).size === 4 &&
        value.every((v) => ctx.pages.some((p) => p[0] === v))
        ? value
        : ctx.defaultPanels.slice();
    } catch {
      return ctx.defaultPanels.slice();
    }
  };
  ctx.setPanel = function setPanel(index, value) {
    const previous = ctx.panels.value[index],
      other = ctx.panels.value.indexOf(value);
    if (other !== -1 && other !== index) ctx.panels.value[other] = previous;
    ctx.panels.value[index] = value;
    ctx.activePanel.value = index;
    if (ctx.tab.value !== value) ctx.tab.value = value;
  };
  ctx.changeLayout = function changeLayout(mode) {
    ctx.showLayouts.value = false;
    if (mode === ctx.layoutMode.value) return;
    if (mode === 1) {
      ctx.layoutMode.value = 1;
      ctx.activePanel.value = 0;
      return;
    }
    if (ctx.layoutMode.value === 1) ctx.setPanel(0, ctx.tab.value);
    ctx.layoutMode.value = mode;
    if (ctx.activePanel.value >= mode) ctx.activePanel.value = 0;
    ctx.tab.value = ctx.panels.value[ctx.activePanel.value];
  };
  ctx.focusPanel = function focusPanel(index) {
    ctx.activePanel.value = index;
    if (ctx.layoutMode.value > 1) ctx.tab.value = ctx.panels.value[index];
  };
  ctx.openBeside = function openBeside(page) {
    if (ctx.layoutMode.value === 1) {
      ctx.changeLayout(2);
      ctx.setPanel(1, page);
    } else ctx.setPanel((ctx.activePanel.value + 1) % ctx.layoutMode.value, page);
  };
  ctx.restoreTabs = function restoreTabs() {
    try {
      const a = JSON.parse(localStorage.getItem('smj-open-tabs'));
      return Array.isArray(a)
        ? [...new Set(['conversation', ...a.filter((id) => ctx.pages.some((p) => p[0] === id))])]
        : ['conversation'];
    } catch {
      return ['conversation'];
    }
  };
  ctx.navigate = function navigate(id) {
    ctx.changeLayout(1);
    ctx.tab.value = id;
  };
  ctx.closeTab = function closeTab(id) {
    const i = ctx.openedTabs.value.indexOf(id);
    ctx.openedTabs.value = ctx.openedTabs.value.filter((x) => x !== id);
    if (ctx.tab.value === id)
      ctx.navigate(ctx.openedTabs.value[Math.max(0, i - 1)] || 'conversation');
  };
  ctx.moveTab = function moveTab(event, index) {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    const id =
      ctx.openedTabs.value[
        (index + delta + ctx.openedTabs.value.length) % ctx.openedTabs.value.length
      ];
    ctx.navigate(id);
    nextTick(() => document.getElementById('tab-' + id)?.focus());
  };
  return () => {
    for (const [state, key, attribute] of [
      [ctx.pageWidth, 'smj-page-width', 'pageWidth'],
      [ctx.agentWidth, 'smj-agent-width', 'agentWidth'],
    ]) {
      watch(
        state,
        (value) => {
          localStorage.setItem(key, value);
          document.documentElement.dataset[attribute] = value;
        },
        { immediate: true },
      );
    }

    watch(
      ctx.theme,
      (v) => {
        localStorage.setItem('smj-theme', v);
        if (v === 'classique') delete document.documentElement.dataset.theme;
        else document.documentElement.dataset.theme = v;
        const meta = document.querySelector('meta[name=theme-color]');
        if (meta) meta.content = ctx.themeColors[v];
      },
      {
        immediate: true,
      },
    );
    watch(ctx.tab, (value) => {
      if (ctx.layoutMode.value > 1 && ctx.panels.value[ctx.activePanel.value] !== value)
        ctx.setPanel(ctx.activePanel.value, value);
    });
    watch(ctx.layoutMode, (value) => localStorage.setItem('smj-layout-mode', String(value)));
    watch(ctx.panels, (value) => localStorage.setItem('smj-layout-panels', JSON.stringify(value)), {
      deep: true,
    });
    // [Sol] Presentation state is separate from persisted business data.
    watch(ctx.visiblePanels, ctx.scrollMessages);
    watch(ctx.collapsed, (v) => localStorage.setItem('smj-sidebar-collapsed', String(v)));
    // [OXIO 15/09/2026] Hors conversation, la barre de gauche disparaît ; un bouton d'en-tête la rappelle le temps d'un choix.
    // [OXIO] Le menu Disposition/Thème se referme après un choix, au clic extérieur et à Échap (sinon il recouvre la navigation sur mobile).
    watch(
      () => ctx.visiblePanels.value.join('|'),
      () => {
        ctx.forceSidebar.value = false;
      },
    );
    watch(ctx.tab, (v) => {
      if (!ctx.openedTabs.value.includes(v)) ctx.openedTabs.value.push(v);
    });
    watch(ctx.openedTabs, (v) => localStorage.setItem('smj-open-tabs', JSON.stringify(v)), {
      deep: true,
    });
    watch(
      [
        ctx.theme,
        ctx.pageWidth,
        ctx.agentWidth,
        ctx.layoutMode,
        ctx.panels,
        ctx.openedTabs,
        ctx.collapsed,
        ctx.provider,
      ],
      () => {
        if (!ctx.memoryReady.value || ctx.activation.value?.completed === false) return;
        localStorage.setItem('smj-preferences-pending', JSON.stringify(ctx.preferenceValues()));
        clearTimeout(ctx.preferenceTimer);
        ctx.memoryStatus.value = tr('Sauvegarde…');
        ctx.preferenceTimer = setTimeout(
          () => ctx.persistMemory('preferences', ctx.preferenceValues()),
          500,
        );
      },
      {
        deep: true,
      },
    );
  };
}
