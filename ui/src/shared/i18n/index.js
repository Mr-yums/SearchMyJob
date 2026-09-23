import { ref, computed, watch } from 'vue';
import en from './locales/en.json';
function initialLanguage() {
  try {
    const saved = localStorage.getItem('smj-language');
    if (saved === 'fr' || saved === 'en') return saved;
  } catch {}
  return typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('en')
    ? 'en'
    : 'fr';
}
export const locale = ref(initialLanguage());
export const intlLocale = computed(() => (locale.value === 'en' ? 'en-GB' : 'fr-FR'));
const french = Object.fromEntries(Object.entries(en).map(([key, value]) => [value, key]));
// Only application-owned labels go through this function, never document or chat content.
export function tr(message, values = {}) {
  if (typeof message !== 'string') return message ?? '';
  const key = message.trim();
  const http = message.match(/^(.*)( \(HTTP \d{3}\)\.)$/);
  if (http) return tr(http[1]) + http[2];
  const check = message.match(
    /^(Freelance|100 % à distance|Sans déplacement|Langue \/ traduction|Disponibilité) : (.*)$/,
  );
  if (check) return tr(check[1]) + (locale.value === 'en' ? ': ' : ' : ') + tr(check[2]);
  const rate = message.match(/^TJM ≥ ([\d.]+) € à vérifier$/);
  if (rate)
    return tr('TJM ≥ {amount} € à vérifier', {
      amount: rate[1],
    });
  const translated = locale.value === 'en' ? en[key] : french[key];
  let result =
    translated === undefined
      ? message
      : message.slice(0, message.length - message.trimStart().length) +
        translated +
        message.slice(message.trimEnd().length);
  return result.replace(/\{(\w+)\}/g, (match, name) =>
    Object.hasOwn(values, name) ? String(values[name]) : match,
  );
}
export function setLanguage(value) {
  if (value === 'fr' || value === 'en') locale.value = value;
}
watch(
  locale,
  (value) => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = value;
      document.title =
        value === 'en' ? 'SearchMyJob — Career workspace' : 'SearchMyJob — Emploi et missions';
    }
    try {
      localStorage.setItem('smj-language', value);
    } catch {}
  },
  {
    immediate: true,
  },
);
