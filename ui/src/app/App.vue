<script setup>
import { tr } from '../shared/i18n/index.js';

import AppIcon from '../shared/components/AppIcon.vue';
import OfferDossier from '../features/opportunities/components/OfferDossier.vue';
import FirstActivation from '../features/onboarding/components/FirstActivation.vue';
import ConversationView from '../features/conversation/ConversationView.vue';
import OpportunitiesView from '../features/opportunities/OpportunitiesView.vue';
import ProfileView from '../features/profile/ProfileView.vue';
import DocumentsView from '../features/documents/DocumentsView.vue';
import MonitoringView from '../features/monitoring/MonitoringView.vue';
import MailView from '../features/mail/MailView.vue';
import ConnectionsView from '../features/connections/ConnectionsView.vue';
import WorkspacePaneContent from './components/WorkspacePaneContent.vue';
import { useWorkspace } from './useWorkspace.js';
const {
  views,
  activation,
  completeActivation,
  tab,
  state,
  profile,
  error,
  notice,
  selected,
  pages,
  modes,
  themes,
  theme,
  layoutMode,
  activePanel,
  visiblePanels,
  scrollMessages,
  setPanel,
  changeLayout,
  focusPanel,
  offerDetail,
  offerDialog,
  preparePrompt,
  collapsed,
  showTasks,
  showLayouts,
  openedTabs,
  forceSidebar,
  sidebarHidden,
  navigate,
  closeTab,
  moveTab,
  busy,
  offers,
  counts,
  mail,
  memoryStatus,
} = useWorkspace();
import WorkspaceTabs from './components/WorkspaceTabs.vue';
import AppHeader from './components/AppHeader.vue';
import AppSidebar from './components/AppSidebar.vue';
</script>
<template>
  <FirstActivation
    v-if="activation?.completed === false && state"
    :token="state.token"
    @activated="completeActivation"
  />
  <div
    v-else
    class="layout"
    :class="{
      'multi-layout': layoutMode > 1,
      'sidebar-collapsed': collapsed,
      'sidebar-hidden': sidebarHidden,
      'tasks-open': showTasks,
    }"
  >
    <AppSidebar :model="views.AppSidebar" />
    <main>
      <AppHeader :model="views.AppHeader" />
      <WorkspaceTabs v-if="sidebarHidden" :model="views.WorkspaceTabs" />
      <div v-if="error" class="alert error" role="alert">
        {{ tr(error) }} <button @click="error = ''">{{ tr('Fermer') }}</button>
      </div>
      <div v-if="notice" class="alert" role="status">
        {{ tr(notice) }} <button @click="notice = ''">×</button>
      </div>
      <div v-if="!state" class="empty">{{ tr('Connexion à ton espace…') }}</div>
      <div
        v-else
        id="workspace-content"
        :role="layoutMode === 1 ? 'tabpanel' : undefined"
        :aria-labelledby="layoutMode === 1 ? 'tab-' + tab : undefined"
        class="workspace-grid"
        :class="'windows-' + layoutMode"
      >
        <article
          v-for="(pane, index) in visiblePanels"
          :key="index"
          class="workspace-pane"
          :class="{ focused: activePanel === index }"
          @pointerdown="focusPanel(index)"
          @focusin="focusPanel(index)"
        >
          <div v-if="layoutMode > 1" class="pane-toolbar">
            <span class="pane-number">{{ index + 1 }}</span
            ><select
              :aria-label="tr('Contenu de la fenêtre ') + (index + 1)"
              :value="pane"
              @change="setPanel(index, $event.target.value)"
            >
              <option v-for="p in pages" :key="p[0]" :value="p[0]">
                {{ tr(p[2]) }}
              </option></select
            ><button
              class="subtle"
              :aria-label="tr('Agrandir la fenêtre ') + (index + 1)"
              @click="
                focusPanel(index);
                changeLayout(1);
              "
            >
              ↗
            </button>
          </div>
          <WorkspacePaneContent :page="pane" @settled="pane === 'conversation' && scrollMessages()">
            <ConversationView v-if="pane === 'conversation'" :model="views.conversation" />
            <OpportunitiesView v-if="pane === 'offers'" :model="views.offers" />
            <ProfileView v-if="pane === 'profile'" :model="views.profile" />
            <DocumentsView v-if="pane === 'documents'" :model="views.documents" />
            <MonitoringView v-if="pane === 'heartbeat'" :model="views.heartbeat" />
            <MailView v-if="pane === 'mail'" :model="views.mail" />
            <ConnectionsView v-if="pane === 'connections'" :model="views.connections" />
          </WorkspacePaneContent>
        </article>
      </div>
    </main>
  </div>
  <dialog
    ref="offerDialog"
    v-if="offerDetail"
    class="offer-dialog"
    :aria-label="tr('Détail de l’opportunité')"
    @cancel.prevent="offerDetail = null"
    @close="offerDetail = null"
  >
    <button
      class="icon-button dialog-close"
      :aria-label="tr('Fermer le détail')"
      @click="offerDetail = null"
    >
      <AppIcon name="close" /></button
    ><span class="tag">{{ offerDetail.source }}</span>
    <h2>{{ offerDetail.title }}</h2>
    <p>
      {{ offerDetail.company || tr('Entreprise à vérifier') }} ·
      {{ offerDetail.location || tr('Lieu à vérifier') }}
    </p>
    <div class="tags">
      <span v-for="check in offerDetail.checks" :key="check">{{ tr(check) }}</span>
    </div>
    <p class="pre">
      {{ offerDetail.description || tr('Le détail est disponible sur le site source.') }}
    </p>
    <a v-if="offerDetail.url" :href="offerDetail.url" target="_blank" rel="noopener noreferrer">{{
      tr('Consulter la source ↗')
    }}</a
    ><OfferDossier :key="offerDetail.id" :offer="offerDetail" :token="state.token" :busy="busy" />
    <div class="form-actions">
      <button
        @click="
          preparePrompt(
            tr('Analyse cette opportunité au regard de mon profil : ') +
              offerDetail.title +
              tr(' (identifiant ') +
              offerDetail.id +
              tr('). Explique les correspondances et les conditions à vérifier.'),
          );
          offerDetail = null;
        "
      >
        {{ tr('En parler à mon équipe ') }}<AppIcon name="arrow" :size="16" />
      </button>
    </div>
  </dialog>
</template>
