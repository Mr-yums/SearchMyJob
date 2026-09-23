<script setup>
import { tr, intlLocale } from '../../../shared/i18n/index.js';
import { ref, onMounted } from 'vue';
const monthly = ref(null),
  monthlyError = ref('');
onMounted(async () => {
  try {
    const r = await fetch('/api/bright/usage');
    if (!r.ok) throw Error();
    monthly.value = await r.json();
  } catch {
    monthlyError.value = tr('Consommation mensuelle indisponible pour le moment.');
  }
});
const month = (value) =>
  new Date(value + 'T12:00:00Z').toLocaleDateString(intlLocale.value, {
    month: 'long',
    year: 'numeric',
  });
const renewal = (value) =>
  new Date(value + 'T12:00:00Z').toLocaleDateString(intlLocale.value, {
    day: 'numeric',
    month: 'long',
  });
defineProps({
  budget: Object,
  usage: Object,
});
const number = (value) =>
  typeof value === 'number' ? value.toLocaleString(intlLocale.value) : '—';
const day = (value) => new Date(value * 1000).toLocaleDateString(intlLocale.value);
</script>
<template>
  <section class="settings-usage" :aria-label="tr('Consommation de l’espace')">
    <span class="prefs-label">{{ tr('Consommation') }}</span>
    <div class="usage-block monthly-bright">
      <div class="usage-title">
        <strong>{{ tr('MCP Bright Data') }}</strong
        ><span class="usage-period">{{ tr('Compte personnel') }}</span>
      </div>
      <p class="usage-value">
        Quota <span>{{ tr('selon ton offre') }}</span>
      </p>
      <small>{{
        tr('Consulte ton tableau de bord fournisseur pour connaître tes crédits et tarifs.')
      }}</small>
      <div v-if="monthly?.status === 'ok'" class="monthly-stat">
        <strong>{{ number(monthly.used) }}</strong
        ><span
          >{{ tr('recherches MCP comptabilisées') }}<br />{{ tr('en ')
          }}{{ month(monthly.period_start) }}</span
        >
      </div>
      <small v-else role="status">{{
        monthlyError || monthly?.message || tr('Lecture des statistiques Bright Data…')
      }}</small>
      <small v-if="monthly?.status === 'ok'"
        >{{ tr('Source : Bright Data · zone MCP · vérifié à ')
        }}{{
          new Date(monthly.checked_at * 1000).toLocaleTimeString(intlLocale, {
            hour: '2-digit',
            minute: '2-digit',
          })
        }}{{ tr('. Actualisation au plus toutes les 15 minutes.') }}</small
      >
      <div class="monthly-balance">
        <span>{{ tr('Solde global de crédits') }}</span
        ><strong>{{ tr('À consulter sur Bright Data') }}</strong
        ><small>{{ tr('Les statistiques MCP ne donnent pas le solde partagé du compte.') }}</small
        ><a href="https://brightdata.com/cp/billing/overview" target="_blank" rel="noopener">{{
          tr('Voir mon solde Bright Data ↗')
        }}</a>
      </div>
      <small v-if="monthly?.renews_at"
        >{{ tr('Prochaine période indiquée : ') }}{{ renewal(monthly.renews_at) }}.</small
      >
      <details class="local-bright">
        <summary>
          {{ tr('Limite locale SearchMyJob · ')
          }}{{
            budget?.used == null
              ? tr('indisponible')
              : number(budget.used) + ' / ' + number(budget.limit)
          }}
        </summary>
        <small
          >{{
            budget?.used == null
              ? tr('Compteur local indisponible.')
              : number(budget.remaining) + tr(' appels restants avant l’arrêt local.')
          }}{{ tr(' Cette limite est indépendante du quota mensuel Bright Data.') }}</small
        ><span v-if="budget?.blocked" class="usage-warning">{{ tr('Appels locaux bloqués') }}</span>
      </details>
    </div>
    <div class="usage-block">
      <div class="usage-title">
        <strong>{{ tr('Tokens utilisés') }}</strong
        ><span v-if="usage?.partial" class="usage-warning">{{ tr('Total partiel') }}</span>
      </div>
      <p class="usage-value">
        {{ number(usage?.total_tokens) }}
        <span>{{
          usage?.total_tokens == null ? tr('en attente de mesure') : tr('tokens mesurés')
        }}</span>
      </p>
      <div class="usage-agent" v-for="name in ['deepseek', 'kimi', 'claude', 'openai']" :key="name">
        <span>{{
          {
            deepseek: 'DeepSeek',
            kimi: 'Kimi',
            claude: 'Claude',
            openai: 'OpenAI',
          }[name]
        }}</span
        ><strong>{{
          usage?.providers?.[name]?.total_tokens == null
            ? tr('Non disponible')
            : number(usage.providers[name].total_tokens)
        }}</strong>
      </div>
      <details v-if="usage?.measured_calls">
        <summary>{{ tr('Détail des tokens') }}</summary>
        <dl
          v-for="name in ['deepseek', 'kimi', 'claude', 'openai'].filter(
            (n) => usage.providers?.[n]?.measured_calls,
          )"
          :key="name"
        >
          <dt>
            {{
              {
                deepseek: 'DeepSeek',
                kimi: 'Kimi',
                claude: 'Claude',
                openai: 'OpenAI',
              }[name]
            }}{{ tr(' · entrée') }}
          </dt>
          <dd>{{ number(usage.providers[name].input_tokens) }}</dd>
          <dt>{{ tr('Dont cache') }}</dt>
          <dd>{{ number(usage.providers[name].cached_input_tokens) }}</dd>
          <dt>{{ tr('Sortie') }}</dt>
          <dd>{{ number(usage.providers[name].output_tokens) }}</dd>
        </dl>
      </details>
      <small v-if="usage?.since"
        >{{ tr('Suivi depuis le ') }}{{ day(usage.since)
        }}{{ tr(' · SearchMyJob uniquement. Historique antérieur non comptabilisé.') }}</small
      >
      <small v-else>{{ tr('Chargement du suivi des tokens…') }}</small>
      <small v-if="usage?.missing_calls"
        >{{ number(usage.missing_calls) }}{{ tr(' appel(s) sans mesure.') }}</small
      >
      <small>{{
        tr(
          'Les tokens sont comptés lorsque le fournisseur les communique. Ce suivi ne représente ni ton solde ni une facture.',
        )
      }}</small>
    </div>
  </section>
