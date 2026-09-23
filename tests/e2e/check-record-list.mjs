// All API calls use fixtures; no user data is modified.
import assert from 'node:assert/strict';
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE ||
    new URL('../../ui/node_modules/playwright/index.mjs', import.meta.url).href
);
const base = process.env.SEARCHMYJOB_TEST_URL || 'http://127.0.0.1:8936';
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  headless: true,
});
const errors = [],
  writes = [];
const state = {
  token: 'fixture-only',
  profile: '',
  conversation_id: 'main',
  conversations: [{ id: 'main', title: 'Mon profil', archived: false }],
  messages: [],
  offers: [],
  runs: [],
  documents: [],
  emails: [],
  imports: [],
  tool_calls: [],
  models: {},
  connections: {},
  criteria: {
    country: 'fr',
    response_language: 'fr',
    objectif: 'emploi',
    axes: [],
    platforms: [],
    international: false,
    keywords: 'Python',
    department: '',
    location: '',
    contract: '',
    remote: true,
    freelance: true,
    min_tjm: 0,
    exclude: '',
    source: 'france',
  },
  settings: {
    enabled: false,
    interval_hours: 4,
    start_hour: 8,
    end_hour: 20,
    max_daily: 3,
    provider: 'openai',
    cache_hours: 24,
    instructions: '',
  },
  bright_budget: { used: 0, limit: 200, remaining: 200, blocked: false },
  agent_usage: { total_tokens: 1234, providers: {} },
  mail: { connected: false, address: '', pending: false, auth_url: '', error: '' },
  next_heartbeat: null,
};
let activated = true,
  configured = false;
const context = await browser.newContext({
  locale: 'fr-FR',
  viewport: { width: 1440, height: 1000 },
});
await context.route('**/api/**', async (route) => {
  const req = route.request(),
    path = new URL(req.url()).pathname;
  const body = req.method() === 'POST' ? req.postDataJSON() : null;
  if (body) writes.push({ path, body });
  let result = {};
  let status = 200;
  if (path === '/api/state') result = state;
  else if (path === '/api/activation') {
    if (body) {
      activated = true;
      state.profile = body.profile;
    }
    result = { completed: activated };
  } else if (path === '/api/workspace-memory')
    result = { preferences: null, heartbeat_draft: null };
  else if (path === '/api/ai') result = { openai: { configured, model: 'fixture-model' } };
  else if (path === '/api/ai/models') result = { models: ['fixture-model'] };
  else if (path === '/api/ai/test') {
    if (body.key === 'bad') {
      status = 422;
      result = { detail: 'Clé API refusée (HTTP 401).' };
    } else {
      configured = true;
      result = { ok: true };
    }
  } else if (path === '/api/connections') result = { france: true, bright: true };
  else if (path === '/api/search/options') result = { countries: ['fr', 'de', 'be', 'it'] };
  else if (path === '/api/bright/usage')
    result = { status: 'ok', used: 1234, period_start: '2026-09-01', checked_at: 1789690000 };
  else if (path === '/api/criteria') state.criteria = body;
  else if (
    !['/api/preferences', '/api/heartbeat-draft', '/api/mail', '/api/conversations'].includes(path)
  )
    errors.push('Unexpected API request: ' + path);
  await route.fulfill({ status, json: result });
});

state.profile =
  '# Profil professionnel\n\n## Expérience\n' +
  'Expérience de démonstration, compétences et réalisations. '.repeat(30);
state.offers = [
  {
    id: 'offer',
    title: 'Opportunité de démonstration',
    source: 'Fixture',
    description: 'Description de démonstration.',
    status: 'new',
    checks: [],
  },
];
state.documents = [
  {
    id: 'doc',
    offer_id: 'offer',
    kind: 'cv',
    text: 'CV de démonstration\n\n' + state.profile,
    created: 1789500000,
    approved: false,
  },
];
state.emails = [
  {
    id: 'email',
    to: 'demo@example.com',
    subject: 'Présentation professionnelle',
    body: 'Bonjour,\n\n' + state.profile,
    status: 'draft',
    updated: 1789500000,
  },
];
state.mail = { ...state.mail, connected: true, address: 'demo@example.com' };
state.messages = [
  {
    id: 'message',
    role: 'assistant',
    provider: 'fixture',
    text:
      'Bilan de démonstration. ' +
      'Voici les points utiles pour préparer votre candidature. '.repeat(30),
    created: 1789500000,
  },
];
const page = await context.newPage();
page.on('pageerror', (e) => errors.push(e.message));
async function nav(name) {
  const reveal = page.getByRole('button', { name: 'Afficher la navigation', exact: true });
  if (await reveal.isVisible()) await reveal.click();
  await page.locator('.app-sidebar nav').getByRole('button', { name, exact: true }).click();
  await page.waitForTimeout(450);
}

