<script setup>
import { tr, intlLocale } from '../../../shared/i18n/index.js';
import { ref, onMounted, onUnmounted } from 'vue';
const props = defineProps({
  offer: Object,
  token: String,
  busy: Boolean,
});
const dossier = ref(null),
  error = ref(''),
  collecting = ref(false),
  source = ref(null);
let timer;
const date = (t) => new Date(t * 1000).toLocaleString(intlLocale.value);
async function read() {
  try {
    const r = await fetch('/api/offers/' + props.offer.id + '/dossier');
    if (!r.ok) throw Error(tr('Fiche indisponible'));
    dossier.value = await r.json();
  } catch (e) {
    error.value = e.message;
  }
}
async function collect(force = false) {
  error.value = '';
  collecting.value = true;
  try {
    const r = await fetch('/api/offers/' + props.offer.id + '/collect?force=' + force, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Workspace-Token': props.token,
      },
      body: '{}',
    });
    const data = await r.json();
    if (!r.ok) throw Error(data.detail || tr('Collecte impossible'));
    if (data.cached) {
      await read();
      collecting.value = false;
      return;
    }
    timer = setInterval(async () => {
      try {
        const r = await fetch('/api/state');
        if (!r.ok) return;
        const state = await r.json();
        const run = state.runs.find((r) => r.id === data.run_id);
        if (run && run.status !== 'running') {
          clearInterval(timer);
          collecting.value = false;
          if (run.status !== 'completed') error.value = run.error || tr('Collecte interrompue');
          await read();
        }
      } catch {
        error.value = tr('Connexion interrompue ; réouvre la fiche pour vérifier la collecte.');
        clearInterval(timer);
        collecting.value = false;
      }
    }, 2500);
  } catch (e) {
    error.value = e.message;
    collecting.value = false;
  }
}
async function openSource(id) {
  try {
    const r = await fetch('/api/sources/' + id);
    if (!r.ok) throw Error(tr('Source indisponible'));
    source.value = await r.json();
  } catch (e) {
    error.value = e.message;
  }
}
onMounted(read);
onUnmounted(() => clearInterval(timer));
</script>
<template>
  <div class="offer-dossier">
    <h3>{{ tr('Fiche conservée') }}</h3>
    <p>
      {{ tr('Sources, contenu et documents restent disponibles dans ta base locale.') }}
    </p>
    <p v-if="error" role="alert">{{ tr(error) }}</p>
    <template v-if="dossier">
      <div v-if="!dossier.page" class="dossier-note">
        <strong>{{ tr('Page complète non collectée') }}</strong>
        <p>
          {{
            tr(
              'Cette fiche contient pour l’instant l’extrait de recherche. La lecture de la page utilise Bright Data.',
            )
          }}
        </p>
        <button class="secondary" :disabled="busy || collecting" @click="collect()">
          {{ collecting ? tr('Collecte en cours…') : tr('Lire et conserver la page') }}
        </button>
      </div>
      <div v-else>
        <p>
          {{ tr('Page collectée le ') }}{{ date(dossier.page.created) }} ·
          {{ dossier.page.content.length.toLocaleString(intlLocale)
          }}{{ tr(' caractères conservés.') }}
        </p>
        <p class="dossier-note">
          <strong>{{
            {
              platform: tr('Candidature via la plateforme'),
              contact_found: tr('Coordonnées repérées · à vérifier'),
              contact_not_found: tr('Coordonnées introuvables dans le contenu reçu'),
            }[dossier.page.application_mode]
          }}</strong
          ><br />{{
            tr(
              'La collecte ne garantit pas que l’annonce soit complète, accessible sans compte ou encore ouverte.',
            )
          }}
        </p>
        <article
          v-for="contact in dossier.page.contacts"
          :key="contact.email"
          class="dossier-contact"
        >
          <strong>{{ contact.email }}</strong
          ><span>{{
            tr('Adresse présente dans la page · destinataire professionnel à vérifier')
          }}</span>
          <blockquote>{{ contact.evidence }}</blockquote>
          <a :href="contact.source_url" target="_blank" rel="noopener">{{
            tr('Source de l’adresse ↗')
          }}</a>
        </article>
        <details>
          <summary>{{ tr('Lire le contenu enregistré') }}</summary>
          <p class="pre">{{ dossier.page.content }}</p>
        </details>
        <button class="subtle" :disabled="busy || collecting" @click="collect(true)">
          {{ collecting ? tr('Actualisation…') : tr('Actualiser la page avec Bright Data') }}
        </button>
      </div>
      <h4>{{ tr('Sources conservées · ') }}{{ dossier.sources.length }}</h4>
      <button
        v-for="s in dossier.sources"
        :key="s.id"
        class="source-row secondary"
        @click="openSource(s.id)"
      >
        {{ s.kind === 'page' ? tr('Page collectée') : tr('Résultat de recherche') }}
        · {{ s.source }}<small>{{ date(s.created) }}</small>
      </button>
      <details v-if="source" open>
        <summary>{{ tr('Contenu de la source sélectionnée') }}</summary>
        <p class="pre">{{ source.content }}</p>
      </details>
      <h4>{{ tr('CV et lettres associés · ') }}{{ dossier.documents.length }}</h4>
      <p v-if="!dossier.documents.length">
        {{ tr('Aucun document généré pour cette offre.') }}
      </p>
      <a
        v-for="d in dossier.documents"
        :key="d.id"
        class="source-row"
        :href="'/api/documents/' + d.id + '/download?format=docx'"
        >{{ d.kind === 'cv' ? 'CV' : tr('Lettre') }} · {{ date(d.created) }} ↓</a
      >
    </template>
  </div>
</template>
<style scoped>
.offer-dossier {
  border-top: 1px solid var(--line);
  margin-top: 24px;
  padding-top: 22px;
}
.offer-dossier h3 {
  font-size: 16px;
}
.offer-dossier h4 {
  font-size: 12px;
  margin: 24px 0 12px;
}
.offer-dossier p,
.offer-dossier span {
  font-size: 12px;
  line-height: 1.7;
  color: var(--muted);
}
.dossier-note {
  background: var(--surface-2);
  border: 1px solid var(--line);
  padding: 15px;
  border-radius: 10px;
}
.dossier-contact {
  padding: 15px 0;
  border-bottom: 1px solid var(--line);
  overflow-wrap: anywhere;
}
.dossier-contact strong,
.dossier-contact span {
  display: block;
}
.dossier-contact blockquote {
  margin: 10px 0;
  font-size: 11px;
  white-space: pre-wrap;
}
.source-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  width: 100%;
  margin: 8px 0;
  padding: 10px;
  font-size: 11px;
}
.source-row small {
  font-size: 10px;
}
.offer-dossier details {
  margin: 16px 0;
  font-size: 12px;
}
.offer-dossier .pre {
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.offer-dossier button {
  font-size: 11px;
}
</style>
