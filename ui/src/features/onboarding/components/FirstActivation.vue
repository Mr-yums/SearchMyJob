<script setup>
import { tr, locale } from '../../../shared/i18n/index.js';
import LanguageSwitcher from '../../../shared/components/LanguageSwitcher.vue';
import { ref } from 'vue';
import AISetup from '../../connections/components/AISetup.vue';
import SourceSetup from '../../connections/components/SourceSetup.vue';
import SearchPreferences from '../../opportunities/components/SearchPreferences.vue';
const props = defineProps({
  token: {
    type: String,
    required: true,
  },
});
const emit = defineEmits(['activated']);
const step = ref(1),
  saving = ref(false),
  error = ref(''),
  ready = ref(false),
  sourcesReady = ref(false);
const form = ref({
  provider: 'openai',
  profile: '',
  keywords: '',
  country: '',
  location: '',
  objectif: 'emploi',
  source: 'bright',
  platforms: ['linkedin', 'indeed'],
  response_language: locale.value,
  freelance: false,
  remote: false,
  free_applications: true,
});
async function activate() {
  saving.value = true;
  error.value = '';
  try {
    const r = await fetch('/api/activation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Workspace-Token': props.token,
      },
      body: JSON.stringify(form.value),
    });
    const data = await r.json();
    if (!r.ok)
      throw Error(typeof data.detail === 'string' ? data.detail : tr('Activation impossible.'));
    emit('activated', form.value.provider);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
</script>
<template>
  <section class="activation">
    <div class="activation-card">
      <div class="activation-language"><LanguageSwitcher /></div>
      <p class="eyebrow">{{ tr('BIENVENUE DANS SEARCHMYJOB · ') }}{{ step }} / 3</p>
      <h1>
        {{
          step === 1
            ? tr('Connecte ton assistant IA')
            : step === 2
              ? tr('Choisis tes sources de recherche')
              : tr('Présente ton parcours')
        }}
      </h1>
      <p class="activation-intro">
        {{
          tr(
            'Ton espace personnel, installé chez toi. Tes choix restent modifiables dans Connexions.',
          )
        }}
      </p>
      <AISetup
        v-show="step === 1"
        :token="token"
        @changed="ready = false"
        @ready="
          (p) => {
            form.provider = p;
            ready = true;
          }
        "
      />
      <div v-if="step === 2">
        <SearchPreferences :criteria="form" />
        <SourceSetup :token="token" :criteria="form" @ready="sourcesReady = $event" />
        <p v-if="!sourcesReady" class="small">
          {{ tr('Enregistre la clé des sources choisies avant de continuer.') }}
        </p>
      </div>
      <div v-if="step === 3">
        <label
          >{{ tr('Ton parcours et tes compétences')
          }}<textarea
            v-model="form.profile"
            maxlength="60000"
            rows="6"
            :placeholder="tr('Ton métier, tes projets, tes compétences…')"
          ></textarea></label
        ><label
          >{{ tr('Métier ou type de mission')
          }}<input
            v-model="form.keywords"
            maxlength="150"
            :placeholder="tr('Ex. infirmier, comptable, cuisinier, développeur…')" /></label
        ><label class="activation-check"
          ><input type="checkbox" v-model="form.freelance" />{{ tr('Missions freelance') }}</label
        ><label class="activation-check"
          ><input type="checkbox" v-model="form.remote" />{{ tr('Travail à distance') }}</label
        ><label class="activation-check"
          ><input type="checkbox" v-model="form.free_applications" />{{
            tr('Exclure les paiements obligatoires pour candidater')
          }}</label
        >
        <p class="small">
          {{
            tr(
              'Tu peux compléter ton profil plus tard. L’activation ne lance aucune recherche ; la veille est désactivée au départ.',
            )
          }}
        </p>
      </div>
      <p v-if="error" role="alert">{{ tr(error) }}</p>
      <div class="activation-actions">
        <button v-if="step > 1" type="button" class="secondary" :disabled="saving" @click="step--">
          {{ tr('Retour') }}</button
        ><button
          type="button"
          :disabled="
            saving ||
            !ready ||
            (step === 2 &&
              (!form.country || !form.keywords.trim() || !sourcesReady || !form.platforms.length))
          "
          @click="step < 3 ? step++ : activate()"
        >
          {{
            saving ? tr('Enregistrement…') : step === 3 ? tr('Activer mon espace') : tr('Continuer')
          }}
        </button>
      </div>
    </div>
  </section>
</template>
<style scoped>
.activation-language {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
.activation {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--bg, #f5f3f8);
}
.activation-card {
  width: min(100%, 650px);
  background: var(--surface, #fff);
  color: var(--text, #292335);
  padding: clamp(20px, 5vw, 42px);
  border: 1px solid var(--border, #e5dfee);
  border-radius: 22px;
  box-shadow: 0 16px 50px #2413420a;
  box-sizing: border-box;
}
h1 {
  font-size: clamp(24px, 4vw, 34px);
  line-height: 1.2;
  margin: 14px 0;
}
.activation-intro {
  margin-bottom: 24px;
  line-height: 1.6;
}
fieldset {
  border: 0;
  padding: 0;
  min-width: 0;
}
legend {
  margin-bottom: 14px;
  font-weight: 600;
}
.assistant-choice {
  display: flex;
  align-items: center;
  gap: 14px;
  border: 1px solid var(--border, #ddd);
  border-radius: 12px;
  padding: 16px;
  margin: 10px 0;
  cursor: pointer;
}
.assistant-choice.chosen {
  border-color: var(--accent, #7052c4);
  box-shadow: 0 0 0 1px var(--accent, #7052c4);
}
.assistant-choice input,
.activation-check input {
  width: auto;
  margin: 0;
  flex-shrink: 0;
}
.assistant-choice small {
  display: block;
  margin-top: 5px;
  font-size: 13px;
  line-height: 1.5;
}
textarea,
input {
  box-sizing: border-box;
  max-width: 100%;
}
textarea {
  width: 100%;
  resize: vertical;
}
.activation-check {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 18px 0;
}
.activation-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}
.small {
  line-height: 1.6;
  margin-top: 16px;
}
</style>
