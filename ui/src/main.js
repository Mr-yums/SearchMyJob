import { createApp } from 'vue';
import App from './app/App.vue';
import './shared/styles/index.css';
try {
  const theme = localStorage.getItem('smj-theme');
  if (['searchmyjob', 'sombre'].includes(theme)) document.documentElement.dataset.theme = theme;
} catch {}
createApp(App).mount('#app');
