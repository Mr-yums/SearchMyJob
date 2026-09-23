<script setup>
import { tr } from '../../../shared/i18n/index.js';
import { ref, watch } from 'vue';
const props = defineProps({
  conversations: {
    type: Array,
    default: () => [],
  },
  current: String,
  busy: Boolean,
  loading: Boolean,
});
const emit = defineEmits(['select', 'create', 'rename', 'reset']);
const editing = ref(false),
  title = ref('');
watch(
  () => props.current,
  () => {
    editing.value = false;
  },
);
function rename() {
  title.value = props.conversations.find((c) => c.id === props.current)?.title || '';
  editing.value = true;
}
</script>
<template>
  <div class="conversation-bar">
    <label class="conversation-picker"
      >{{ tr('Mes conversations')
      }}<select
        :aria-label="tr('Choisir une conversation')"
        :value="current"
        @change="emit('select', $event.target.value)"
      >
        <option v-for="c in conversations" :key="c.id" :value="c.id">
          {{ c.archived ? tr('Archive · ') : '' }}{{ c.title }}
        </option>
      </select></label
    >
    <div class="conversation-actions">
      <button type="button" :disabled="loading" @click="emit('create')">
        {{ tr('＋ Nouveau chat') }}</button
      ><button type="button" class="secondary" @click="rename">
        {{ tr('Renommer') }}</button
      ><button
        type="button"
        class="secondary"
        :disabled="busy || loading || !!conversations.find((c) => c.id === current)?.archived"
        @click="emit('reset')"
        :title="tr('Repartir à zéro et conserver ce fil dans les archives')"
      >
        {{ tr('Réinitialiser') }}
      </button>
    </div>
    <form
      v-if="editing"
      class="rename-form"
      @submit.prevent="
        emit('rename', title.trim());
        editing = false;
      "
    >
      <input
        :aria-label="tr('Nom de la conversation')"
        v-model="title"
        maxlength="100"
        required
      /><button :disabled="!title.trim()">{{ tr('Enregistrer') }}</button
      ><button type="button" class="secondary" @click="editing = false">
        {{ tr('Annuler') }}
      </button>
    </form>
  </div>
</template>
<style scoped>
.conversation-bar {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border, #e6e0ef);
}
.conversation-picker {
  flex: 1;
  min-width: 160px;
  max-width: 100%;
  font-size: 12px;
}
.conversation-picker select {
  display: block;
  width: 100%;
  margin-top: 6px;
  text-overflow: ellipsis;
}
.conversation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.conversation-actions button {
  font-size: 12px;
  padding: 9px 12px;
}
.rename-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}
.rename-form input {
  flex: 1;
  min-width: 140px;
  max-width: 100%;
}
@media (max-width: 600px) {
  .conversation-bar {
    padding: 12px;
  }
  .conversation-picker {
    flex-basis: 100%;
  }
}
</style>
