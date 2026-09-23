import { watch } from 'vue';
export function registerMonitoring(ctx) {
  return () => {
    watch(
      ctx.settings,
      () => {
        if (!ctx.memoryReady.value) return;
        localStorage.setItem('smj-heartbeat-draft', JSON.stringify(ctx.settings.value));
        clearTimeout(ctx.heartbeatTimer);
        ctx.heartbeatTimer = setTimeout(
          () =>
            ctx.persistMemory('heartbeat-draft', {
              values: {
                ...ctx.settings.value,
              },
            }),
          600,
        );
      },
      {
        deep: true,
      },
    );
  };
}
