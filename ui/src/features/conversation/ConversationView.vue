<script setup>
import { toRefs } from 'vue';
import { tr } from '../../shared/i18n/index.js';

import AppIcon from '../../shared/components/AppIcon.vue';
import ConversationBar from './components/ConversationBar.vue';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const {
  conversationId,
  conversationArchived,
  conversationBusy,
  chooseConversation,
  newConversation,
  resetConversation,
  renameConversation,
  state,
  settings,
  profile,
  draft,
  provider,
  loading,
  filter,
  timer,
  quickPrompts,
  preparePrompt,
  openBeside,
  showTasks,
  recentTasks,
  navigate,
  busy,
  taskPhase,
  elapsedTime,
  offers,
  counts,
  date,
  statusText,
  api,
  action,
  send,
  saveDraft,
  search,
  registerMessageList,
} = toRefs(props.model);
</script>
<template>
  <section class="conversation-view">
    <div class="chat-grid">
      <div class="chat-panel">
        <div class="panel-head">
          <div class="chat-identity">
            <span class="assistant-mark"><AppIcon name="spark" :size="19" /></span>
            <div>
              <h2>Conversation</h2>
              <p>{{ busy ? tr(taskPhase) : tr('Assistant IA') }}</p>
            </div>
          </div>
          <button
            class="icon-button"
            :title="tr('Ouvrir les opportunités à côté')"
            :aria-label="tr('Ouvrir les opportunités à côté')"
            @click="openBeside('offers')"
          >
            <AppIcon name="offers" :size="19" />
          </button>
        </div>
        <ConversationBar
          :conversations="state.conversations || []"
          :current="conversationId"
          :busy="conversationBusy"
          :loading="loading"
          @select="chooseConversation"
          @create="newConversation"
          @rename="renameConversation"
          @reset="resetConversation"
        />
        <p v-if="conversationArchived" class="small" style="padding: 0 20px">
          {{
            tr(
              'Conversation archivée, conservée en lecture seule. Ouvre un nouveau chat pour continuer.',
            )
          }}
        </p>
        <div
          class="messages"
          :ref="registerMessageList"
          role="log"
          :aria-label="tr('Historique de conversation')"
        >
          <div v-if="!state.messages.length" class="welcome">
            <span class="round-mark"><AppIcon name="spark" :size="28" /></span>
            <h2>
              {{ state.profile ? tr('Que veux-tu faire ?') : tr('Nouvelle conversation') }}
            </h2>
            <p>
              {{
                state.profile
                  ? tr('Demande une recherche, travaille ton offre ou prépare une candidature.')
                  : tr('Tes projets et tes envies seront notre point de départ.')
              }}
            </p>
          </div>
          <article v-for="m in state.messages" :key="m.id" class="message" :class="m.role">
            <span v-if="m.role !== 'system'" class="message-avatar">{{
              m.role === 'user' ? 'T' : tr('IA')
            }}</span>
            <div class="message-content">
              <div class="message-label">
                {{ m.role === 'user' ? tr('Toi') : m.provider }}
                <time>{{ date(m.created) }}</time>
              </div>
              <div class="message-body">{{ m.text }}</div>
            </div>
          </article>
          <div v-if="conversationBusy" class="thinking task-progress">
            <i class="phase-spinner" aria-hidden="true"></i
            ><strong class="phase-label">{{ tr(taskPhase) }}</strong
            ><time
              class="phase-timer"
              aria-live="off"
              :title="tr('Temps écoulé depuis le début de la tâche')"
              :aria-label="tr('Temps écoulé : ') + elapsedTime"
              >{{ elapsedTime }}</time
            >
          </div>
        </div>
        <details v-if="state.tool_calls?.length" class="small" style="padding: 8px 20px">
          <summary>{{ tr('Outils utilisés dans ce chat') }}</summary>
          <ul>
            <li v-for="t in state.tool_calls" :key="t.id">
              {{ t.label }} · {{ t.provider }} · {{ statusText(t.status) }}
            </li>
          </ul>
        </details>
        <div class="quick-actions">
          <button v-for="(q, i) in quickPrompts" :key="q.label" @click="preparePrompt(tr(q.text))">
            <AppIcon :name="i === 0 ? 'search' : i === 1 ? 'profile' : 'spark'" :size="14" />{{
              tr(q.label)
            }}
          </button>
        </div>
        <form class="composer" @submit.prevent="send">
          <textarea
            :disabled="conversationArchived"
            :aria-label="tr('Ton message')"
            data-chat-input
            :placeholder="tr('Une envie, une mission, une question… parle-nous.')"
            v-model="draft"
            @input="saveDraft"
            @keydown.ctrl.enter.prevent="send"
          ></textarea>
          <div>
            <select aria-label="Agent" v-model="provider">
              <option value="deepseek">DeepSeek</option>
              <option value="kimi">Kimi</option>
              <option value="claude">Claude</option>
              <option value="openai">OpenAI</option></select
            ><span class="small">{{ tr('Ctrl + Entrée pour envoyer') }}</span
            ><button
              :disabled="busy || loading || conversationArchived || !draft.trim()"
              :aria-label="tr('Envoyer')"
            >
              <AppIcon name="send" :size="17" />{{ tr('Envoyer') }}
            </button>
          </div>
        </form>
      </div>
      <div v-if="showTasks" class="context-column">
        <div class="context-header">
          <h2>{{ tr('Activité') }}</h2>
          <button
            class="icon-button"
            :aria-label="tr('Masquer les tâches')"
            @click="showTasks = false"
          >
            <AppIcon name="close" :size="16" />
          </button>
        </div>
        <div class="agent-widget" :class="{ running: busy }">
          <div class="agent-orb" aria-hidden="true">
            <i></i><i></i><i></i><AppIcon name="spark" :size="24" />
          </div>
          <div>
            <strong>{{ tr('Assistant IA') }}</strong
            ><span>{{ busy ? tr(taskPhase) : tr('Prêts à travailler') }}</span>
          </div>
          <button
            v-if="busy"
            class="stop-task"
            @click="action(() => api('cancel'), tr('Arrêt demandé.'))"
          >
            {{ tr('Arrêter') }}
          </button>
        </div>
        <button class="profile-shortcut" @click="navigate('profile')">
          <span class="user-avatar">T</span><span>{{ tr('Voir mon profil') }}</span
          ><AppIcon name="chevron" :size="15" />
        </button>
        <div class="task-metrics">
          <button
            @click="
              navigate('offers');
              filter = 'new';
            "
          >
            <strong>{{ counts.new }}</strong
            ><span>{{ tr('Pistes') }}</span></button
          ><button
            @click="
              navigate('offers');
              filter = 'saved';
            "
          >
            <strong>{{ counts.saved }}</strong
            ><span>{{ tr('Retenues') }}</span></button
          ><button @click="navigate('documents')">
            <strong>{{ counts.docs }}</strong
            ><span>Documents</span>
          </button>
        </div>
        <div class="task-list">
          <div class="task-list-heading">
            <h3>{{ tr('Tâches récentes') }}</h3>
            <button class="text-button" @click="navigate('heartbeat')">
              {{ tr('Tout voir') }}
            </button>
          </div>
          <p v-if="!recentTasks.length" class="task-empty">
            {{ tr('Aucune tâche pour le moment.') }}
          </p>
          <button
            class="task-row"
            v-for="r in recentTasks"
            :key="r.id"
            @click="navigate('heartbeat')"
          >
            <span class="task-status" :class="r.status"
              ><AppIcon
                :name="
                  r.status === 'completed'
                    ? 'check'
                    : r.status === 'running'
                      ? 'clock'
                      : 'heartbeat'
                "
                :size="14" /></span
            ><span
              ><strong>{{
                {
                  chat: 'Conversation',
                  search: tr('Recherche'),
                  document: 'Document',
                  heartbeat: tr('Veille'),
                  checkup: tr('Bilan'),
                  connections: tr('Connexions'),
                }[r.kind] || r.kind
              }}</strong
              ><small>{{ date(r.created) }}</small></span
            ><em>{{ statusText(r.status) }}</em>
          </button>
        </div>
        <button class="watch-shortcut" @click="navigate('heartbeat')">
          <AppIcon name="clock" :size="16" /><span>{{
            state.settings.enabled ? tr('Veille active') : tr('Veille en pause')
          }}</span
          ><AppIcon name="chevron" :size="14" />
        </button>
      </div>
    </div>
  </section>
</template>
