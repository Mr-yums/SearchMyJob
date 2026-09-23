<script setup>
import RecordList from '../../shared/components/RecordList.vue';
import { computed, nextTick, ref, toRefs } from 'vue';
import { tr } from '../../shared/i18n/index.js';

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const {
  tab,
  state,
  selected,
  docText,
  docApproved,
  busy,
  offers,
  date,
  api,
  action,
  mail,
  emailFromDoc,
  editDoc,
} = toRefs(props.model);
const expanded = ref(false);
const readerView = ref(null);
async function toggleView(value = !expanded.value) {
  expanded.value = value;
  await nextTick();
  readerView.value?.closest('.pane-content')?.scrollTo({ top: 0, behavior: 'instant' });
}
const isExpanded = computed(() => expanded.value && !!selected.value);
const listItems = computed(() =>
  state.value.documents.map((doc) => ({
    id: doc.id,
    title:
      state.value.offers.find((offer) => offer.id === doc.offer_id)?.title || tr('Offre archivée'),
    meta: `${doc.kind === 'cv' ? 'CV' : tr('Lettre')} · ${doc.approved ? tr('Validé par toi') : tr('Brouillon')} · ${date.value(doc.created)}`,
    category: doc.kind,
  })),
);
const listFilters = computed(() => [
  { value: 'cv', label: 'CV' },
  { value: 'letter', label: tr('Lettres') },
]);
function selectRecord(id) {
  editDoc.value(state.value.documents.find((doc) => doc.id === id));
}
</script>
<template>
  <section ref="readerView" class="documents-view" :class="{ 'reader-expanded': isExpanded }">
    <div class="page-heading compact">
      <div>
        <h1>Documents</h1>
        <p>{{ state.documents.length }}{{ tr(' documents enregistrés') }}</p>
      </div>
    </div>
    <div v-if="!state.documents.length" class="empty card">
      <h2>{{ tr('Aucun document') }}</h2>
      <p>{{ tr('Choisis une offre pour préparer un CV ou une lettre.') }}</p>
      <button @click="tab = 'offers'">
        {{ tr('Voir les opportunités →') }}
      </button>
    </div>
    <div v-if="state.imports?.length" class="card imported-documents" v-show="!isExpanded">
      <h3>{{ tr('Fichiers importés conservés') }}</h3>
      <p class="small">
        {{ tr('Les originaux de tes CV restent téléchargeables, même après un redémarrage.') }}
      </p>
      <a v-for="f in state.imports" :key="f.id" :href="'/api/imports/' + f.id + '/download'"
        >{{ f.name }} · {{ date(f.created) }} ↓</a
      >
    </div>
    <div class="documents-layout">
      <div v-show="!isExpanded" class="document-list">
        <RecordList
          :items="listItems"
          :selected-id="selected?.id"
          :filters="listFilters"
          @select="selectRecord"
        />
      </div>
      <div v-if="selected" class="card">
        <div class="reader-heading">
          <h2>{{ tr('Ton document') }}</h2>
          <button type="button" class="secondary" :aria-pressed="isExpanded" @click="toggleView()">
            {{ isExpanded ? tr('Vue classique') : tr('Vue complète') }}
          </button>
        </div>
        <textarea class="document-editor" aria-label="Document" v-model="docText"></textarea
        ><label class="check"
          ><input type="checkbox" v-model="docApproved" />{{
            tr(' J’ai relu et validé ce document')
          }}</label
        >
        <div class="form-actions">
          <button
            v-if="selected.kind === 'letter'"
            type="button"
            class="secondary"
            :disabled="busy"
            @click="emailFromDoc(selected)"
          >
            {{ tr('Préparer l’e-mail') }}
          </button>
          <a
            class="button secondary"
            :href="'/api/documents/' + selected.id + '/download?format=docx'"
            >{{ tr('DOCX enregistré ↓') }}</a
          ><a
            class="button secondary"
            :href="'/api/documents/' + selected.id + '/download?format=txt'"
            >{{ tr('Texte ↓') }}</a
          ><button
            @click="
              action(
                () =>
                  api('documents/' + selected.id, {
                    text: docText,
                    approved: docApproved,
                  }),
                tr('Document enregistré. La version précédente est conservée.'),
              )
            "
          >
            {{ tr('Enregistrer') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
