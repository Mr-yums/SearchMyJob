<script setup>
// [Sol] Consistent, accessible UI pictograms; no external assets.
defineProps({
  name: String,
  size: {
    type: Number,
    default: 20,
  },
});
const paths = {
  menu: 'M4 7h16 M4 12h16 M4 17h16',
  mail: 'M3 6h18v12H3V6Z m0 1 9 6 9-6',
  conversation: 'M4 4h16v12H9l-5 4V4Z M8 8h8 M8 12h5',
  offers: 'M9 5V3h6v2 M3 7h18v13H3V7Z M3 12c6 3 12 3 18 0 M10 12h4v3h-4z',
  documents: 'M6 3h8l4 4v14H6V3Z M14 3v5h4 M9 12h6 M9 16h6',
  profile: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2',
  heartbeat: 'M3 12h4l3-8 4 16 3-8h4',
  connections: 'M8 3v5 M16 3v5 M6 8h12v3a6 6 0 0 1-12 0V8Z M12 17v4',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
  globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c-5 5-5 13 0 18 M12 3c5 5 5 13 0 18',
  check: 'm5 12 4 4L19 6',
  close: 'm6 6 12 12 M18 6 6 18',
  search: 'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0 M15 15l6 6',
  edit: 'm16 3 5 5-12 12-6 1 1-6L16 3Z M13 6l5 5',
  sliders: 'M4 7h8 M16 7h4 M4 17h3 M11 17h9 M12 4v6 M7 14v6',
  send: 'm4 12 8-8 8 8 M12 4v16',
  chevron: 'm9 5 7 7-7 7',
  clock: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l3 2',
};
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.spark" />
  </svg>
</template>
