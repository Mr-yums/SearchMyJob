<script setup>
import { computed, onMounted, ref } from 'vue';
import { intlLocale, tr } from '../i18n/index.js';
defineProps({ modelValue: { type: String, default: '' } });
const emit = defineEmits(['update:modelValue']);
const countries = ref(['fr', 'de', 'be', 'it']);
const error = ref(false);
onMounted(async () => {
  try {
    const response = await fetch('/api/search/options');
    if (!response.ok) throw Error();
    const data = await response.json();
    if (!Array.isArray(data.countries)) throw Error();
    countries.value = data.countries;
  } catch {
    error.value = true;
  }
});
const options = computed(() => {
  const names = new Intl.DisplayNames([intlLocale.value], { type: 'region' });
  return countries.value
    .map((code) => ({ code, name: names.of(code.toUpperCase()) }))
    .sort((a, b) => a.name.localeCompare(b.name, intlLocale.value));
});
</script>
<template>
  <label
    >{{ tr('Pays de recherche') }}
    <select
      :aria-label="tr('Pays de recherche')"
      :value="modelValue"
      required
      @change="emit('update:modelValue', $event.target.value)"
    >
      <option disabled value="">{{ tr('Choisis un pays') }}</option>
      <option v-for="country in options" :key="country.code" :value="country.code">
        {{ country.name }}
      </option>
    </select>
  </label>
  <p v-if="error" role="status">
    {{ tr('Liste des pays indisponible : recharge la page pour afficher tous les pays.') }}
  </p>
</template>
