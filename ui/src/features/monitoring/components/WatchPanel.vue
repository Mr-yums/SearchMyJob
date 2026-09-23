<script setup>
import { tr, intlLocale } from '../../../shared/i18n/index.js';
import { ref, computed } from 'vue';
import AppIcon from '../../../shared/components/AppIcon.vue';
const props = defineProps({
  state: Object,
  settings: Object,
  busy: Boolean,
  loading: Boolean,
});
const emit = defineEmits(['save', 'checkup', 'mail']);
const sections = [
  ['config', 'sliders', 'Configuration'],
  ['tasks', 'clock', 'Tâches planifiées'],
  ['logs', 'documents', 'Logs'],
];
const active = ref(0),
  direction = ref('next'),
  logFilter = ref('all');
let touch = null;
function select(index, focus = false) {
  direction.value = index > active.value ? 'next' : 'previous';
  active.value = index;
  if (focus) document.getElementById('watch-tab-' + sections[index][0])?.focus();
}
function keyTab(event) {
  let index = active.value;
  if (event.key === 'ArrowRight') index = (index + 1) % 3;
  else if (event.key === 'ArrowLeft') index = (index + 2) % 3;
  else if (event.key === 'Home') index = 0;
  else if (event.key === 'End') index = 2;
  else return;
  event.preventDefault();
  select(index, true);
}
function touchStart(event) {
  if (event.target.closest('input,textarea,select,button,a,summary')) return;
  const t = event.changedTouches[0];
  touch = {
    x: t.clientX,
    y: t.clientY,
  };
}
function touchEnd(event) {
  if (!touch) return;
  const t = event.changedTouches[0],
    dx = t.clientX - touch.x,
    dy = t.clientY - touch.y;
  touch = null;
  if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5)
    select(Math.max(0, Math.min(2, active.value + (dx < 0 ? 1 : -1))));
}
const presets = [
  {
    name: 'Matin tranquille',
    description: 'Un passage, de 8 h à 12 h',
    interval_hours: 24,
    max_daily: 1,
    start_hour: 8,
    end_hour: 12,
  },
  {
    name: 'Suivi régulier',
    description: 'Toutes les 4 h, de 8 h à 20 h',
    interval_hours: 4,
    max_daily: 3,
    start_hour: 8,
    end_hour: 20,
  },
  {
    name: 'Veille soutenue',
    description: 'Toutes les 2 h, de 8 h à 20 h',
    interval_hours: 2,
    max_daily: 6,
    start_hour: 8,
    end_hour: 20,
  },
];
const fields = ['interval_hours', 'max_daily', 'start_hour', 'end_hour'];
function matches(p) {
  return fields.every((k) => props.settings[k] === p[k]);
}
function preset(p) {
  for (const k of fields) props.settings[k] = p[k];
}
const dirty = computed(
  () => JSON.stringify(props.settings) !== JSON.stringify(props.state.settings),
);
const logs = computed(() =>
  props.state.runs.filter(
    (r) =>
      logFilter.value === 'all' ||
      (logFilter.value === 'issues'
        ? ['failed', 'interrupted', 'cancelled'].includes(r.status)
        : r.kind === 'heartbeat' || r.kind === 'checkup'),
  ),
);
const date = (t) =>
  t
    ? new Date(t * 1000).toLocaleString(intlLocale.value, {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Europe/Paris',
      })
    : tr('À planifier');
const status = (s) =>
  ({
    running: tr('En cours'),
    completed: tr('Terminé'),
    failed: tr('Échec'),
    interrupted: tr('Interrompu'),
    cancelled: tr('Arrêté'),
  })[s] || s;
const kind = (k) =>
  ({
    heartbeat: tr('Veille automatique'),
    checkup: 'Check-up',
    search: tr('Recherche'),
    chat: 'Conversation',
    document: 'Document',
    connections: tr('Connexions'),
  })[k] || k;
