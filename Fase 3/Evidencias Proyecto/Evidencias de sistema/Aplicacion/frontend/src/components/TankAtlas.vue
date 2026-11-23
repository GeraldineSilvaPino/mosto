<script setup>
import { computed, ref, watch } from 'vue'
import TankSilhouette from './TankSilhouette.vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps({ cubas: { type: Array, required: true } })
const page = ref(0)
const pageSize = 4
const pageCount = computed(() => Math.ceil(props.cubas.length / pageSize))
const visible = computed(() => props.cubas.slice(page.value * pageSize, (page.value + 1) * pageSize))
watch(() => props.cubas.map(c => c.id).join(','), () => { page.value = 0 })
</script>

<template>
  <section class="atlas" aria-labelledby="atlas-title">
    <header>
      <h2 id="atlas-title">Atlas de fermentación</h2>
      <div v-if="pageCount > 1" class="pager">
        <button type="button" aria-label="Cubas anteriores" :disabled="page === 0" @click="page--"><ChevronLeft :size="16" /></button>
        <span>{{ page + 1 }} / {{ pageCount }}</span>
        <button type="button" aria-label="Cubas siguientes" :disabled="page + 1 >= pageCount" @click="page++"><ChevronRight :size="16" /></button>
      </div>
    </header>
    <div class="vessels">
      <RouterLink v-for="c in visible" :key="c.id" :to="{name: 'CubaDetailParam', params: { id: c.id }}" class="vessel"
        :aria-label="[c.codigo, c.estadoLabel, c.temperaturaTexto, c.llenado == null ? 'Nivel sin datos' : c.llenado + '% de capacidad'].join(', ')"
        :title="[c.codigo, c.estadoLabel, c.volumen != null && c.capacidad > 0 ? c.volumen.toLocaleString('es-CL') + ' de ' + c.capacidad.toLocaleString('es-CL') + ' L' : 'Nivel sin datos'].join(' · ')">
        <span class="vessel-head"><i :class="c.estado"></i>{{ c.codigo }}</span>
        <TankSilhouette :id="c.id" :nivel="c.llenado" />
        <strong>{{ c.temperaturaTexto }}</strong>
        <span class="volume">{{ c.llenado == null ? 'Nivel sin datos' : c.llenado + '% de capacidad' }}</span>
      </RouterLink>
    </div>
    <div class="legend" aria-label="Estados térmicos">
      <span><i class="normal"></i>Normal</span><span><i class="advertencia"></i>Advertencia</span>
      <span><i class="critico"></i>Crítico</span><span><i class="sin_datos"></i>Sin diagnóstico</span>
    </div>
  </section>
</template>

<style scoped>
.atlas { color: #fff5ee; background: #32232d; border-radius: 14px; padding: 22px 24px 15px; min-width: 0; }
header, .pager, .legend, .legend span, .vessel-head { display: flex; align-items: center; }
header { justify-content: space-between; gap: 8px; }
h2 { font: 400 1.95rem/1.1 var(--atlas-display); }
.pager { gap: 3px; color: #e8cfcf; font-size: .75rem; white-space: nowrap; }
.pager button { width: 27px; height: 32px; color: inherit; display: grid; place-items: center; }
.pager button:disabled { opacity: .35; cursor: default; }
.vessels { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 21px 0 17px; }
.vessel { min-width: 0; display: flex; flex-direction: column; align-items: center; padding: 4px 5px; border-radius: 5px; }
.vessel:hover { background-color: #49303e; }
.atlas :focus-visible { outline: 2px solid #ffd0a6; outline-offset: 1px; }
.vessel-head { gap: 6px; font-size: .76rem; font-weight: 650; overflow-wrap: anywhere; }
.atlas i { display: inline-block; width: 9px; height: 9px; flex-shrink: 0; }
.normal { background: #a8cca5; border-radius: 50%; }
.advertencia { background: #f5c078; clip-path: polygon(50% 0,100% 100%,0 100%); }
.critico { background: #ff828b; clip-path: polygon(50% 0,100% 50%,50% 100%,0 50%); }
.sin_datos { border: 1px solid #c6afbd; }
.vessel :deep(svg) { width: 100%; max-width: 120px; height: 130px; }
.vessel strong { font-size: 1.05rem; font-variant-numeric: tabular-nums; }
.volume { color: #ddc3cb; font-size: .75rem; text-align: center; }
.legend { gap: 7px 14px; border-top: 1px solid #644854; padding-top: 12px; color: #e6d1d6; flex-wrap: wrap; }
.legend span { gap: 5px; font-size: .73rem; }
@media(max-width:650px) {
  .atlas { padding: 16px; }
  h2 { font-size: 1.55rem; }
  .vessels { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 4px; }
  .vessel :deep(svg) { height: 110px; }
}
</style>
