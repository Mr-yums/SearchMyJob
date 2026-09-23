import { tr } from '../../shared/i18n/index.js';

import { nextTick } from 'vue';
export function registerConversation(ctx) {
  ctx.draftKey = function draftKey(id = ctx.conversationId.value) {
    return 'smj-chat-draft-' + id;
  };
  ctx.chooseConversation = async function chooseConversation(id) {
    ctx.saveDraft();
    ctx.conversationId.value = id;
    localStorage.setItem('smj-conversation', id);
    ctx.draft.value = localStorage.getItem(ctx.draftKey()) || '';
    await ctx.refresh();
    ctx.scrollMessages();
  };
  ctx.newConversation = async function newConversation() {
    await ctx.action(async () => {
      const c = await ctx.api('conversations', {});
      await ctx.chooseConversation(c.id);
    });
  };
  ctx.resetConversation = async function resetConversation() {
    await ctx.action(async () => {
      const c = await ctx.api('conversations/' + ctx.conversationId.value + '/reset', {});
      await ctx.chooseConversation(c.id);
    }, tr('Chat réinitialisé. L’ancien fil reste consultable dans les archives.'));
  };
  ctx.renameConversation = async function renameConversation(title) {
    await ctx.action(() =>
      ctx.api('conversations/' + ctx.conversationId.value + '/rename', {
        title,
      }),
    );
  };
  ctx.preparePrompt = function preparePrompt(text) {
    ctx.tab.value = 'conversation';
    ctx.draft.value = ctx.draft.value.trim() ? ctx.draft.value + '\n\n' + text : text;
    ctx.saveDraft();
    nextTick(() => document.querySelector('[data-chat-input]')?.focus());
  };
  ctx.scrollMessages = function scrollMessages() {
    nextTick(() =>
      ctx.messageLists.value.forEach((el) => {
        if (el) el.scrollTop = el.scrollHeight;
      }),
    );
  };
  ctx.send = async function send() {
    if (!ctx.draft.value.trim() || ctx.conversationArchived.value) return;
    const sent = ctx.draft.value,
      cid = ctx.conversationId.value;
    await ctx.action(async () => {
      await ctx.api('chat', {
        text: sent,
        provider: ctx.provider.value,
        conversation_id: cid,
      });
      if (ctx.conversationId.value === cid && ctx.draft.value === sent) ctx.draft.value = '';
      if (localStorage.getItem(ctx.draftKey(cid)) === sent)
        localStorage.removeItem(ctx.draftKey(cid));
      if (cid === 'main') localStorage.removeItem('smj-draft');
    }, tr('Les agents préparent leur réponse.'));
  };
  ctx.saveDraft = function saveDraft() {
    localStorage.setItem(ctx.draftKey(), ctx.draft.value);
  };
  return () => {};
}
