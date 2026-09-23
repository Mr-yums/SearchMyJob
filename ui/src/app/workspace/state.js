import { tr, intlLocale } from '../../shared/i18n/index.js';

import { ref, computed } from 'vue';
import { prettyTitle } from '../../shared/utils/titles.js';
export function initializeWorkspaceState(ctx) {
  ctx.conversationId = ref(localStorage.getItem('smj-conversation') || 'main');
  ctx.conversationArchived = computed(
    () =>
      !!ctx.state.value?.conversations?.find((c) => c.id === ctx.conversationId.value)?.archived,
  );
  ctx.conversationBusy = computed(() =>
    ctx.state.value?.runs?.some(
      (r) => r.status === 'running' && r.conversation_id === ctx.conversationId.value,
    ),
  );
  ctx.activation = ref(null);
  ctx.tab = ref('conversation');
  ctx.state = ref(null);
  ctx.criteria = ref({});
  ctx.settings = ref({});
  ctx.profile = ref('');
  ctx.draft = ref(
    localStorage.getItem(ctx.draftKey()) ||
      (ctx.conversationId.value === 'main' ? localStorage.getItem('smj-draft') : '') ||
      '',
  );
  ctx.provider = ref('openai');
  ctx.error = ref('');
  ctx.notice = ref('');
  ctx.loading = ref(false);
  ctx.filter = ref('all');
  ctx.resultType = ref('all');
  ctx.query = ref('');
  ctx.selected = ref(null);
  ctx.docText = ref('');
  ctx.docApproved = ref(false);
  ctx.credentials = ref({
    ft_client_id: '',
    ft_client_secret: '',
    bright_key: '',
    bright_zone: '',
  });
  ctx.brightLimit = ref(null);
  ctx.timer = undefined;
  ctx.clockTimer = undefined;
  ctx.pages = [
    ['conversation', '◎', 'Conversation'],
    ['offers', '⌕', 'Opportunités'],
    ['documents', '▤', 'Documents'],
    ['mail', '✉', 'Courrier'],
    ['profile', '◉', 'Mon profil'],
    ['heartbeat', '◷', 'Veille & checkups'],
    ['connections', '⇄', 'Connexions'],
  ];
  ctx.modes = [1, 2, 4];
  ctx.themes = [
    ['classique', 'Classique'],
    ['searchmyjob', 'SearchMyJob'],
    ['sombre', 'Sombre'],
  ];
  ctx.themeColors = {
    classique: '#6b52c2',
    searchmyjob: '#2a1f4d',
    sombre: '#14111f',
  };
  ctx.theme = ref(
    ctx.themes.some((t) => t[0] === localStorage.getItem('smj-theme'))
      ? localStorage.getItem('smj-theme')
      : 'classique',
  );
  ctx.pageWidth = ref(localStorage.getItem('smj-page-width') === 'full' ? 'full' : 'centered');
  ctx.agentWidth = ref(localStorage.getItem('smj-agent-width') === 'normal' ? 'normal' : 'full');
  ctx.layoutMode = ref(
    ctx.modes.includes(Number(localStorage.getItem('smj-layout-mode')))
      ? Number(localStorage.getItem('smj-layout-mode'))
      : 1,
  );
  ctx.defaultPanels = ['conversation', 'offers', 'documents', 'heartbeat'];
  ctx.panels = ref(ctx.restoredPanels());
  ctx.activePanel = ref(0);
  if (ctx.layoutMode.value > 1) ctx.tab.value = ctx.panels.value[0];
  ctx.visiblePanels = computed(() =>
    ctx.layoutMode.value === 1 ? [ctx.tab.value] : ctx.panels.value.slice(0, ctx.layoutMode.value),
  );
  ctx.editingProfile = ref(false);
  ctx.offerDetail = ref(null);
  ctx.showSearch = ref(false);
  ctx.messageLists = ref([]);
  ctx.offerDialog = ref(null);
  ctx.profileDirty = computed(() => ctx.profile.value !== ctx.state.value?.profile);
  ctx.profileTitle = computed(
    () =>
      prettyTitle(ctx.state.value?.profile?.split('\n')[0] || '') ||
      tr('Ton profil reste à compléter'),
  );
  ctx.brief = computed(() => {
    const p = ctx.state.value?.profile || '';
    return [
      p.includes('Disponibilité : dès maintenant') ? tr('Disponible maintenant') : null,
      p.includes('100 % à distance') ? tr('100 % à distance') : null,
      p.includes('France et international') ? tr('France & international') : null,
    ].filter(Boolean);
  });
  ctx.quickPrompts = [
    {
      label: 'Trouver ma prochaine mission',
      text: 'À partir de mon profil et de mes critères, cherche des opportunités avec les sources configurées. Commence par une recherche ciblée ; distingue les conditions confirmées de celles à vérifier.',
    },
    {
      label: 'Valoriser mes projets',
      text: 'À partir de mon profil, aide-moi à présenter mes trois projets les plus pertinents à un client freelance. Utilise uniquement les faits disponibles.',
    },
    {
      label: 'Préparer mon offre de services',
      text: 'Aide-moi à formuler une offre de services claire à partir de mon profil, sans inventer de références clients.',
    },
  ];
  ctx.collapsed = ref(
    localStorage.getItem('smj-sidebar-collapsed') === 'true' ||
      (!localStorage.getItem('smj-sidebar-collapsed') && innerWidth < 900),
  );
  ctx.showTasks = ref(innerWidth >= 1100);
  ctx.showLayouts = ref(false);
  ctx.openedTabs = ref(ctx.restoreTabs());
  ctx.recentTasks = computed(() => (ctx.state.value?.runs || []).slice(0, 4));
  // [OXIO 15/09/2026] Hors conversation, la barre de gauche disparaît ; un bouton d'en-tête la rappelle le temps d'un choix.
  // [OXIO] Le menu Disposition/Thème se referme après un choix, au clic extérieur et à Échap (sinon il recouvre la navigation sur mobile).
  document.addEventListener('click', (e) => {
    if (ctx.showLayouts.value && !e.target.closest('.layout-control'))
      ctx.showLayouts.value = false;
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') ctx.showLayouts.value = false;
  });
  ctx.forceSidebar = ref(false);
  ctx.sidebarHidden = computed(
    () => !ctx.visiblePanels.value.includes('conversation') && !ctx.forceSidebar.value,
  );
  ctx.activeRun = computed(() => ctx.state.value?.runs.find((r) => r.status === 'running'));
  ctx.busy = computed(() => !!ctx.activeRun.value);
  ctx.taskPhase = computed(() => ctx.activeRun.value?.phase || tr('Traitement en cours'));
  ctx.clockNow = ref(Date.now());
  ctx.elapsedTime = computed(() => {
    const seconds = Math.max(
      0,
      Math.floor(
        ctx.clockNow.value / 1000 - (ctx.activeRun.value?.created || ctx.clockNow.value / 1000),
      ),
    );
    return (
      String(Math.floor(seconds / 60)).padStart(2, '0') +
      ':' +
      String(seconds % 60).padStart(2, '0')
    );
  });
  ctx.offers = computed(() =>
    (ctx.state.value?.offers || []).filter(
      (o) =>
        (ctx.filter.value === 'all' || o.status === ctx.filter.value) &&
        (ctx.resultType.value === 'all' || o.result_kind === ctx.resultType.value) &&
        (o.title + ' ' + o.company + ' ' + o.location)
          .toLowerCase()
          .includes(ctx.query.value.toLowerCase()),
    ),
  );
  ctx.counts = computed(() => ({
    new: ctx.state.value?.offers.filter((o) => o.status === 'new').length || 0,
    saved: ctx.state.value?.offers.filter((o) => o.status === 'saved').length || 0,
    docs: ctx.state.value?.documents.length || 0,
  }));
  ctx.date = (t) =>
    t
      ? new Date(t * 1000).toLocaleString(intlLocale.value, {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        })
      : tr('Pas encore planifié');
  ctx.statusText = (s) =>
    ({
      running: tr('En cours'),
      completed: tr('Terminé'),
      failed: tr('Échec'),
      interrupted: tr('Interrompu'),
      cancelled: tr('Arrêté'),
    })[s] || s;
  ctx.mailForm = ref({
    to: '',
    subject: '',
    body: '',
  });
  ctx.mailSelected = ref(null);
  ctx.mailConfirm = ref(false);
  ctx.senderName = ref('');
  ctx.emails = computed(() =>
    (ctx.state.value?.emails || []).filter((e) => e.status !== 'discarded'),
  );
  ctx.mail = computed(
    () =>
      ctx.state.value?.mail || {
        connected: false,
        address: '',
        pending: false,
        auth_url: '',
        error: '',
      },
  );
  ctx.memoryStatus = ref('');
  ctx.memoryReady = ref(false);
  ctx.preferenceTimer = undefined;
  ctx.heartbeatTimer = undefined;
  ctx.memoryQueue = Promise.resolve();
}
