import { tr } from '../../shared/i18n/index.js';

import { watch, nextTick } from 'vue';
export function registerOpportunities(ctx) {
  ctx.search = async function search(force = false) {
    await ctx.action(
      () =>
        ctx.api(
          'search?force=' +
            force +
            '&conversation_id=' +
            encodeURIComponent(ctx.conversationId.value),
          ctx.criteria.value,
        ),
      tr('Recherche lancée. L’IA analysera les résultats et répondra dans la conversation.'),
    );
  };
  ctx.generate = async function generate(o, kind) {
    await ctx.action(
      () =>
        ctx.api('generate', {
          offer_id: o.id,
          kind,
          provider: ctx.provider.value,
          conversation_id: ctx.conversationId.value,
        }),
      kind === 'email'
        ? tr(
            'E-mail en préparation. Tu le retrouveras dans Courrier, à compléter et relire avant envoi.',
          )
        : tr('Document en préparation. Tu le retrouveras dans Documents.'),
    );
  };
  return () => {
    watch(ctx.offerDetail, async (value) => {
      await nextTick();
      if (value && ctx.offerDialog.value && !ctx.offerDialog.value.open)
        ctx.offerDialog.value.showModal();
    });
  };
}
