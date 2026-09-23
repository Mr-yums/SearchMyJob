<script setup>
import { toRefs } from 'vue';
import AppIcon from '../../shared/components/AppIcon.vue';
import { tr, locale } from '../../shared/i18n/index.js';
const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
});
const { tab, profile, pages, collapsed, navigate, offers, counts } = toRefs(props.model);
</script>
<template>
  <aside class="app-sidebar">
    <div class="sidebar-top">
      <a class="brand" href="/" aria-label="SearchMyJob"
        ><span class="logo">s<span>.</span></span
        ><span class="brand-text">searchmyjob</span></a
      ><button
        class="sidebar-toggle"
        :aria-label="collapsed ? tr('Déployer la navigation') : tr('Rétracter la navigation')"
        :aria-expanded="!collapsed"
        @click="collapsed = !collapsed"
      >
        <AppIcon name="sliders" :size="18" />
      </button>
    </div>
    <div class="workspace-label">{{ tr('ESPACE DE TRAVAIL') }}</div>
    <nav :aria-label="tr('Navigation principale')">
      <button
        v-for="p in pages"
        :key="p[0]"
        :title="collapsed ? tr(p[2]) : undefined"
        :aria-label="tr(p[2])"
        :class="{ active: tab === p[0] }"
        :aria-current="tab === p[0] ? 'page' : undefined"
        @click="navigate(p[0])"
      >
        <AppIcon :name="p[0]" /><span class="nav-label">{{ tr(p[2]) }}</span
        ><small v-if="p[0] === 'offers' && counts.new">{{ counts.new }}</small>
      </button>
    </nav>
    <div class="sidebar-bottom">
      <a
        class="guide-link"
        :href="locale === 'en' ? '/guide-en.html' : '/guide.html'"
        target="_blank"
        rel="noopener"
        title="Guide"
        ><AppIcon name="documents" :size="17" /><span>Guide</span></a
      ><button class="account" @click="navigate('profile')" :aria-label="tr('Voir mon profil')">
        <span class="user-avatar">T</span
        ><span class="account-label"
          ><strong>{{ tr('Mon espace') }}</strong
          ><small>{{ tr('Mon profil') }}</small></span
        ><AppIcon name="chevron" :size="16" />
      </button>
    </div>
  </aside>
</template>
