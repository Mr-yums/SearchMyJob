// [OXIO 15/09/2026] Titres saisis en capitales rendus lisibles.
// Chaque suite de mots en capitales (titre entier, ou « JARVIS / AIOS » au début d'une ligne mixte) passe en
// minuscules avec majuscule initiale ; les sigles connus et les noms connus gardent leur forme ; une majuscule
// est remise après chaque séparateur (—, :, /) et après un numéro de section. Les mots avec chiffres sont gardés.
const ACRONYMS = new Set([
  'IA',
  'AI',
  'API',
  'RH',
  'CV',
  'TJM',
  'ATS',
  'SQL',
  'UI',
  'UX',
  'IT',
  'ETL',
  'BI',
  'PDF',
  'HTML',
  'CSS',
  'JS',
  'TS',
  'PHP',
  'AWS',
  'GCP',
  'ERP',
  'CRM',
  'IOT',
  'AIOS',
  'SEO',
  'SAAS',
  'B2B',
  'B2C',
  'R&D',
  'ML',
  'NLP',
  'LLM',
  'CI',
  'CD',
  'VPS',
  'NAS',
  'DNS',
  'SSH',
  'VPN',
  'MCP',
  'OS',
]);
const NAMES = {
  YUMS: 'Yums',
  JARVIS: 'Jarvis',
  PURPLECHART: 'PurpleChart',
  SEARCHMYJOB: 'SearchMyJob',
  TRACKMYSTART: 'TrackMyStart',
  LINKEDIN: 'LinkedIn',
  GITHUB: 'GitHub',
  PYTHON: 'Python',
  JAVASCRIPT: 'JavaScript',
  TYPESCRIPT: 'TypeScript',
  POSTGRESQL: 'PostgreSQL',
  DOCKER: 'Docker',
  LINUX: 'Linux',
  WINDOWS: 'Windows',
  FRANCE: 'France',
  PARIS: 'Paris',
  GROUPAMA: 'Groupama',
};
const core = (w) => w.replace(/[^A-ZÀ-Ÿ0-9&]/g, '');
const cap = (s) => s.charAt(0).toLocaleUpperCase('fr') + s.slice(1);
const isUpper = (w) => /[A-ZÀ-Ÿ]/.test(w) && w === w.toLocaleUpperCase('fr');
const isSep = (w) => /^[—–/:.,&'’-]+$/.test(w);
const isWordy = (w) =>
  w.replace(/[^A-ZÀ-Ÿ]/g, '').length >= 4 && !/\d/.test(w) && !ACRONYMS.has(core(w));
function convert(run) {
  return run.map((w, k) => {
    const c = core(w);
    if (/\d/.test(w) || ACRONYMS.has(c)) return w;
    if (NAMES[c]) return w.replace(c, NAMES[c]);
    const low = w.toLocaleLowerCase('fr');
    return k === 0 ? cap(low) : low;
  });
}
export function prettyTitle(title) {
  if (!title) return title;
  const tokens = title.split(' ');
  const out = [];
  let i = 0;
  while (i < tokens.length) {
    if (!isUpper(tokens[i])) {
      out.push(tokens[i]);
      i++;
      continue;
    }
    let j = i;
    while (j < tokens.length && (isUpper(tokens[j]) || isSep(tokens[j]))) j++;
    while (j > i && isSep(tokens[j - 1])) j--;
    const run = tokens.slice(i, j);
    out.push(...(run.some(isWordy) ? convert(run) : run));
    i = j;
  }
  let s = out.join(' ');
  s = s.replace(
    /(^|[—–:/]\s*|^\d+\.\s*)([a-zà-ÿ])/g,
    (m, pre, ch) => pre + ch.toLocaleUpperCase('fr'),
  );
  return cap(s);
}
