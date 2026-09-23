<script setup>
import SearchPreferences from './components/SearchPreferences.vue';
import { toRefs } from 'vue';
import { tr } from '../../shared/i18n/index.js';

import AppIcon from '../../shared/components/AppIcon.vue';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const {
  state,
  criteria,
  loading,
  filter,
  resultType,
  query,
  offerDetail,
  showSearch,
  quickPrompts,
  preparePrompt,
  busy,
  offers,
  counts,
  date,
  api,
  action,
  search,
  generate,
  mail,
} = toRefs(props.model);
</script>
<template>
  <section class="offers-view">
    <div class="page-heading compact">
      <div>
        <h1>{{ tr('Opportunités') }}</h1>
        <a class="small" href="/api/export/offers.csv">{{ tr('Exporter les fiches en CSV ↓') }}</a>
        <p>
          {{ state.offers.length }}{{ tr(' pistes · ') }}{{ counts.saved }}{{ tr(' retenues') }}
        </p>
      </div>
      <button @click="preparePrompt(tr(quickPrompts[0].text))">
        <AppIcon name="spark" :size="17" />{{ tr('Demander une recherche') }}
      </button>
    </div>
    <div class="offer-summary">
      <button :class="{ chosen: filter === 'all' }" @click="filter = 'all'">
        {{ tr('Toutes ') }}<b>{{ state.offers.length }}</b></button
      ><button :class="{ chosen: filter === 'new' }" @click="filter = 'new'">
        {{ tr('À découvrir ') }}<b>{{ counts.new }}</b></button
      ><button :class="{ chosen: filter === 'saved' }" @click="filter = 'saved'">
        {{ tr('Retenues ') }}<b>{{ counts.saved }}</b></button
      ><button class="filter-toggle" :aria-expanded="showSearch" @click="showSearch = !showSearch">
        <AppIcon name="sliders" :size="16" />{{ tr('Critères avancés') }}
      </button>
    </div>
    <form v-if="showSearch" class="card criteria" @submit.prevent="search()">
      <div class="mode-switch full" role="group" :aria-label="tr('Objectif')">
        <button
          type="button"
          :aria-pressed="(criteria.objectif || 'emploi') === 'emploi'"
          @click="criteria.objectif = 'emploi'"
        >
          <AppIcon name="offers" :size="15" />{{ tr('Trouver un emploi') }}</button
        ><button
          type="button"
          :aria-pressed="criteria.objectif === 'prospection'"
          @click="criteria.objectif = 'prospection'"
        >
          <AppIcon name="spark" :size="15" />{{ tr('Trouver des clients') }}
        </button>
      </div>
      <p class="small full" v-if="criteria.objectif === 'prospection'">
        {{
          tr(
            'Mode prospection : l’IA cherche des entreprises à démarcher (pas des offres d’emploi), repère un besoin et un contact public, et prépare un e-mail d’approche à relire dans Courrier.',
          )
        }}
      </p>
      <div class="full"><SearchPreferences :criteria="criteria" /></div>
      <label class="full"
        >{{ tr('Autres métiers à rechercher (un par ligne, 4 maximum)') }}
        <textarea
          :value="(criteria.axes || []).join('\n')"
          @input="
            criteria.axes = $event.target.value
              .split('\n')
              .map((s) => s.trim())
              .filter(Boolean)
              .slice(0, 4)
          "
          rows="3"
        />
      </label>
      <label
        >{{ tr('Exclure (séparés par virgules)')
        }}<input v-model="criteria.exclude" maxlength="400"
      /></label>
      <label v-if="criteria.source !== 'bright'"
        >{{ tr('Département (France Travail)')
        }}<input v-model="criteria.department" placeholder="69 ou 75,92"
      /></label>
      <label v-if="criteria.source !== 'bright'"
        >{{ tr('Contrat France Travail')
        }}<select :aria-label="tr('Contrat France Travail')" v-model="criteria.contract">
          <option value="">{{ tr('Tous') }}</option>
          <option value="CDI">CDI</option>
          <option value="CDD">CDD</option>
          <option value="MIS">{{ tr('Intérim') }}</option>
          <option value="LIB">{{ tr('Profession libérale') }}</option>
        </select></label
      >
      <label v-if="criteria.freelance"
        >{{ tr('TJM souhaité minimum (€)')
        }}<input type="number" min="0" max="5000" v-model.number="criteria.min_tjm"
      /></label>
      <div class="form-actions">
        <button
          type="button"
          class="secondary"
          @click="action(() => api('criteria', criteria), tr('Critères enregistrés.'))"
        >
          {{ tr('Enregistrer') }}</button
        ><button type="button" class="secondary" :disabled="busy || loading" @click="search(true)">
          {{ tr('Actualiser les sources') }}</button
        ><button :disabled="busy || loading">{{ tr('Rechercher ↗') }}</button>
      </div>
      <p class="small full">
        {{
          tr(
            'Chaque métier déclenche une collecte par plateforme choisie : 20 annonces maximum pour LinkedIn ou Indeed, 30 résultats pour le web. Maximum 4 métiers. Les conditions non publiées restent à vérifier.',
          )
        }}
      </p>
    </form>
    <div class="list-toolbar">
      <input
        :aria-label="tr('Filtrer les résultats')"
        v-model="query"
        :placeholder="tr('Filtrer titre, entreprise ou lieu')"
      /><select :aria-label="tr('Type de résultat')" v-model="resultType">
        <option value="all">{{ tr('Tous les types de pistes') }}</option>
        <option value="individual">
          {{ tr('Annonces individuelles probables') }}
        </option>
        <option value="listing">
          {{ tr('Pages de recherche / annuaires') }}
        </option>
        <option value="web_lead">
          {{ tr('Pistes non identifiées') }}
        </option></select
      ><select :aria-label="tr('Statut des offres')" v-model="filter">
        <option value="all">{{ tr('Toutes les pistes') }}</option>
        <option value="new">{{ tr('À découvrir') }}</option>
        <option value="saved">{{ tr('Retenues') }}</option>
        <option value="dismissed">{{ tr('Écartées') }}</option>
        <option value="ready">{{ tr('Prêtes') }}</option></select
      ><span class="small">{{ offers.length }}{{ tr(' résultats') }}</span>
    </div>
    <div v-if="!offers.length" class="empty card opportunity-empty">
      <span class="empty-icon"><AppIcon name="offers" :size="32" /></span>
      <h2>
        {{
          state.offers.length
            ? tr('Aucune piste dans cette sélection.')
            : tr('Aucune opportunité pour le moment.')
        }}
      </h2>
      <p>
        {{
          state.offers.length
            ? tr('Essaie un autre filtre ou d’autres mots-clés.')
            : tr(
                'Décris ce que tu cherches dans la conversation. Les résultats apparaîtront ici, avec leurs sources.',
              )
        }}
      </p>
      <button @click="preparePrompt(tr(quickPrompts[0].text))">
        {{ tr('Préparer une recherche ') }}<AppIcon name="arrow" :size="16" />
      </button>
    </div>
    <div class="offer-grid">
      <article v-for="o in offers" :key="o.id" class="card offer">
        <div class="offer-top">
          <span class="tag">{{ o.source }}</span
          ><span class="small">{{ o.contract || tr('Contrat non précisé') }}</span>
        </div>
        <h2>
          <button class="offer-title" @click="offerDetail = o">
            {{ o.title }}
          </button>
        </h2>
        <p>
          {{ o.company || tr('Entreprise non précisée') }} ·
          {{ o.location || tr('Lieu à vérifier') }}
        </p>
        <p v-if="o.salary" class="salary">{{ o.salary }}</p>
        <div class="tags">
          <span v-for="check in o.checks" class="warning">{{ tr(check) }}</span>
        </div>
        <details>
          <summary>{{ tr('Description & source') }}</summary>
          <p v-if="o.search_axes?.length" class="small">
            {{ tr('Axes : ') }}{{ o.search_axes.join(', ') }}
          </p>
          <p
            v-for="(condition, key) in o.conditions"
            :key="key"
            v-show="condition.evidence"
            class="small"
          >
            {{
              {
                freelance: 'Freelance',
                remote: tr('Distance'),
                travel: tr('Déplacements'),
                language: tr('Langue'),
                availability: tr('Disponibilité'),
              }[key]
            }}{{ tr(' — extrait : « ') }}{{ condition.evidence }}{{ tr(' » · page non vérifiée') }}
          </p>
          <p class="pre">
            {{ o.description || tr('Consulte la source pour le détail de cette piste.') }}
          </p>
          <a v-if="o.url" :href="o.url" target="_blank" rel="noopener noreferrer">{{
            tr('Voir l’offre originale ↗')
          }}</a>
          <p class="small">
            {{ tr('Découverte le ') }}{{ date(o.found) }}{{ tr(' · Dernière collecte ')
            }}{{ date(o.updated) }}
          </p>
        </details>
        <div class="offer-actions">
          <button
            class="secondary"
            @click="
              action(() =>
                api('offers/' + o.id, {
                  status: o.status === 'saved' ? 'new' : 'saved',
                }),
              )
            "
          >
            {{ o.status === 'saved' ? tr('✓ Retenue') : tr('Retenir') }}</button
          ><button
            class="subtle"
            @click="action(() => api('offers/' + o.id, { status: 'dismissed' }))"
          >
            {{ tr('Écarter') }}</button
          ><button :disabled="busy" @click="generate(o, 'cv')">CV</button
          ><button :disabled="busy" @click="generate(o, 'letter')">
            {{ tr('Lettre') }}</button
          ><button :disabled="busy" @click="generate(o, 'email')">E-mail</button>
        </div>
      </article>
    </div>
  </section>
</template>
