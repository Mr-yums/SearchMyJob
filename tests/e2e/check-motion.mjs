// All API calls are mocked; this test does not alter the user workspace.
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
try {
  await page.goto(base);
  await page.getByLabel('Ton message', { exact: true }).waitFor();
  state.messages[0].text = 'Message long pour vérifier le défilement. '.repeat(300);
  await page.reload();
  await page.getByLabel('Ton message', { exact: true }).waitFor();
  await page.getByLabel('Ton message', { exact: true }).fill('Brouillon à conserver');
  const clickNav = async (name) =>
    page
      .locator('.app-sidebar nav')
      .getByRole('button', { name, exact: true, includeHidden: true })
      .evaluate((e) => e.click());
  await clickNav('Opportunités');
  await page.locator('.pane-snapshot').waitFor({ state: 'attached' });
  assert.equal(await page.locator('.pane-content:not(.pane-snapshot)').count(), 1);
  assert.equal(await page.locator('.pane-snapshot[inert][aria-hidden="true"]').count(), 1);
  assert.equal(await page.locator('.pane-snapshot [id]').count(), 0);
  await page.evaluate(() =>
    document.getAnimations().forEach((a) => {
      a.pause();
      a.currentTime = 130;
    }),
  );
  await page.screenshot({ path: '/tmp/smj-motion-' + new URL(base).port + '.png' });
  await page.evaluate(() => document.getAnimations().forEach((a) => a.play()));
  await page.waitForTimeout(450);
  for (let i = 0; i < 40; i++) {
    await clickNav(i % 2 ? 'Conversation' : 'Documents');
    await page.waitForTimeout(18);
    assert((await page.locator('.pane-snapshot').count()) <= 1);
    assert.equal(await page.locator('.pane-content:not(.pane-snapshot)').count(), 1);
  }
  await clickNav('Conversation');
  await page.waitForTimeout(500);
  assert.equal(await page.locator('.pane-snapshot').count(), 0);
  assert.equal(
    await page.evaluate(
      () =>
        Array.from(document.querySelectorAll('.pane-stage > .pane-content')).flatMap((e) =>
          e.getAnimations(),
        ).length,
    ),
    0,
  );
  assert.equal(
    await page.getByLabel('Ton message', { exact: true }).inputValue(),
    'Brouillon à conserver',
  );
  assert(
    await page
      .locator('.messages')
      .evaluate((e) => e.scrollHeight <= e.clientHeight + 2 || e.scrollTop > 0),
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await clickNav('Documents');
  await page.waitForTimeout(50);
  assert.equal(await page.locator('.pane-snapshot').count(), 0);
  await clickNav('Conversation');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  for (const width of [2560, 1920, 1366, 900, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const name of [
      'Opportunités',
      'Documents',
      'Courrier',
      'Mon profil',
      'Veille & checkups',
      'Connexions',
      'Conversation',
    ]) {
      await nav(name);
      if (name === 'Documents' || name === 'Courrier')
        await page.locator('.record-row').first().click();
      const box = await page.locator('.pane-content').evaluate((p) => {
        const s = p.querySelector(':scope > section'),
          r = s.getBoundingClientRect(),
          parent = p.getBoundingClientRect();
        return {
          width: r.width,
          center: r.x + r.width / 2,
          parentCenter: parent.x + p.clientWidth / 2,
          overflow: p.scrollWidth > p.clientWidth + 1,
        };
      });
      if (name !== 'Conversation')
        assert(box.width <= 1101, `${name} width ${width}: ${JSON.stringify(box)}`);
      assert(
        Math.abs(box.center - box.parentCenter) < 2,
        `${name} center ${width}: ${JSON.stringify(box)}`,
      );
      assert(!box.overflow, `${name} pane overflow ${width}`);
      assert(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        `${name} viewport overflow ${width}`,
      );
      if (name === 'Documents' || name === 'Courrier')
        assert(
          await page
            .locator('.document-editor')
            .evaluate((e) => parseFloat(getComputedStyle(e).fontSize) >= 15),
        );
      if (width === 2560 && ['Opportunités', 'Documents', 'Courrier', 'Mon profil'].includes(name))
        await page.screenshot({
          path:
            '/tmp/smj-centered-' +
            new URL(base).port +
            '-' +
            {
              Opportunités: 'offers',
              Documents: 'documents',
              Courrier: 'mail',
              'Mon profil': 'profile',
            }[name] +
            '.png',
        });
    }
  }
  await page.setViewportSize({ width: 2560, height: 1200 });
  await page.getByRole('button', { name: 'Choisir la disposition', exact: true }).click();
  const pagesGroup = page.getByRole('group', { name: 'Largeur des pages', exact: true });
  const agentGroup = page.getByRole('group', { name: 'Affichage de l’agent', exact: true });
  await agentGroup.getByRole('button', { name: 'Normal', exact: true }).click();
  assert(
    await page
      .locator('.conversation-view')
      .evaluate((e) => e.getBoundingClientRect().width <= 1101),
  );
  await agentGroup.getByRole('button', { name: 'Pleine largeur', exact: true }).click();
  assert(
    await page
      .locator('.conversation-view')
      .evaluate((e) => Math.abs(e.getBoundingClientRect().width - e.parentElement.clientWidth) < 2),
  );
  await pagesGroup.getByRole('button', { name: 'Pleine largeur', exact: true }).click();
  await page.getByRole('button', { name: 'Choisir la disposition', exact: true }).click();
  await nav('Opportunités');
  assert(
    await page
      .locator('.pane-content > section')
      .evaluate((e) => Math.abs(e.getBoundingClientRect().width - e.parentElement.clientWidth) < 2),
  );
  await page.waitForTimeout(650);
  assert(
    writes.some(
      (w) =>
        w.path === '/api/preferences' &&
        w.body.page_width === 'full' &&
        w.body.agent_width === 'full',
    ),
  );
  await page.reload();
  await page.getByLabel('Ton message', { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.dataset.pageWidth), 'full');
  assert.equal(await page.evaluate(() => document.documentElement.dataset.agentWidth), 'full');
  await page.getByRole('button', { name: 'Choisir la disposition', exact: true }).click();
  await pagesGroup.getByRole('button', { name: 'Centrées', exact: true }).click();
  await page.screenshot({ path: '/tmp/smj-preferences-' + new URL(base).port + '.png' });
  await page.getByRole('button', { name: '4 fenêtres', exact: true }).click();
  await page.waitForTimeout(250);
  assert.equal(await page.locator('.workspace-pane').count(), 4);
  for (const pane of await page.locator('.pane-content').all())
    assert(await pane.evaluate((p) => p.scrollWidth <= p.clientWidth + 1));
  assert.deepEqual(errors, []);
  console.log(
    'PASS ' +
      base +
      ': 40 rapid switches, one live page, no leftover animation, drafts and scrolling preserved; responsive layout at 2560/1920/1366/900/390, CV/mail readability, four panes, no real writes.',
  );
} finally {
  await browser.close();
}
