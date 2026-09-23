<script setup>
import { tr } from '../../../shared/i18n/index.js';
import { ref, onMounted, watch } from 'vue';
const props = defineProps({
  token: String,
});
const emit = defineEmits(['ready', 'changed']);
const provider = ref('openai'),
  key = ref(''),
  model = ref(''),
  models = ref([]),
  configs = ref({}),
  busy = ref(false),
  error = ref(''),
  notice = ref(''),
  verified = ref(false);
const providers = [
  ['deepseek', 'DeepSeek'],
  ['kimi', 'Kimi'],
  ['claude', 'Claude'],
  ['openai', 'OpenAI'],
];
const keyPages = {
  deepseek: 'https://platform.deepseek.com/api_keys',
  kimi: 'https://platform.kimi.ai/console/api-keys',
  claude: 'https://platform.claude.com/settings/keys',
  openai: 'https://platform.openai.com/api-keys',
};
async function load() {
  const r = await fetch('/api/ai');
  if (!r.ok) throw Error(tr('Configuration indisponible.'));
  configs.value = await r.json();
}
function select() {
  key.value = '';
  models.value = [];
  model.value = configs.value[provider.value]?.model || '';
  verified.value = !!configs.value[provider.value]?.configured;
  error.value = '';
  notice.value = '';
  emit('changed', provider.value);
  if (verified.value) emit('ready', provider.value);
}
onMounted(async () => {
  try {
    await load();
    select();
  } catch (e) {
    error.value = e.message;
  }
});
watch(provider, select);
watch(
  [key, model],
  () => {
    verified.value = false;
    notice.value = '';
    emit('changed', provider.value);
  },
  {
    flush: 'sync',
  },
);
async function post(path) {
  const r = await fetch('/api/ai/' + path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Workspace-Token': props.token,
    },
    body: JSON.stringify({
      provider: provider.value,
      key: key.value,
      model: model.value,
    }),
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(typeof data.detail === 'string' ? data.detail : tr('Paramètres invalides.'));
  return data;
}
async function perform(fn) {
  busy.value = true;
  error.value = '';
  notice.value = '';
  try {
    await fn();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function catalog() {
  await perform(async () => {
    models.value = (await post('models')).models;
    notice.value = models.value.length
      ? tr('Choisis un modèle, puis teste-le.')
      : tr('Aucun modèle proposé. Tu peux saisir son identifiant exact.');
  });
}
async function test() {
  await perform(async () => {
    await post('test');
    await load();
    key.value = '';
    await new Promise((resolve) => setTimeout(resolve, 0));
    verified.value = true;
    notice.value = tr('Connexion et appel d’outil validés. Configuration enregistrée.');
    emit('ready', provider.value);
  });
}
async function disconnect() {
  await perform(async () => {
    await post('disconnect');
    key.value = '';
    model.value = '';
    verified.value = false;
    await load();
    emit('changed', provider.value);
    notice.value = tr('Clé supprimée de cette installation.');
  });
}
</script>
<template>
  <div class="ai-setup">
    <label
      >{{ tr('Fournisseur IA')
      }}<select :aria-label="tr('Fournisseur IA')" v-model="provider" :disabled="busy">
        <option v-for="[id, label] in providers" :key="id" :value="id">
          {{ label }}
        </option>
      </select></label
    >
    <label
      >{{ tr('Clé API')
      }}<input
        type="password"
        v-model="key"
        :disabled="busy"
        autocomplete="new-password"
        :placeholder="
          configs[provider]?.configured
            ? tr('Clé enregistrée · laisser vide pour la conserver')
            : tr('Clé personnelle du fournisseur')
        "
    /></label>
    <p class="small">
      <a :href="keyPages[provider]" target="_blank" rel="noopener noreferrer"
        >{{
          tr('Créer ou retrouver ma clé {provider}', {
            provider: providers.find(([id]) => id === provider)?.[1],
          })
        }}
        ↗</a
      ><br />
      {{ tr('Connecte-toi au site officiel, puis crée une clé API et colle-la ici.') }}
    </p>
    <button
      type="button"
      class="secondary"
      :disabled="busy || (!key && !configs[provider]?.configured)"
      @click="catalog"
    >
      {{ tr('Charger les modèles') }}
    </button>
    <label v-if="models.length"
      >{{ tr('Modèles proposés')
      }}<select :aria-label="tr('Modèles proposés')" v-model="model" :disabled="busy">
        <option value="" disabled>{{ tr('Choisir un modèle') }}</option>
        <option v-for="id in models" :key="id" :value="id">{{ id }}</option>
      </select></label
    >
    <label
      >{{ tr('Identifiant du modèle')
      }}<input
        v-model="model"
        :disabled="busy"
        maxlength="160"
        :placeholder="tr('Identifiant du modèle fourni par le service')"
    /></label>
    <p class="small">
      {{
        tr(
          'Le test effectue un court appel IA pour vérifier la clé, le modèle et les outils. Cet appel peut être facturé par ton fournisseur. Les abonnements aux applications de chat ne remplacent pas une clé API.',
        )
      }}
    </p>
    <div class="setup-actions">
      <button
        type="button"
        :disabled="busy || !model || (!key && !configs[provider]?.configured)"
        @click="test"
      >
        {{ busy ? tr('Vérification…') : tr('Tester et enregistrer') }}</button
      ><button
        v-if="configs[provider]?.configured"
        type="button"
        class="secondary"
        :disabled="busy"
        @click="disconnect"
      >
        {{ tr('Oublier cette clé') }}
      </button>
    </div>
    <p v-if="error" role="alert">{{ tr(error) }}</p>
    <p v-if="notice" role="status">{{ tr(notice) }}</p>
    <p v-else-if="verified" role="status">
      {{ tr('Ce fournisseur a déjà été testé sur cette installation.') }}
    </p>
    <p class="small">
      {{
        tr(
          'Tes clés restent côté serveur, dans le volume privé de ton installation. Elles ne sont jamais renvoyées au navigateur.',
        )
      }}
    </p>
  </div>
</template>
<style scoped>
.ai-setup label {
  display: block;
  margin: 16px 0;
}
.setup-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.small {
  line-height: 1.6;
}
input,
select {
  width: 100%;
  box-sizing: border-box;
}
</style>