const pending = computed(
  () => (props.state.emails || []).filter((e) => e.status === 'draft').length,
);
</script>
<template>
  <section class="heartbeat-view watch-view">
    <div class="page-heading compact">
      <div>
        <span class="eyebrow">{{ tr('TON COPILOTE AU QUOTIDIEN') }}</span>
        <h1>{{ tr('Veille & check-ups') }}</h1>
        <p>
          {{ tr('Un rythme clair. Les bonnes opportunités. Tu gardes la main.') }}
        </p>
      </div>
      <span class="pill">{{ state.settings.enabled ? tr('Veille active') : tr('En pause') }}</span>
    </div>
    <div class="watch-nav" role="tablist" :aria-label="tr('Menu de veille')" @keydown="keyTab">
      <button
        v-for="(section, index) in sections"
        :key="section[0]"
        :id="'watch-tab-' + section[0]"
        type="button"
        role="tab"
        :aria-selected="active === index"
        :aria-controls="'watch-panel-' + section[0]"
        :tabindex="active === index ? 0 : -1"
        @click="select(index)"
      >
        <AppIcon :name="section[1]" :size="16" /><span>{{ tr(section[2]) }}</span
        ><small v-if="index === 2">{{ state.runs.length }}</small>
      </button>
    </div>
    <div
      class="watch-viewport"
      @touchstart.passive="touchStart"
      @touchend.passive="touchEnd"
      @touchcancel="touch = null"
    >
      <Transition :name="'watch-' + direction" mode="out-in">
        <div
          :key="active"
          :id="'watch-panel-' + sections[active][0]"
          role="tabpanel"
          :aria-labelledby="'watch-tab-' + sections[active][0]"
          tabindex="0"
        >
          <form v-if="active === 0" class="watch-config" @submit.prevent="emit('save')">
            <label class="watch-toggle card"
              ><span class="watch-tile-icon"><AppIcon name="heartbeat" /></span
              ><span
                ><strong>{{ tr('Activer la veille automatique') }}</strong
                ><small>{{
                  tr('Recherche et bilan selon le rythme choisi ci-dessous.')
                }}</small></span
              ><input
                type="checkbox"
                v-model="settings.enabled"
                role="switch"
                :aria-label="tr('Activer la veille automatique')"
            /></label>
            <div class="card watch-card">
              <div class="watch-section-title">
                <span class="watch-step">01</span>
                <div>
                  <h2>{{ tr('Choisis ton rythme') }}</h2>
                  <p>
                    {{ tr('Un point de départ, ajustable à tout moment.') }}
                  </p>
                </div>
              </div>
              <div class="watch-presets">
                <button
                  v-for="p in presets"
                  :key="p.name"
                  type="button"
                  :aria-pressed="matches(p)"
                  @click="preset(p)"
                >
                  <AppIcon :name="matches(p) ? 'check' : 'clock'" :size="18" /><strong>{{
                    tr(p.name)
                  }}</strong
                  ><small>{{ tr(p.description) }}</small>
                </button>
              </div>
              <div class="watch-fields">
                <label
                  >{{ tr('Toutes les (heures)')
                  }}<input
                    type="number"
                    min="1"
                    max="168"
                    required
                    v-model.number="settings.interval_hours" /></label
                ><label
                  >{{ tr('Passages maximum / jour')
                  }}<input
                    type="number"
                    min="1"
                    max="24"
                    required
                    v-model.number="settings.max_daily" /></label
                ><label
                  >{{ tr('Début · heure de Paris')
                  }}<input
                    type="number"
                    min="0"
                    max="23"
                    required
                    v-model.number="settings.start_hour" /></label
                ><label
                  >{{ tr('Fin · heure de Paris')
                  }}<input
                    type="number"
                    :min="Number(settings.start_hour) + 1"
                    max="24"
                    required
                    v-model.number="settings.end_hour"
                /></label>
              </div>
              <label
                >{{ tr('Réutiliser une recherche Bright Data pendant (heures)')
                }}<input
                  type="number"
                  min="0"
                  max="168"
                  required
                  v-model.number="settings.cache_hours"
              /></label>
              <p class="small">
                {{
                  tr(
                    'Une recherche identique réutilise ses sources en base pendant cette durée. 0 désactive le cache. « Actualiser les sources » force une nouvelle collecte.',
                  )
                }}
              </p>
              <p class="small">
                {{
                  tr(
                    'L’intervalle démarre à l’enregistrement. Un passage hors plage attend la prochaine ouverture. L’ordinateur et le service doivent rester allumés.',
                  )
                }}
              </p>
            </div>
            <div class="card watch-card">
              <div class="watch-section-title">
                <span class="watch-step">02</span>
                <div>
                  <h2>{{ tr('Donne le cap à ton agent') }}</h2>
                  <p>
                    {{ tr('Chaque passage recherche les offres et prépare un bilan.') }}
                  </p>
                </div>
              </div>
              <label
                >{{ tr('Qui prépare le check-up ?')
                }}<select v-model="settings.provider">
                  <option value="deepseek">DeepSeek</option>
                  <option value="kimi">Kimi</option>
                  <option value="claude">Claude</option>
                  <option value="openai">OpenAI</option>
                </select></label
              ><label
                >{{ tr('Consignes de veille')
                }}<textarea
                  v-model="settings.instructions"
                  maxlength="3000"
                  rows="4"
                  :placeholder="tr('Les missions à privilégier, les points à vérifier…')"
                ></textarea>
              </label>
            </div>
            <div class="card watch-card">
              <div class="watch-section-title">
                <span class="watch-step">03</span>
                <div>
                  <h2>{{ tr('Du repérage au premier contact') }}</h2>
                  <p>
                    {{ tr('Le parcours email proposé pour aller plus loin.') }}
                  </p>
                </div>
              </div>
              <ol class="watch-workflow">
                <li>
                  <strong>{{ tr('Repérer & résumer') }}</strong
                  ><span>{{ tr('Disponible dans chaque heartbeat.') }}</span>
                </li>
                <li>
                  <strong>{{ tr('Préparer le bon email') }}</strong
                  ><span>{{
                    tr('Disponible depuis une opportunité ; relecture et envoi dans Courrier.')
                  }}</span>
                </li>
                <li>
                  <strong>{{ tr('Lire les réponses & proposer une relance') }}</strong
                  ><span>{{
                    tr('À relier au heartbeat : la lecture mail existe dans un module séparé.')
                  }}</span>
                </li>
              </ol>
              <div class="watch-mail-note">
                <AppIcon name="mail" />
                <p>
                  {{
                    state.mail?.connected
                      ? tr('Boîte d’envoi connectée.')
                      : tr('Connecte ta boîte dans Courrier pour envoyer tes emails.')
                  }}{{ tr(' L’envoi actuel demande ta validation.') }}
                </p>
                <button type="button" class="secondary" @click="emit('mail')">
                  {{ tr('Ouvrir Courrier ') }}<AppIcon name="arrow" :size="15" />
                </button>
              </div>
            </div>
            <div class="watch-save">
              <span
                >{{ dirty ? tr('Modifications à enregistrer') : tr('Réglages enregistrés')
                }}<small
                  >Bright Data : {{ state.bright_budget?.used ?? '?' }} /
                  {{ state.bright_budget?.limit ?? '?'
                  }}{{ tr(' · appels agent selon usage') }}</small
                ></span
              ><button :disabled="loading">
                {{ loading ? tr('Enregistrement…') : tr('Enregistrer la veille') }}
              </button>
            </div>
          </form>
          <div v-else-if="active === 1" class="watch-tasks">
            <div class="card watch-card">
              <div class="watch-section-title">
                <span class="watch-tile-icon"><AppIcon name="clock" /></span>
                <div>
                  <h2>{{ tr('Prochain passage automatique') }}</h2>
                  <p>
                    {{
                      state.settings.enabled
                        ? tr('Échéance : ') + date(state.next_heartbeat)
                        : tr('La veille est en pause.')
                    }}
                  </p>
                </div>
              </div>
              <div class="watch-task-summary">
                <span
                  >{{ tr('Toutes les ')
                  }}<strong>{{ state.settings.interval_hours }} h</strong></span
                ><span
                  ><strong
                    >{{ state.settings.start_hour }} h – {{ state.settings.end_hour }} h</strong
                  >
                  · Paris</span
                ><span
                  ><strong>{{ state.settings.max_daily }}</strong
                  >{{ tr(' max / jour') }}</span
                >
              </div>
              <p class="small">
                {{
                  tr(
                    'Exécution à partir de l’échéance, dans la plage autorisée, selon le plafond quotidien et dès que l’agent est libre. Une seule tâche à la fois.',
                  )
                }}
              </p>
              <button type="button" class="secondary" @click="select(0)">
                {{ tr('Ajuster la planification') }}
              </button>
            </div>
            <div class="card watch-card">
              <div class="watch-section-title">
                <AppIcon name="spark" />
                <div>
                  <h2>{{ tr('Besoin d’un point maintenant ?') }}</h2>
                  <p>
                    {{ tr('Un check-up ponctuel utilise les critères et consignes enregistrés.') }}
                  </p>
                </div>
              </div>
              <button type="button" :disabled="busy || loading" @click="emit('checkup')">
                {{ busy ? tr('Une tâche est en cours') : tr('Faire un check-up maintenant') }}
              </button>
              <p v-if="dirty" class="small">
                {{ tr('Tes modifications de configuration ne sont pas encore enregistrées.') }}
              </p>
            </div>
            <div class="card watch-card">
              <h2>{{ tr('Emails à suivre') }}</h2>
              <p>
                {{ pending }}{{ tr(' brouillon') }}{{ pending > 1 ? 's' : ''
                }}{{
                  tr(' à relire dans Courrier. Aucune tâche email automatique n’est planifiée.')
                }}
              </p>
              <button type="button" class="secondary" @click="emit('mail')">
                {{ tr('Voir le courrier') }}
              </button>
            </div>
          </div>
          <div v-else class="card watch-card">
            <div class="watch-log-heading">
              <div>
                <h2>{{ tr('Journal des passages') }}</h2>
                <p>
                  {{ tr('Les 60 dernières exécutions, avec leur résultat.') }}
                </p>
              </div>
              <label
                >{{ tr('Afficher')
                }}<select v-model="logFilter" :aria-label="tr('Filtrer le journal')">
                  <option value="all">{{ tr('Tout le journal') }}</option>
                  <option value="watch">{{ tr('Veille & check-ups') }}</option>
                  <option value="issues">{{ tr('À vérifier') }}</option>
                </select></label
              >
            </div>
            <div v-if="!logs.length" class="watch-empty">
              <AppIcon name="documents" :size="28" />
              <h3>{{ tr('Aucun passage à afficher') }}</h3>
              <p>
                {{
                  logFilter === 'all'
                    ? tr('Les résultats apparaîtront ici après une première tâche.')
                    : tr('Aucune exécution ne correspond à ce filtre.')
                }}
              </p>
            </div>
            <details class="run" v-for="r in logs" :key="r.id">
              <summary>
                <span
                  class="tag"
                  :class="{
                    warning: ['failed', 'interrupted'].includes(r.status),
                  }"
                  >{{ status(r.status) }}</span
                ><strong>{{ kind(r.kind) }} · {{ r.provider }}</strong
                ><time>{{ date(r.created) }}</time>
              </summary>
              <p class="pre">
                {{ r.error || r.output || r.phase || tr('Traitement en cours…') }}
              </p>
            </details>
          </div>
        </div>
      </Transition>
    </div>
  </section>
