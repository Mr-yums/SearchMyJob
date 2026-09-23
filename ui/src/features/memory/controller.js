import { tr } from '../../shared/i18n/index.js';

import { nextTick } from 'vue';
export function registerMemory(ctx) {
  ctx.preferenceValues = function preferenceValues() {
    return {
      theme: ctx.theme.value,
      page_width: ctx.pageWidth.value,
      agent_width: ctx.agentWidth.value,
      layout: ctx.layoutMode.value,
      panels: [...ctx.panels.value],
      tabs: [...ctx.openedTabs.value],
      collapsed: ctx.collapsed.value,
      provider: ctx.provider.value,
    };
  };
  ctx.persistMemory = function persistMemory(path, body) {
    ctx.memoryStatus.value = tr('Sauvegarde…');
    ctx.memoryQueue = ctx.memoryQueue.then(async () => {
      try {
        const r = await fetch('/api/' + path, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Workspace-Token': ctx.state.value.token,
          },
          body: JSON.stringify(body),
        });
        if (!r.ok) throw Error();
        ctx.memoryStatus.value = tr('Préférences et brouillons sauvegardés');
        if (
          path === 'heartbeat-draft' &&
          localStorage.getItem('smj-heartbeat-draft') === JSON.stringify(body.values)
        )
          localStorage.removeItem('smj-heartbeat-draft');
        if (
          path === 'preferences' &&
          localStorage.getItem('smj-preferences-pending') === JSON.stringify(body)
        )
          localStorage.removeItem('smj-preferences-pending');
      } catch {
        ctx.memoryStatus.value = tr('Sauvegarde serveur à réessayer');
      }
    });
  };
  ctx.hydrateMemory = async function hydrateMemory() {
    try {
      const r = await fetch('/api/workspace-memory');
      if (!r.ok) throw Error();
      const data = await r.json();
      let pendingPrefs = null,
        pendingHeartbeat = null;
      try {
        pendingPrefs = JSON.parse(localStorage.getItem('smj-preferences-pending'));
        pendingHeartbeat = JSON.parse(localStorage.getItem('smj-heartbeat-draft'));
      } catch {}
      const p = pendingPrefs || data.preferences;
      if (p) {
        ctx.theme.value = p.theme;
        if (['centered', 'full'].includes(p.page_width)) ctx.pageWidth.value = p.page_width;
        if (['normal', 'full'].includes(p.agent_width)) ctx.agentWidth.value = p.agent_width;
        ctx.panels.value = p.panels;
        ctx.layoutMode.value = p.layout;
        ctx.openedTabs.value = p.tabs;
        ctx.collapsed.value = p.collapsed;
        ctx.provider.value = p.provider;
        if (ctx.layoutMode.value > 1) ctx.tab.value = ctx.panels.value[0];
      }
      if (pendingHeartbeat || data.heartbeat_draft)
        ctx.settings.value = {
          ...ctx.settings.value,
          ...(pendingHeartbeat || data.heartbeat_draft),
        };
      await nextTick();
      ctx.memoryReady.value = true;
      if ((!p || pendingPrefs) && ctx.activation.value?.completed !== false)
        ctx.persistMemory('preferences', ctx.preferenceValues());
      else ctx.memoryStatus.value = tr('Préférences et brouillons sauvegardés');
      if (pendingHeartbeat)
        ctx.persistMemory('heartbeat-draft', {
          values: {
            ...ctx.settings.value,
          },
        });
    } catch {
      ctx.memoryStatus.value = tr('Préférences serveur indisponibles');
    }
  };
  return () => {};
}