state.offers = Array.from({ length: 100 }, (_, i) => ({
  id: 'o' + i,
  title: 'Entreprise ' + String(i).padStart(3, '0'),
  checks: [],
}));
state.documents = Array.from({ length: 100 }, (_, i) => ({
  id: 'd' + i,
  offer_id: 'o' + i,
  kind: i % 2 ? 'letter' : 'cv',
  text: 'Document ' + i,
  approved: false,
  created: 1789500000 + i,
}));
state.emails = Array.from({ length: 100 }, (_, i) => ({
  id: 'e' + i,
  subject: 'Courrier ' + String(i).padStart(3, '0'),
  to: 'user' + i + '@example.com',
  body: 'Message ' + i,
  status: i % 5 ? 'draft' : 'sent',
  updated: 1789500000 + i,
}));
try {
  await page.goto(base);
  await page.getByLabel('Ton message', { exact: true }).waitFor();
  for (const section of ['Courrier', 'Documents']) {
    await nav(section);
    const list = page.locator('.record-list'),
      rows = list.locator('.record-row');
    assert.equal(await rows.count(), 8);
    assert.equal(await list.getByRole('status').innerText(), '1–8 / 100');
    const pane = page.locator('.pane-content:not(.pane-snapshot)');
    assert(await pane.evaluate((e) => e.scrollHeight < 2400));
    await list.getByLabel('Page de la liste', { exact: true }).selectOption('13');
    assert.equal(await rows.count(), 4);
    assert.equal(await list.getByRole('status').innerText(), '97–100 / 100');
    assert(await list.getByRole('button', { name: 'Page suivante', exact: true }).isDisabled());
    await rows.last().click();
    const editor = page.locator(section === 'Courrier' ? '.mail-editor' : '.document-editor');
    assert.equal(await editor.inputValue(), section === 'Courrier' ? 'Message 99' : 'Document 99');
    await editor.fill('Modifications conservées');
    await list.getByLabel('Rechercher dans la liste', { exact: true }).fill('099');
    assert.equal(await rows.count(), 1);
    assert.equal(await editor.inputValue(), 'Modifications conservées');
    await list.getByLabel('Rechercher dans la liste', { exact: true }).fill('introuvable xyz');
    assert.equal(await rows.count(), 0);
    assert.equal(await list.getByRole('status').innerText(), '0–0 / 0');
    await list.getByLabel('Rechercher dans la liste', { exact: true }).fill('');
    await list
      .getByLabel('Filtrer la liste', { exact: true })
      .selectOption(section === 'Courrier' ? 'draft' : 'letter');
    assert.equal(await rows.count(), 8);
    assert.equal(
      await list.getByRole('status').innerText(),
      section === 'Courrier' ? '1–8 / 80' : '1–8 / 50',
    );
    await list.getByLabel('Page de la liste', { exact: true }).selectOption('2');
    await page.getByRole('button', { name: 'Vue complète', exact: true }).click();
    assert.equal(await list.isVisible(), false);
    await page.getByRole('button', { name: 'Vue classique', exact: true }).click();
    assert.equal(await list.getByLabel('Page de la liste', { exact: true }).inputValue(), '2');
    assert.equal(await editor.inputValue(), 'Modifications conservées');
    for (const width of [2560, 1366, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      assert(await list.locator('.record-rows').evaluate((e) => e.clientHeight <= 521));
      if (width === 2560)
        await page.screenshot({
          path: '/tmp/smj-list-' + new URL(base).port + '-' + section + '.png',
        });
    }
    await list.getByLabel('Filtrer la liste', { exact: true }).selectOption('');
    await list.getByLabel('Page de la liste', { exact: true }).selectOption('13');
    await list.getByLabel('Rechercher dans la liste', { exact: true }).fill('001');
    assert.equal(await list.getByLabel('Page de la liste', { exact: true }).inputValue(), '1');
  }
  const language = page.getByLabel('Langue / Language');
  if (await language.count()) {
    await language.selectOption('en');
    assert(await page.getByLabel('Search this list', { exact: true }).isVisible());
    await page.getByLabel('Search this list', { exact: true }).fill('');
    await page.getByLabel('List page', { exact: true }).selectOption('2');
    assert(await page.getByRole('button', { name: 'Previous page', exact: true }).isEnabled());
  }
  assert(!writes.some((w) => w.path.includes('emails') || w.path.includes('documents')));
  assert.deepEqual(errors, []);
  console.log(
    'PASS ' +
      base +
      ': 100 emails and documents, eight rows/page, last page/direct jump/search/filter, unchanged editor across pagination/full view, mobile and English, no business writes.',
  );
} finally {
  await browser.close();
}
