<script setup>
import { toRefs } from 'vue';
import { tr, intlLocale } from '../../shared/i18n/index.js';

import AppIcon from '../../shared/components/AppIcon.vue';
import ProfileReader from './components/ProfileReader.vue';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const {
  state,
  profile,
  draft,
  loading,
  editingProfile,
  profileDirty,
  profileTitle,
  brief,
  saveProfile,
  importCV,
} = toRefs(props.model);
</script>
<template>
  <section class="profile-view">
    <div class="page-heading compact">
      <div>
        <h1>{{ tr('Mon profil') }}</h1>
        <p>{{ tr('Informations utilisées par tes agents.') }}</p>
      </div>
      <button class="secondary" @click="editingProfile = !editingProfile">
        <AppIcon :name="editingProfile ? 'profile' : 'edit'" :size="17" />{{
          editingProfile ? tr('Voir le profil') : tr('Modifier mon profil')
        }}
      </button>
    </div>
    <div class="profile-banner">
      <span class="profile-avatar">T<span></span></span>
      <div>
        <span class="eyebrow">{{ tr('PROFIL PROFESSIONNEL') }}</span>
        <h2>{{ profileTitle }}</h2>
        <div class="tags">
          <span v-for="line in brief" :key="line">{{ tr(line) }}</span>
        </div>
      </div>
      <span class="profile-state"
        ><AppIcon name="check" :size="16" />{{
          state.profile ? tr('Enregistré') : tr('À compléter')
        }}</span
      >
    </div>
    <div v-if="profileDirty" class="draft-banner">
      <AppIcon name="edit" :size="17" /><span>{{
        tr('Un brouillon différent du profil enregistré est conservé.')
      }}</span
      ><button class="text-button" @click="editingProfile = true">
        {{ tr('Reprendre le brouillon') }}
      </button>
    </div>
    <ProfileReader v-if="!editingProfile && state.profile" :text="state.profile" />
    <div v-if="editingProfile || !state.profile" class="card profile-edit">
      <div class="editor-heading">
        <h3>{{ tr('Modifier le profil') }}</h3>
        <span class="small"
          >{{ profile.length.toLocaleString(intlLocale) }}{{ tr(' caractères · ')
          }}{{ profileDirty ? tr('brouillon non enregistré') : tr('à jour') }}</span
        >
      </div>
      <label class="upload"
        >{{ tr('Importer un CV · PDF texte, DOCX, TXT')
        }}<input type="file" accept=".pdf,.docx,.txt,.md" @change="importCV" /></label
      ><label
        >{{ tr('Profil professionnel')
        }}<textarea
          class="profile-editor"
          v-model="profile"
          :placeholder="tr('Mon expérience, mes compétences, mes projets, mes résultats…')"
        ></textarea>
      </label>
      <div class="form-actions">
        <button class="secondary" @click="profile = state.profile">
          {{ tr('Recharger le profil enregistré') }}</button
        ><button :disabled="loading" @click="saveProfile">
          {{ tr('Enregistrer mon profil') }}
        </button>
      </div>
      <p class="small">
        {{ tr('Tes modifications restent un brouillon jusqu’à l’enregistrement.') }}
      </p>
    </div>
  </section>
</template>
