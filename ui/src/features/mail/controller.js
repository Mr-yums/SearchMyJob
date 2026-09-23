import { tr } from '../../shared/i18n/index.js';

export function registerMail(ctx) {
  ctx.openEmail = function openEmail(e) {
    ctx.mailSelected.value = e;
    ctx.mailForm.value = {
      to: e.to,
      subject: e.subject,
      body: e.body,
    };
    ctx.mailConfirm.value = false;
  };
  ctx.connectMail = async function connectMail(event) {
    const file = event.target.files[0];
    if (!file) return;
    await ctx.action(async () => {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch('/api/mail/connect', {
        method: 'POST',
        headers: {
          'X-Workspace-Token': ctx.state.value.token,
        },
        body: fd,
      });
      const out = await r.json();
      if (!r.ok) throw Error(typeof out.detail === 'string' ? out.detail : tr('Fichier refusé.'));
      window.open(out.auth_url, '_blank', 'noopener');
      await ctx.refresh();
    }, tr('Autorise SearchMyJob dans l’onglet Google qui vient de s’ouvrir : la connexion se confirmera ici toute seule.'));
    event.target.value = '';
  };
  ctx.saveEmail = async function saveEmail() {
    await ctx.action(async () => {
      ctx.mailSelected.value = await ctx.api(
        'emails/' + ctx.mailSelected.value.id,
        ctx.mailForm.value,
      );
    }, tr('Brouillon enregistré.'));
  };
  ctx.sendEmail = async function sendEmail() {
    await ctx.action(async () => {
      await ctx.api('emails/' + ctx.mailSelected.value.id, ctx.mailForm.value);
      ctx.mailSelected.value = await ctx.api('emails/' + ctx.mailSelected.value.id + '/send', {
        confirm: ctx.mailConfirm.value,
      });
      ctx.mailConfirm.value = false;
    }, tr('E-mail envoyé depuis ta boîte.'));
  };
  ctx.discardEmail = async function discardEmail() {
    await ctx.action(async () => {
      await ctx.api('emails/' + ctx.mailSelected.value.id + '/discard');
      ctx.mailSelected.value = null;
    }, tr('Brouillon écarté.'));
  };
  ctx.emailFromDoc = async function emailFromDoc(d) {
    await ctx.action(async () => {
      const out = await ctx.api('emails', {
        document_id: d.id,
      });
      ctx.navigate('mail');
      ctx.openEmail(out);
    }, tr('E-mail préparé à partir de la lettre. Indique le destinataire, relis, puis envoie.'));
  };
  ctx.newEmail = async function newEmail() {
    await ctx.action(async () => {
      ctx.openEmail(await ctx.api('emails', {}));
    }, tr('Nouveau brouillon vide.'));
  };
  return () => {};
}
