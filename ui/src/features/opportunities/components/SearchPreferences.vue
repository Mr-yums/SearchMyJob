<script setup>
import { watch } from 'vue';
import { tr } from '../../../shared/i18n/index.js';
import CountrySelect from '../../../shared/components/CountrySelect.vue';
const props = defineProps({ criteria: { type: Object, required: true } });
watch(
  () => props.criteria.country,
  (country) => {
    if (country !== 'fr') props.criteria.source = 'bright';
  },
);
</script>
<template>
  <div class="search-preferences">
    <CountrySelect v-model="criteria.country" />
    <label
      >{{ tr('Ville ou région (facultatif)') }}<input v-model="criteria.location" maxlength="100"
    /></label>
    <label
      >{{ tr('Métier / mots-clés')
      }}<input
        v-model="criteria.keywords"
        maxlength="150"
        :placeholder="tr('Ex. infirmier, comptable, cuisinier, développeur…')"
    /></label>
    <label
      >{{ tr('Objectif')
      }}<select v-model="criteria.objectif">
        <option value="emploi">{{ tr('Trouver un emploi ou une mission') }}</option>
        <option value="prospection">{{ tr('Trouver des clients') }}</option>
      </select></label
    >
    <label
      >{{ tr('Sources utilisées pour chercher')
      }}<select :aria-label="tr('Sources utilisées pour chercher')" v-model="criteria.source">
        <option value="bright">Bright Data · LinkedIn / Indeed / Web</option>
        <option v-if="criteria.country === 'fr'" value="france">France Travail</option>
        <option v-if="criteria.country === 'fr'" value="both">{{ tr('Les deux sources') }}</option>
      </select></label
    >
    <fieldset v-if="criteria.source !== 'france' && criteria.objectif !== 'prospection'">
      <legend>{{ tr('Sites à explorer avec Bright Data') }}</legend>
      <label
        v-for="platform in [
          ['linkedin', 'LinkedIn'],
          ['indeed', 'Indeed'],
          ['direct', 'Autres sites d’annonces'],
          ['freelance', 'Upwork / Freelancer'],
        ]"
        :key="platform[0]"
        class="check"
      >
        <input type="checkbox" v-model="criteria.platforms" :value="platform[0]" />{{
          tr(platform[1])
        }}
      </label>
    </fieldset>
    <p>
      {{
        tr(
          'LinkedIn et Indeed : annonces publiques collectées via Bright Data, sans connexion à ton compte. La couverture dépend du pays et de la plateforme.',
        )
      }}
    </p>
    <label class="check"
      ><input type="checkbox" v-model="criteria.freelance" />{{
        tr('Missions freelance uniquement')
      }}</label
    >
    <label class="check"
      ><input type="checkbox" v-model="criteria.remote" />{{ tr('Télétravail souhaité') }}</label
    >
    <label
      >{{ tr('Langue de l’aide et des documents')
      }}<select
        :aria-label="tr('Langue de l’aide et des documents')"
        v-model="criteria.response_language"
      >
        <option value="fr">Français</option>
        <option value="en">English</option>
      </select></label
    >
  </div>
</template>
<style scoped>
label {
  display: block;
  margin: 14px 0;
}
input,
select {
  width: 100%;
  box-sizing: border-box;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
}
.check input {
  width: auto;
}
fieldset {
  margin: 16px 0;
  border: 1px solid var(--line, #ddd);
  border-radius: 8px;
}
p {
  font-size: 12px;
  line-height: 1.6;
}
</style>
