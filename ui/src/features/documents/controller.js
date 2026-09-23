import { watch } from 'vue';
export function registerDocuments(ctx) {
  ctx.editDoc = function editDoc(d) {
    ctx.selected.value = d;
    ctx.docText.value = localStorage.getItem('smj-doc-' + d.id) ?? d.text;
    ctx.docApproved.value = !!d.approved;
  };
  return () => {
    watch(ctx.docText, (v) => {
      if (ctx.selected.value) localStorage.setItem('smj-doc-' + ctx.selected.value.id, v);
    });
  };
}
