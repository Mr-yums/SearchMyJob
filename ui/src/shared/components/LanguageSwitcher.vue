<script setup>
import { locale, setLanguage } from '../i18n/index.js';
</script>
<template>
  <label class="language-switcher"
    ><span aria-hidden="true">◎</span
    ><select
      aria-label="Langue / Language"
      :value="locale"
      @change="setLanguage($event.target.value)"
    >
      <option value="fr" lang="fr">Français</option>
      <option value="en" lang="en">English</option>
    </select></label
  >
</template>
<style scoped>
.language-switcher {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  flex-shrink: 0;
  color: var(--ink);
  font-size: 12px;
}
.language-switcher select {
  width: auto;
  max-width: 130px;
  margin: 0;
  padding: 7px 8px;
  border: 1px solid var(--line, #ddd);
  border-radius: 8px;
  background: var(--surface, #fff);
  color: inherit;
  font: inherit;
}
.language-switcher select:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
