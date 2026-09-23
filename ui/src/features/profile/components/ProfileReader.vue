<script setup>
import { tr, intlLocale } from '../../../shared/i18n/index.js';

// [Sol] Readable sections derived only from the saved profile, no invented facts.
// [OXIO 15/09/2026] Lecture en deux colonnes : index fixe à gauche (sélecteur + liste), sections à droite en cartes.
import { computed, ref } from 'vue';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { prettyTitle as pretty } from '../../../shared/utils/titles.js';
const props = defineProps({
  text: {
    type: String,
    default: '',
  },
});
const active = ref('all');
const sections = computed(() => {
  const result = [];
  let current = {
    title: tr('Présentation générale'),
    lines: [],
  };
  for (const line of props.text.split('\n')) {
    const t = line.trim();
    const heading =
      t.length > 3 &&
      t.length < 130 &&
      ((t === t.toLocaleUpperCase('fr') && /[A-ZÀ-Ÿ]/.test(t) && !t.startsWith('•')) ||
        /^\d+\. /.test(t));
    if (heading) {
      if (current.lines.length) result.push(current);
      current = {
        title: t,
        lines: [],
      };
    } else if (t) current.lines.push(t);
  }
  if (current.lines.length) result.push(current);
  return result;
});
const shown = computed(() =>
  active.value === 'all' ? sections.value : sections.value.filter((s) => s.title === active.value),
);
const wordCount = computed(() => props.text.split(/\s+/).filter(Boolean).length);
</script>
<template>
  <div class="profile-reader">
    <aside class="reader-index">
      <label
        >{{ tr('Parcourir le profil')
        }}<select v-model="active">
          <option value="all">{{ tr('Tout le parcours') }}</option>
          <option v-for="s in sections" :key="s.title">{{ s.title }}</option>
        </select></label
      >
      <div class="reader-list" role="navigation" :aria-label="tr('Sections du profil')">
        <button type="button" :class="{ active: active === 'all' }" @click="active = 'all'">
          <span class="section-marker">••</span><span>{{ tr('Tout le parcours') }}</span>
        </button>
        <button
          type="button"
          v-for="(s, i) in sections"
          :key="s.title"
          :class="{ active: active === s.title }"
          :title="s.title"
          @click="active = s.title"
        >
          <span class="section-marker">{{ String(i + 1).padStart(2, '0') }}</span
          ><span>{{ pretty(s.title) }}</span>
        </button>
      </div>
      <span
        >{{ sections.length }}{{ tr(' sections · ') }}{{ wordCount.toLocaleString(intlLocale)
        }}{{ tr(' mots · profil enregistré') }}</span
      >
    </aside>
    <div class="reader-body">
      <section v-for="s in shown" :key="s.title" class="profile-section">
        <div class="profile-section-title">
          <span class="section-marker">{{ String(sections.indexOf(s) + 1).padStart(2, '0') }}</span>
          <h3 :title="s.title">{{ pretty(s.title) }}</h3>
        </div>
        <div class="profile-section-content">
          <p
            v-for="(line, n) in s.lines"
            :key="n"
            :class="{ 'profile-bullet': line.startsWith('•') }"
          >
            <AppIcon v-if="line.startsWith('•')" name="check" :size="15" />{{
              line.replace(/^•\s*/, '')
            }}
          </p>
        </div>
      </section>
    </div>
  </div>
</template>
