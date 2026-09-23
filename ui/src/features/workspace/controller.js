import { tr } from '../../shared/i18n/index.js';

import { onMounted, onUnmounted, watch } from 'vue';
export function registerWorkspace(ctx) {
  ctx.completeActivation = async function completeActivation() {
    localStorage.removeItem('smj-preferences-pending');
    await ctx.refresh(true);
    await ctx.hydrateMemory();
    ctx.activation.value = {
      completed: true,
    };
  };
  ctx.refresh = async function refresh(initial = false) {
    try {
      const requested = ctx.conversationId.value;
      const r = await fetch(
        '/api/state' + (requested ? '?conversation_id=' + encodeURIComponent(requested) : ''),
      );
      if (r.status === 404 && initial) {
        ctx.conversationId.value = '';
        return ctx.refresh(true);
      }
      if (!r.ok) throw Error(tr('Service indisponible'));
      const s = await r.json();
      if (ctx.conversationId.value !== requested) return;
      ctx.conversationId.value = s.conversation_id || requested;
      localStorage.setItem('smj-conversation', ctx.conversationId.value);
      const previous = ctx.state.value;
      if (!initial && previous) {
        if (ctx.profile.value === previous.profile) ctx.profile.value = s.profile;
        if (JSON.stringify(ctx.criteria.value) === JSON.stringify(previous.criteria))
          ctx.criteria.value = {
            ...s.criteria,
          };
        if (JSON.stringify(ctx.settings.value) === JSON.stringify(previous.settings))
          ctx.settings.value = {
            ...s.settings,
          };
      }
      ctx.state.value = s;
      if (initial) {
        ctx.criteria.value = {
          ...s.criteria,
        };
        ctx.settings.value = {
          ...s.settings,
        };
        ctx.profile.value = localStorage.getItem('smj-profile-draft') ?? s.profile;
      }
    } catch (e) {
      ctx.error.value = e.message;
    }
  };
  ctx.api = async function api(path, data) {
    ctx.error.value = '';
    const r = await fetch('/api/' + path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Workspace-Token': ctx.state.value.token,
      },
      body: JSON.stringify(data || {}),
    });
    let out = await r.json();
    if (!r.ok) {
      throw Error(
        typeof out.detail === 'string' ? out.detail : tr('Vérifie les champs du formulaire.'),
      );
    }
    await ctx.refresh();
    return out;
  };
  ctx.action = async function action(fn, message = '') {
    try {
      ctx.loading.value = true;
      await fn();
      ctx.notice.value = message;
    } catch (e) {
      ctx.error.value = e.message;
    } finally {
      ctx.loading.value = false;
    }
  };
  return () => {
    watch(
      () => ctx.state.value?.messages.length,
      (n, old) => {
        if (old === undefined || n !== old) ctx.scrollMessages();
      },
    );
    watch(
      () => ctx.state.value?.mail?.sender_name,
      (v) => {
        if (typeof v === 'string' && !ctx.senderName.value) ctx.senderName.value = v;
      },
    );
    onMounted(async () => {
      ctx.clockTimer = setInterval(() => {
        ctx.clockNow.value = Date.now();
      }, 1000);
      await ctx.refresh(true);
      try {
        const r = await fetch('/api/activation');
        if (r.ok) ctx.activation.value = await r.json();
      } catch {}
      await ctx.hydrateMemory();
      ctx.timer = setInterval(async () => {
        await ctx.refresh();
        if (!ctx.memoryReady.value) await ctx.hydrateMemory();
      }, 2500);
    });
    onUnmounted(() => {
      clearInterval(ctx.timer);
      clearInterval(ctx.clockTimer);
      clearTimeout(ctx.preferenceTimer);
      clearTimeout(ctx.heartbeatTimer);
    });
  };
}