</template>
<style scoped>
.settings-usage {
  border-top: 1px solid var(--line);
  padding-top: 10px;
  margin-top: 5px;
  min-width: 0;
}
.settings-usage > .prefs-label {
  display: block;
  margin-bottom: 9px;
}
.usage-block {
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
  border-radius: 9px;
  padding: 12px;
  margin-top: 8px;
}
.usage-title,
.usage-agent {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: var(--ink);
}
.usage-title strong {
  font-weight: 600;
}
.usage-warning {
  color: var(--warn-text);
  background: var(--warn-bg);
  font-size: 9px;
  padding: 3px 6px;
  border-radius: 5px;
}
.usage-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--accent-text);
  margin: 11px 0 8px;
  line-height: 1.3;
}
.usage-value span {
  font-size: 11px;
  font-weight: 400;
  color: var(--muted);
}
.usage-block small {
  display: block;
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
  margin-top: 7px;
}
.usage-block progress {
  width: 100%;
  height: 5px;
  appearance: none;
  border: 0;
  border-radius: 5px;
  overflow: hidden;
  background: var(--line);
}
.usage-block progress::-webkit-progress-bar {
  background: var(--line);
}
.usage-block progress::-webkit-progress-value {
  background: var(--accent);
}
.usage-block progress::-moz-progress-bar {
  background: var(--accent);
}
.usage-agent {
  padding: 6px 0;
  border-bottom: 1px solid var(--line-soft);
}
.usage-agent strong {
  font-size: 11px;
  font-weight: 500;
}
.usage-block details {
  font-size: 10px;
  color: var(--muted);
  margin-top: 9px;
}
.usage-block summary {
  cursor: pointer;
}
.usage-block dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 5px;
}
.usage-block dd {
  margin: 0;
  text-align: right;
}
.usage-period {
  font-size: 9px;
  color: var(--accent-text);
}
.monthly-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0 4px;
}
.monthly-stat > strong {
  font-size: 21px;
  color: var(--ink);
}
.monthly-stat > span {
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
}
.monthly-balance {
  border-top: 1px solid var(--line);
  margin-top: 12px;
  padding-top: 12px;
  font-size: 10px;
}
.monthly-balance > span,
.monthly-balance > strong {
  display: block;
  margin-bottom: 5px;
}
.monthly-balance > strong {
  font-weight: 500;
  color: var(--ink);
}
.monthly-balance a {
  display: inline-block;
  margin-top: 9px;
  font-size: 11px;
  color: var(--accent-text);
}
.local-bright {
  border-top: 1px solid var(--line);
  padding-top: 10px;
}
.local-bright .usage-warning {
  display: inline-block;
  margin-top: 7px;
}
</style>
