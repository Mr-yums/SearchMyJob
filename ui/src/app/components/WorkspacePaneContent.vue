<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps({ page: { type: String, required: true } });
const emit = defineEmits(['settled']);
const stage = ref(null);
const content = ref(null);
let generation = 0;
let ghost = null;
let animations = [];

function clearMotion() {
  for (const animation of animations) animation.cancel();
  animations = [];
  ghost?.remove();
  ghost = null;
}

watch(
  () => props.page,
  async (page, previous) => {
    const current = ++generation;
    clearMotion();
    const outgoing = content.value;
    const animate =
      outgoing &&
      (page === 'conversation' || previous === 'conversation') &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const bounds = animate ? outgoing.getBoundingClientRect() : null;
    // Only the current page stays live. The outgoing card is an inert visual snapshot.
    const snapshot = animate ? outgoing.cloneNode(true) : null;
    const offsets = animate
      ? [outgoing, ...outgoing.querySelectorAll('*')].map((element) => ({
          top: element.scrollTop,
          left: element.scrollLeft,
          value: element.value,
          checked: element.checked,
        }))
      : [];
    if (snapshot) {
      snapshot.inert = true;
      snapshot.setAttribute('aria-hidden', 'true');
      for (const element of [snapshot, ...snapshot.querySelectorAll('[id]')])
        element.removeAttribute('id');
    }
    await nextTick();
    if (current !== generation || !content.value) return;
    // Position the new conversation before animating it, so messages do not jump at the end.
    emit('settled');
    await nextTick();
    if (current !== generation || !content.value || !snapshot) return;
    const destination = stage.value.getBoundingClientRect();
    ghost = snapshot;
    snapshot.classList.add('pane-snapshot');
    Object.assign(snapshot.style, {
      position: 'absolute',
      width: `${bounds.width}px`,
      height: `${bounds.height}px`,
      left: `${bounds.left - destination.left}px`,
      top: `${bounds.top - destination.top}px`,
      pointerEvents: 'none',
      zIndex: '2',
      margin: '0',
    });
    stage.value.append(snapshot);
    // Restore scroll offsets after attachment (detached elements cannot retain scrolling).
    const copies = [snapshot, ...snapshot.querySelectorAll('*')];
    offsets.forEach(({ top, left, value, checked }, index) => {
      copies[index].scrollTop = top;
      copies[index].scrollLeft = left;
      if (value !== undefined && copies[index].type !== 'file') copies[index].value = value;
      if (checked !== undefined) copies[index].checked = checked;
    });
    const direction = previous === 'conversation' ? 1 : -1;
    const travel = Math.min(56, destination.height * 0.08) * direction;
    const easing = 'cubic-bezier(0.22, 0.61, 0.36, 1)';
    animations = [
      ...Array.from(snapshot.children).map((element) =>
        element.animate([{ opacity: 1 }, { opacity: 0 }], {
          duration: 100,
          easing: 'ease-out',
          fill: 'both',
        }),
      ),
      snapshot.animate(
        [
          { transform: 'perspective(1800px) translate3d(0, 0, 0) rotateX(0)', opacity: 1 },
          {
            transform: `perspective(1800px) translate3d(0, ${travel}px, -100px) rotateX(${-7 * direction}deg) scale(0.98)`,
            opacity: 0,
          },
        ],
        { duration: 280, easing, fill: 'both' },
      ),
      content.value.animate(
        [
          {
            transform: `perspective(1800px) translate3d(0, ${-travel * 0.55}px, -90px) rotateX(${5 * direction}deg) scale(0.985)`,
            opacity: 0,
          },
          { transform: 'perspective(1800px) translate3d(0, 0, 0) rotateX(0)', opacity: 1 },
        ],
        { duration: 280, delay: 80, easing, fill: 'both' },
      ),
    ];
    await Promise.allSettled(animations.map((animation) => animation.finished));
    if (current === generation) clearMotion();
  },
);

onBeforeUnmount(() => {
  generation++;
  clearMotion();
});
</script>

<template>
  <div ref="stage" class="pane-stage">
    <div :key="page" ref="content" class="pane-content"><slot /></div>
  </div>
</template>

<style scoped>
.pane-stage {
  position: relative;
  height: 100%;
  min-height: 0;
  min-width: 0;
  flex: 1;
  isolation: isolate;
  overflow: hidden;
}
.pane-stage > .pane-content {
  height: 100%;
  min-height: 0;
  min-width: 0;
  background: var(--bg);
  transform-origin: center center;
}
.pane-stage > .pane-content > :deep(section) {
  animation: none;
}
.pane-stage > :deep(.pane-snapshot) {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(var(--shadow-rgb), 0.09);
}
</style>