</template>
<style scoped>
.watch-view {
  max-width: 1100px;
  margin: auto;
  container-type: inline-size;
}
.eyebrow {
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--accent-text);
  font-weight: 600;
}
.watch-nav {
  display: flex;
  padding: 5px;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: var(--surface-3);
  margin: 6px 0 24px;
}
.watch-nav button {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: transparent;
  color: var(--muted);
  padding: 12px 8px;
  border-radius: 9px;
  font-size: 12px;
  border: 1px solid transparent;
}
.watch-nav button[aria-selected='true'] {
  background: var(--surface);
  color: var(--accent-text);
  border-color: var(--line);
  box-shadow: 0 2px 8px rgba(var(--shadow-rgb), 0.06);
}
.watch-nav small {
  font-size: 10px;
}
.watch-viewport {
  overflow: hidden;
  touch-action: pan-y;
}
.watch-card {
  margin-bottom: 18px;
  padding: 24px;
}
.watch-card h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
.watch-card p {
  font-size: 12px;
  line-height: 1.7;
  margin: 7px 0 16px;
  color: var(--muted);
}
.watch-section-title {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 18px;
}
.watch-section-title p {
  margin-bottom: 0;
}
.watch-step,
.watch-tile-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 11px;
  background: var(--accent-tint);
  color: var(--accent-text);
  font-size: 12px;
}
.watch-toggle {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  margin: 0 0 18px;
  cursor: pointer;
}
.watch-toggle strong {
  font-size: 14px;
  color: var(--ink);
}
.watch-toggle small {
  display: block;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.6;
  color: var(--muted);
  margin-top: 5px;
}
.watch-toggle input {
  appearance: none;
  flex-shrink: 0;
  width: 42px;
  height: 24px;
  margin: 0 0 0 auto;
  border-radius: 99px;
  padding: 3px;
  background: var(--line-strong);
  border: 0;
  cursor: pointer;
}
.watch-toggle input:before {
  content: '';
  display: block;
  width: 18px;
  height: 18px;
  background: var(--surface);
  border-radius: 50%;
  transition: transform 0.2s;
}
.watch-toggle input:checked {
  background: var(--accent);
}
.watch-toggle input:checked:before {
  transform: translateX(18px);
}
.watch-presets {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 22px;
}
.watch-presets button {
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink);
  padding: 16px;
  text-align: left;
  border-radius: 12px;
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 9px;
}
.watch-presets button[aria-pressed='true'] {
  border-color: var(--accent);
  background: var(--accent-tint);
  color: var(--accent-text);
}
.watch-presets strong {
  font-size: 12px;
}
.watch-presets small {
  font-size: 11px;
  line-height: 1.6;
  font-weight: 400;
}
.watch-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.watch-card label {
  font-size: 11px;
  margin-bottom: 16px;
}
.watch-card textarea {
  min-height: 110px;
}
.watch-workflow {
  list-style: none;
  padding: 0;
  counter-reset: step;
  display: grid;
  gap: 0;
}
.watch-workflow li {
  counter-increment: step;
  position: relative;
  padding: 0 0 23px 37px;
}
.watch-workflow li:before {
  content: counter(step);
  position: absolute;
  left: 0;
  top: 0;
  border: 1px solid var(--line);
  border-radius: 50%;
  width: 23px;
  height: 23px;
  text-align: center;
  line-height: 23px;
  color: var(--accent-text);
  font-size: 11px;
}
.watch-workflow strong {
  display: block;
  font-size: 12px;
  margin-bottom: 5px;
}
.watch-workflow span {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.7;
}
.watch-mail-note {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: var(--surface-2);
  border-radius: 10px;
  padding: 14px;
}
.watch-mail-note p {
  flex: 1;
  min-width: 160px;
  margin: 0;
}
.watch-mail-note button {
  display: flex;
  gap: 8px;
  align-items: center;
}
.watch-save {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 2px;
}
.watch-save span {
  font-size: 12px;
  color: var(--accent-text);
}
.watch-save small {
  display: block;
  color: var(--muted);
  font-size: 10px;
  margin-top: 6px;
  line-height: 1.6;
}
.watch-task-summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
}
.watch-task-summary span {
  background: var(--surface-2);
  padding: 10px 13px;
  border-radius: 8px;
}
.watch-log-heading {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  flex-wrap: wrap;
}
.watch-empty {
  text-align: center;
  padding: 44px 12px;
  color: var(--muted);
}
.watch-empty svg {
  margin-bottom: 14px;
}
.watch-empty h3 {
  font-size: 14px;
}
.watch-next-enter-active,
.watch-next-leave-active,
.watch-previous-enter-active,
.watch-previous-leave-active {
  transition:
    transform 0.18s ease,
    opacity 0.18s ease;
}
.watch-next-enter-from,
.watch-previous-leave-to {
  transform: translateX(35px);
  opacity: 0;
}
.watch-next-leave-to,
.watch-previous-enter-from {
  transform: translateX(-35px);
  opacity: 0;
}
button:focus-visible,
input:focus-visible,
[role='tabpanel']:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}
@container (max-width:580px) {
  .watch-nav button {
    font-size: 10px;
    gap: 5px;
    flex-direction: column;
  }
  .watch-nav small {
    display: none;
  }
  .watch-presets {
    grid-template-columns: 1fr;
  }
  .watch-presets button {
    display: grid;
    grid-template-columns: 20px 1fr;
    padding: 13px;
  }
  .watch-presets small {
    grid-column: 2;
  }
  .watch-card {
    padding: 18px;
  }
  .watch-toggle {
    padding: 16px;
    gap: 10px;
  }
  .watch-toggle > .watch-tile-icon {
    display: none;
  }
  .watch-save {
    align-items: stretch;
    flex-direction: column;
  }
  .watch-fields {
    gap: 12px;
  }
  .watch-nav {
    margin-bottom: 16px;
  }
}
@container (max-width:320px) {
  .watch-fields {
    grid-template-columns: 1fr;
  }
  .watch-nav button {
    font-size: 9px;
    padding: 10px 2px;
  }
  .watch-section-title {
    gap: 8px;
  }
  .watch-card {
    padding: 14px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .watch-viewport *,
  .watch-toggle input:before {
    transition: none !important;
  }
}
</style>
