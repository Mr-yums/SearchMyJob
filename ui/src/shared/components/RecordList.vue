<script setup>
import { computed, ref, watch } from 'vue';
import { tr } from '../i18n/index.js';
const props = defineProps({
  items: { type: Array, required: true },
  selectedId: { type: String, default: null },
  filters: { type: Array, default: () => [] },
});
const emit = defineEmits(['select']);
const query = ref('');
const filter = ref('');
const page = ref(1);
const rows = ref(null);
const pageSize = 8;
const normalize = (value) =>
  String(value || '')
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLocaleLowerCase();
const filtered = computed(() =>
  props.items.filter(
    (item) =>
      (!filter.value || item.category === filter.value) &&
      normalize(`${item.title} ${item.meta} ${item.search || ''}`).includes(
        normalize(query.value.trim()),
      ),
  ),
);
const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)));
const visible = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize),
);
watch([query, filter], () => {
  page.value = 1;
});
watch(pageCount, (count) => {
  page.value = Math.min(page.value, count);
});
watch([page, query, filter], () => {
  if (rows.value) rows.value.scrollTop = 0;
});
</script>

<template>
  <div class="record-list">
    <input
      v-model="query"
      type="search"
      :aria-label="tr('Rechercher dans la liste')"
      :placeholder="tr('Rechercher dans la liste')"
    />
    <select v-if="filters.length" v-model="filter" :aria-label="tr('Filtrer la liste')">
      <option value="">{{ tr('Tous') }}</option>
      <option v-for="choice in filters" :key="choice.value" :value="choice.value">
        {{ choice.label }}
      </option>
    </select>
    <div ref="rows" class="record-rows">
      <button
        v-for="item in visible"
        :key="item.id"
        type="button"
        class="record-row"
        :aria-pressed="selectedId === item.id"
        :title="item.title + ' · ' + item.meta"
        @click="emit('select', item.id)"
      >
        <strong>{{ item.title }}</strong
        ><span>{{ item.meta }}</span>
      </button>
      <p v-if="!filtered.length" class="small">{{ tr('Aucun résultat') }}</p>
    </div>
    <div class="record-pagination">
      <span role="status"
        >{{ filtered.length ? (page - 1) * pageSize + 1 : 0 }}–{{
          Math.min(page * pageSize, filtered.length)
        }}
        / {{ filtered.length }}</span
      >
      <div class="record-page-controls">
        <button
          type="button"
          class="secondary"
          :disabled="page === 1"
          :aria-label="tr('Page précédente')"
          @click="page--"
        >
          ‹
        </button>
        <select v-model.number="page" :aria-label="tr('Page de la liste')">
          <option v-for="number in pageCount" :key="number" :value="number">
            {{ number }} / {{ pageCount }}
          </option>
        </select>
        <button
          type="button"
          class="secondary"
          :disabled="page >= pageCount"
          :aria-label="tr('Page suivante')"
          @click="page++"
        >
          ›
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.record-list {
  display: grid;
  gap: 10px;
  min-width: 0;
}
.record-list input,
.record-list select {
  width: 100%;
  min-width: 0;
  margin: 0;
}
.record-rows {
  order: 1;
  max-height: clamp(240px, 52dvh, 520px);
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}
.record-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
  min-width: 0;
  padding: 12px;
  text-align: left;
  border: 0;
  border-bottom: 1px solid var(--line-soft);
  border-radius: 0;
  background: transparent;
  color: var(--ink);
}
.record-row:last-child {
  border-bottom: 0;
}
.record-row:hover {
  background: var(--surface-2);
}
.record-row[aria-pressed='true'] {
  background: var(--accent-soft);
  box-shadow: inset 3px 0 var(--accent);
}
.record-row strong,
.record-row span {
  display: block;
  width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.record-row strong {
  font-size: 13px;
  font-weight: 600;
}
.record-row span {
  font-size: 11px;
  color: var(--muted);
}
.record-rows > p {
  padding: 14px;
}
.record-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}
.record-page-controls {
  display: flex;
  gap: 5px;
  align-items: center;
}
.record-page-controls button {
  padding: 6px 10px;
}
.record-page-controls select {
  width: auto;
  padding: 6px;
}
</style>
