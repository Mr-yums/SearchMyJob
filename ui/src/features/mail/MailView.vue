<script setup>
import RecordList from '../../shared/components/RecordList.vue';
import { computed, nextTick, ref, toRefs } from 'vue';
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
  error,
  selected,
  credentials,
  navigate,
  busy,
  offers,
  date,
  api,
  action,
  send,
  mailForm,
  mailSelected,
  mailConfirm,
  senderName,
  emails,
  mail,
  openEmail,
  connectMail,
  saveEmail,
  sendEmail,
  discardEmail,
  newEmail,
} = toRefs(props.model);
const expanded = ref(false);
const readerView = ref(null);
async function toggleView(value = !expanded.value) {
  expanded.value = value;
  await nextTick();
  readerView.value?.closest('.pane-content')?.scrollTo({ top: 0, behavior: 'instant' });
}
const isExpanded = computed(() => expanded.value && !!mailSelected.value);
const listItems = computed(() =>
  emails.value.map((email) => ({
    id: email.id,
    title: email.subject || tr('Sans objet'),
    meta: `${email.status === 'sent' ? tr('Envoyé') : tr('Brouillon')} · ${email.to || tr('Destinataire à indiquer')}`,
    search: props.model.state.offers.find((offer) => offer.id === email.offer_id)?.title,
    category: email.status === 'sent' ? 'sent' : 'draft',
  })),
);
const listFilters = computed(() => [
  { value: 'draft', label: tr('Brouillons') },
  { value: 'sent', label: tr('Envoyés') },
]);
function selectRecord(id) {
  openEmail.value(emails.value.find((email) => email.id === id));
}
</script>
<template>
  <section ref="readerView" class="mail-view" :class="{ 'reader-expanded': isExpanded }">
    <div class="page-heading compact">
      <div>
        <h1>{{ tr('Courrier') }}</h1>
        <p>
          {{ tr('L’agent prépare, tu relis et tu valides, ça part de ta boîte.') }}
        </p>
      </div>
      <button class="secondary" :disabled="busy" @click="newEmail">
        <AppIcon name="edit" :size="16" /><span>{{ tr('Nouveau brouillon') }}</span>
      </button>
    </div>
    <div class="card mail-connection" v-show="!isExpanded" v-if="!mail.connected">
      <div class="budget-heading">
        <span class="eyebrow">{{ tr('GMAIL · CONNEXION') }}</span
        ><AppIcon name="mail" />
      </div>
      <h3>{{ tr('Connecter ta boîte Gmail') }}</h3>
      <p class="small">
        {{
          tr('Envoi seulement : SearchMyJob ne lit jamais ta boîte. Une mise en place unique sur ')
        }}<a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener"
          >console.cloud.google.com</a
        >.
      </p>
      <ol class="steps">
        <li>{{ tr('Crée un projet, ou choisis-en un.') }}</li>
        <li>
          {{ tr('Active l’') }}<strong>{{ tr('API Gmail') }}</strong
          >{{ tr(' dans la bibliothèque d’API.') }}
        </li>
        <li>
          {{ tr('Écran de consentement OAuth : type ') }}<strong>{{ tr('Externe') }}</strong
          >{{ tr(', ajoute le scope ') }}<code>gmail.send</code>{{ tr(', puis ')
          }}<strong>{{ tr('publie « En production »') }}</strong
          >{{ tr(' pour une connexion permanente (sinon elle expire après 7 jours).') }}
        </li>
        <li>
          {{ tr('Identifiants → ID client OAuth → type ')
          }}<strong>{{ tr('Application de bureau') }}</strong
          >.
        </li>
        <li>{{ tr('Télécharge le JSON et dépose-le ici.') }}</li>
      </ol>
      <div v-if="mail.pending" class="alert" role="status">
        <span>{{ tr('Autorisation en attente dans ton navigateur…') }}</span>
        <a class="button secondary" :href="mail.auth_url" target="_blank" rel="noopener">{{
          tr('Rouvrir la page Google')
        }}</a>
      </div>
      <p v-if="mail.error" class="small warning-text" role="alert">
        {{ tr(mail.error) }}
      </p>
      <label class="upload"
        ><input
          type="file"
          accept=".json,application/json"
          :aria-label="tr('Déposer le JSON Google')"
          @change="connectMail"
        /><span>{{ tr('Déposer le JSON Google et connecter') }}</span></label
      >
    </div>
    <details class="card mail-connection" v-show="!isExpanded" v-else>
      <summary>{{ mail.address }} · {{ tr('Réglages Gmail') }}</summary>
      <div class="budget-heading">
        <span class="eyebrow">{{ tr('GMAIL · CONNECTÉ') }}</span
        ><AppIcon name="mail" />
      </div>
      <h3>{{ mail.address }}</h3>
      <p class="small">
        {{ tr('Les e-mails partent de cette adresse, en ton nom. Rien ne part sans ton clic.') }}
      </p>
      <div class="mail-prefs">
        <label
          >{{ tr('Nom affiché en expéditeur')
          }}<input
            v-model="senderName"
            :placeholder="tr('Prénom Nom')"
            @change="
              action(() => api('mail/prefs', { sender_name: senderName }), tr('Nom enregistré.'))
            "
        /></label>
      </div>
      <div class="form-actions">
        <button
          class="secondary"
          :disabled="busy"
          @click="action(() => api('mail/test'), tr('E-mail de test envoyé à ta propre adresse.'))"
        >
          {{ tr('M’envoyer un test') }}</button
        ><button
          class="subtle"
          @click="action(() => api('mail/disconnect'), tr('Boîte déconnectée.'))"
        >
          {{ tr('Déconnecter') }}
        </button>
      </div>
    </details>
    <div v-if="!emails.length" class="empty card">
      <h2>{{ tr('Aucun brouillon') }}</h2>
      <p>
        {{
          tr(
            'Sur une opportunité, clique « E-mail » : l’agent rédige, tu complètes le destinataire, tu relis, tu envoies.',
          )
        }}
      </p>
      <button @click="navigate('offers')">
        {{ tr('Voir les opportunités →') }}
      </button>
    </div>
    <div v-else class="documents-layout">
      <div v-show="!isExpanded" class="mail-list">
        <RecordList
          :items="listItems"
          :selected-id="mailSelected?.id"
          :filters="listFilters"
          @select="selectRecord"
        />
      </div>
      <div v-if="mailSelected" class="card mail-reader">
        <div class="reader-heading">
          <h2>
            {{ mailSelected.status === 'sent' ? tr('E-mail envoyé') : tr('Ton e-mail') }}
          </h2>
          <button
            type="button"
            class="secondary mail-view-toggle"
            :aria-pressed="isExpanded"
            @click="toggleView()"
          >
            {{ isExpanded ? tr('Vue classique') : tr('Vue complète') }}
          </button>
        </div>
        <div class="mail-fields">
          <label
            >{{ tr('Destinataire')
            }}<input
              v-model="mailForm.to"
              type="email"
              :placeholder="tr('recruteur@entreprise.com')"
              :disabled="mailSelected.status === 'sent'" /></label
          ><label
            >{{ tr('Objet')
            }}<input v-model="mailForm.subject" :disabled="mailSelected.status === 'sent'"
          /></label>
        </div>
        <textarea
          class="document-editor mail-editor"
          :aria-label="tr('Corps de l’e-mail')"
          v-model="mailForm.body"
          :disabled="mailSelected.status === 'sent'"
        ></textarea>
        <p v-if="mailSelected.error" class="small warning-text" role="alert">
          {{ tr(mailSelected.error) }}
        </p>
        <template v-if="mailSelected.status !== 'sent'"
          ><label class="check"
            ><input type="checkbox" v-model="mailConfirm" />{{
              tr(' J’ai relu et validé cet e-mail, il part de ')
            }}{{ mail.address || tr('ma boîte') }}</label
          >
          <div class="form-actions">
            <button class="subtle" @click="discardEmail">
              {{ tr('Écarter') }}</button
            ><button class="secondary" :disabled="busy" @click="saveEmail">
              {{ tr('Enregistrer') }}</button
            ><button :disabled="busy || !mailConfirm || !mail.connected" @click="sendEmail">
              <AppIcon name="send" :size="16" /><span>{{ tr('Envoyer') }}</span>
            </button>
          </div>
          <p v-if="!mail.connected" class="small">
            {{ tr('Connecte ta boîte Gmail pour pouvoir envoyer.') }}
          </p>
          <button
            v-if="!mail.connected && isExpanded"
            type="button"
            class="secondary"
            @click="toggleView(false)"
          >
            {{ tr('Configurer Gmail') }}
          </button></template
        >
        <p v-else class="small">
          {{ tr('Parti le ') }}{{ date(mailSelected.sent_at) }}{{ tr(' vers ')
          }}{{ mailSelected.to }}.
        </p>
      </div>
    </div>
  </section>
</template>
