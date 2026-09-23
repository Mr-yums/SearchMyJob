import { tr } from '../../shared/i18n/index.js';

import { watch } from 'vue';
export function registerProfile(ctx) {
  ctx.saveProfile = async function saveProfile() {
    const sent = ctx.profile.value;
    await ctx.action(async () => {
      await ctx.api('profile', {
        text: sent,
      });
      if (ctx.profile.value === sent) {
        localStorage.removeItem('smj-profile-draft');
        ctx.editingProfile.value = false;
      }
    }, tr('Profil enregistré. Les agents disposent de cette version.'));
  };
  ctx.importCV = async function importCV(event) {
    const file = event.target.files[0];
    if (!file) return;
    await ctx.action(async () => {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch('/api/import', {
        method: 'POST',
        headers: {
          'X-Workspace-Token': ctx.state.value.token,
        },
        body: fd,
      });
      const out = await r.json();
      if (!r.ok) throw Error(out.detail);
      ctx.profile.value = ctx.profile.value ? ctx.profile.value + '\n\n' + out.text : out.text;
      await ctx.refresh();
    }, tr('Fichier original conservé dans Documents ; texte ajouté au brouillon du profil.'));
    event.target.value = '';
  };
  return () => {
    watch(ctx.profile, (v) => {
      if (v !== ctx.state.value?.profile) localStorage.setItem('smj-profile-draft', v);
      else localStorage.removeItem('smj-profile-draft');
    });
  };
}
