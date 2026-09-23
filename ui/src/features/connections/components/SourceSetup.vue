<script setup>
import { tr } from '../../../shared/i18n/index.js';
import { ref, onMounted, computed, watch } from 'vue';
const props = defineProps({
  token: String,
  criteria: {
    type: Object,
    default: () => ({
      country: 'fr',
      source: 'bright',
      keywords: 'jobs',
      platforms: ['linkedin', 'indeed'],
    }),
  },
});
const emit = defineEmits(['ready']);
const configured = ref({}),
  resultCount = ref(0);
async function load() {
  const r = await fetch('/api/connections');
  if (r.ok) configured.value = await r.json();
}
onMounted(load);
async function test() {
  busy.value = true;
  notice.value = '';
  error.value = '';
  try {
    const r = await fetch('/api/connections/' + source.value + '/test', {
      method: 'POST',
      headers: {
        'X-Workspace-Token': props.token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...props.criteria, keywords: props.criteria.keywords || 'jobs' }),
    });
    const d = await r.json();
    if (!r.ok) throw Error(d.detail || tr('Test impossible.'));
    notice.value = 'Connexion vérifiée · {count} résultat(s) reçus, sans ajout aux pistes.';
    resultCount.value = d.results;
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
const source = ref('bright'),
  ftId = ref(''),
  ftSecret = ref(''),
  brightKey = ref(''),
  busy = ref(false),
  notice = ref(''),
  error = ref('');
async function save() {
  busy.value = true;
  error.value = '';
  notice.value = '';
  try {
    const body =
      source.value === 'france'
        ? {
            ft_client_id: ftId.value,
            ft_client_secret: ftSecret.value,
          }
        : {
            bright_key: brightKey.value,
          };
    const r = await fetch('/api/connections', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Workspace-Token': props.token,
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw Error(tr('Enregistrement impossible.'));
    ftId.value = '';
    ftSecret.value = '';
    brightKey.value = '';
    notice.value = tr('Identifiants enregistrés. Aucune recherche effectuée.');
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
const ready = computed(() =>
  props.criteria.source === 'both'
    ? Boolean(configured.value.france && configured.value.bright)
    : Boolean(configured.value[props.criteria.source]),
);
watch(ready, (value) => emit('ready', value), { immediate: true });
watch(
  () => props.criteria.country,
  (country) => {
    if (country !== 'fr') source.value = 'bright';
  },
);
watch(
  () => props.criteria.source,
  (value) => {
    source.value = value === 'france' ? 'france' : 'bright';
  },
  { immediate: true },
);
</script>
<template>
  <div class="source-setup">
    <p>
      {{
        tr(
          'Les sources sont indépendantes du fournisseur IA. Enregistre les accès des sources choisies. Tu pourras les modifier dans Connexions.',
        )
      }}
    </p>
    <label
      >Source<select aria-label="Source" v-model="source">
        <option v-if="criteria.country === 'fr'" value="france">France Travail</option>
        <option value="bright">{{ tr('Bright Data · LinkedIn, Indeed et web') }}</option>
      </select></label
    >
    <p class="small">
      {{
        configured[source]
          ? tr('Identifiants déjà enregistrés pour cette source.')
          : tr('Cette source n’est pas encore configurée.')
      }}
    </p>
    <div v-if="source === 'france'">
      <label
        >{{ tr('Client ID France Travail')
        }}<input type="password" autocomplete="new-password" v-model="ftId" /></label
      ><label
        >{{ tr('Client secret France Travail')
        }}<input type="password" autocomplete="new-password" v-model="ftSecret"
      /></label>
      <p class="small">
        {{ tr('Identifiants de l’API Offres d’emploi de France Travail.') }}
        <a href="https://francetravail.io/" target="_blank" rel="noopener noreferrer"
          >{{ tr('Obtenir mes accès France Travail') }} ↗</a
        >
      </p>
      <p class="small">
        {{
          tr(
            'Sur France Travail IO, connecte-toi, crée une application et demande l’accès à l’API Offres d’emploi pour obtenir le Client ID et le Client secret.',
          )
        }}
      </p>
    </div>
    <div v-else>
      <label
        >{{ tr('Clé Bright Data')
        }}<input type="password" autocomplete="new-password" v-model="brightKey"
      /></label>
      <p class="small">
        {{
          tr(
            'Clé API Bright Data distincte de ta clé IA. Active les scrapers LinkedIn Jobs et Indeed Jobs dans ton compte. Les annonces collectées peuvent être facturées par résultat ; le plafond local compte les appels, pas les euros.',
          )
        }}
      </p>
    </div>
    <p v-if="source === 'bright'" class="small">
      <a href="https://brightdata.com/cp/setting/users" target="_blank" rel="noopener noreferrer">{{
        tr('Obtenir ma clé Bright Data')
      }}</a>
    </p>
    <button
      type="button"
      :disabled="busy || (source === 'france' ? !ftId || !ftSecret : !brightKey)"
      @click="save"
    >
      {{ tr('Enregistrer cette source') }}
    </button>
    <p class="small">
      {{
        tr(
          'Le test recherche ton métier dans le pays choisi. Jusqu’à 20 annonces par plateforme ; Bright Data peut facturer ces résultats.',
        )
      }}
    </p>
    <button type="button" class="secondary" :disabled="busy || !configured[source]" @click="test">
      {{ tr('Tester cette connexion') }}
    </button>
    <p v-if="notice" role="status">{{ tr(notice, { count: resultCount }) }}</p>
    <p v-if="error" role="alert">{{ tr(error) }}</p>
  </div>
</template>
<style scoped>
label {
  display: block;
  margin: 16px 0;
}
input,
select {
  width: 100%;
  box-sizing: border-box;
}
p {
  line-height: 1.6;
}
</style>
