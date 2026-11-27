<script setup>
import { Grape } from 'lucide-vue-next'
</script>

<template>
  <main class="login">
    <header class="cellar">
      <div class="wordmark"><Grape aria-hidden="true" :size="33" :stroke-width="1.5" /><span>Mosto</span></div>
      <p>Monitor de bodega</p>
    </header>

    <div class="entry">
      <div class="access"><slot /></div>
    </div>
  </main>
</template>

<style scoped>
.login {
  --canvas: #f8f5ef;
  --ink: #30232a;
  --muted: #695d61;
  --wine: #763c51;
  --line: #d8cec6;
  --display: 'Instrument Serif', Georgia, serif;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  min-height: 100vh;
  min-height: 100svh;
  color: var(--ink);
  background: var(--canvas);
}
.cellar {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: clamp(32px, 4.6vw, 90px);
  color: #fff7ee;
  background-color: #32232d;
  background-image: linear-gradient(0deg, rgb(27 20 23 / .88), transparent 46%), url('../assets/sala-de-cubas.webp');
  background-size: cover;
  background-position: center;
}
.wordmark { display: flex; flex-direction: column; align-items: flex-start; gap: 12px; font: 400 clamp(4.4rem, 7.8vw, 8rem)/.88 var(--display); letter-spacing: -.035em; }
.wordmark svg { color: #f2dcdf; }
.cellar p { margin-top: 16px; font-size: 1rem; }
.entry { display: grid; align-items: center; justify-items: center; padding: 46px clamp(32px, 4vw, 96px); }
.access { width: min(100%, 415px); }
.login ::selection { background: #e4cdd5; color: var(--ink); }
@media (max-width: 760px) {
  .login { grid-template-columns: 1fr; align-content: start; }
  .cellar { flex-direction: row; align-items: center; justify-content: space-between; gap: 12px; padding: 16px clamp(18px, 5vw, 32px); background-image: none; }
  .wordmark { flex-direction: row; align-items: center; gap: 8px; font-size: 2.35rem; }
  .wordmark svg { width: 25px; height: 25px; }
  .cellar p { margin: 0; font-size: .84rem; }
  .entry { padding: clamp(32px, 7vh, 68px) clamp(18px, 5vw, 32px); }
}
</style>
