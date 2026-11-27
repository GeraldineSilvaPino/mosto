<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, ArrowRight, ArrowUpRight, Check, ChevronRight, Cylinder, Droplets, LayoutGrid, ListFilter, RefreshCw, Thermometer, TriangleAlert } from 'lucide-vue-next'
import TankAtlas from '../components/TankAtlas.vue'
import cubaService from '../services/cubaService'

const route = useRoute()
const router = useRouter()
const activeTab = ref('overview')
const cubas = ref([])
const busy = ref(false)
const error = ref('')
const lastSync = ref(null)
const variety = ref('')
const status = ref('')
const onlyRisk = ref(false)
let pollInterval

const tabs = [
  { id: 'overview', label: 'Resumen' },
  { id: 'health', label: 'Estado térmico' },
  { id: 'comparison', label: 'Comparar lotes' },
  { id: 'grid', label: 'Cubas' }
]
const estados = {
  critico: { label: 'Crítico', order: 0 }, advertencia: { label: 'Advertencia', order: 1 },
  normal: { label: 'Normal', order: 2 }, sin_datos: { label: 'Sin diagnóstico', order: 3 }
}
const decimal = new Intl.NumberFormat('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const litros = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 })
const hora = new Intl.DateTimeFormat('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const numero = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value)
const medida = (n, unit) => n == null ? '—' : decimal.format(n) + ' ' + unit

function mapearCuba(item, previa) {
  const temperatura = numero(item.ultima_temperatura)
  const tempMin = numero(item.temp_min_perfil)
  const tempMax = numero(item.temp_max_perfil)
  const volumen = numero(item.volumen_actual_lts)
  const capacidad = numero(item.capacidad_lts)
  const enUso = item.estado_operativo === 'en_uso'
  let estado = 'sin_datos'
  let diagnostico = 'Pendiente de lectura o perfil'
  if (temperatura != null && tempMin != null && tempMax != null) {
    const desvio = Math.max(tempMin - temperatura, temperatura - tempMax)
    estado = desvio > 1.5 ? 'critico' : desvio > 0 ? 'advertencia' : 'normal'
    diagnostico = desvio <= 0 ? 'Dentro del perfil' : temperatura > tempMax
      ? 'Sobre el máximo de ' + medida(tempMax, '°C') : 'Bajo el mínimo de ' + medida(tempMin, '°C')
  }
  const diferencia = temperatura != null && previa?.temperatura != null ? temperatura - previa.temperatura : 0
  return {
    id: item.id, codigo: item.codigo_cuba || 'Cuba ' + item.id, variedad: item.variedad || '', lote: item.lote || '',
    temperatura, temperaturaTexto: medida(temperatura, '°C'), tempMin, tempMax, brix: numero(item.ultimos_brix),
    volumen, capacidad, llenado: volumen != null && volumen >= 0 && capacidad > 0 ? Math.round(100 * volumen / capacidad) : null,
    estado, estadoLabel: estados[estado].label, diagnostico, enUso,
    fase: enUso ? 'En fermentación' : item.estado_operativo === 'disponible' ? 'Disponible' : item.estado_operativo || 'Sin estado',
    dia: item.dia_fermentacion, prediccion: item.prediccion_ml,
    tendencia: diferencia > .05 ? 'En alza' : diferencia < -.05 ? 'En baja' : '',
    lectura: item.ultima_lectura_timestamp
  }
}

async function sincronizar() {
  if (busy.value) return
  busy.value = true
  try {
    const rows = await cubaService.listarCubas({ incluirPrediccion: lastSync.value !== null })
    const anteriores = new Map(cubas.value.map(c => [c.id, c]))
    cubas.value = rows.map(item => mapearCuba(item, anteriores.get(item.id))).sort((a, b) => a.id - b.id)
    lastSync.value = new Date()
    error.value = ''
  } catch (err) {
    error.value = err.message || 'La telemetría no está disponible.'
  } finally {
    busy.value = false
  }
}

const query = computed(() => String(route.query.q || '').trim())
watch(query, value => { if (value) activeTab.value = 'grid' }, { immediate: true })
const variedades = computed(() => [...new Set(cubas.value.map(c => c.variedad).filter(Boolean))].sort())
const enRiesgo = c => c.estado === 'critico' || c.estado === 'advertencia'
const seleccion = computed(() => {
  const q = query.value.toLocaleLowerCase('es')
  return cubas.value.filter(c =>
    (!variety.value || c.variedad === variety.value) && (!status.value || c.estado === status.value) &&
    (!onlyRisk.value || enRiesgo(c)) && (!q || [c.codigo, c.variedad, c.lote].some(s => s.toLocaleLowerCase('es').includes(q))))
})
const porPrioridad = computed(() => [...seleccion.value].sort((a, b) => estados[a.estado].order - estados[b.estado].order || a.id - b.id))
const riesgos = computed(() => porPrioridad.value.filter(enRiesgo))
const metricas = computed(() => {
  const lecturas = seleccion.value.map(c => c.temperatura).filter(t => t != null)
  const evaluadas = seleccion.value.filter(c => c.estado !== 'sin_datos').length
  return {
    promedio: lecturas.length ? decimal.format(lecturas.reduce((a, b) => a + b, 0) / lecturas.length) : '—',
    activas: seleccion.value.filter(c => c.enUso).length,
    criticas: riesgos.value.filter(c => c.estado === 'critico').length,
    evaluadas,
    dentro: evaluadas ? Math.round(100 * (evaluadas - riesgos.value.length) / evaluadas) : null
  }
})
const filtrosActivos = computed(() => Boolean(query.value || variety.value || status.value || onlyRisk.value))
const escalaBrix = computed(() => Math.max(25, ...seleccion.value.map(c => c.brix ?? 0)))
function limpiarFiltros() {
  variety.value = status.value = ''
  onlyRisk.value = false
  if (query.value) {
    const { q, ...resto } = route.query
    router.replace({ path: route.path, query: resto })
  }
}
function prediccionTexto(pred) {
  if (!pred?.estado_ia) return ''
  const riesgo = numero(pred.riesgo_pct)
  switch (pred.estado_ia) {
    case 'CRITICO': case 'ADVERTENCIA': case 'NORMAL':
      return riesgo == null ? 'Riesgo pendiente' : 'Riesgo estimado de parada · ' + Math.round(riesgo) + '%'
    case 'NO_VALIDADO': return 'Sin modelo validado'
    case 'FINALIZADA': return 'Brix en tramo final'
    default: return 'Modelo en calibración'
  }
}
function horaLectura(valor) {
  const date = new Date(valor)
  return valor && Number.isFinite(date.getTime()) ? date.toLocaleString('es-CL') : 'Sin lectura'
}
onMounted(() => {
  sincronizar()
  pollInterval = setInterval(sincronizar, 5000)
})
onBeforeUnmount(() => clearInterval(pollInterval))
</script>

<template>
  <div class="dashboard">
    <header class="page-head">
      <div>
        <h1>Monitor de bodega</h1>
        <p v-if="lastSync">{{ cubas.length }} {{ cubas.length === 1 ? 'cuba registrada' : 'cubas registradas' }} · Última sincronización {{ hora.format(lastSync) }}</p>
      </div>
      <button type="button" class="sync" :disabled="busy" @click="sincronizar"><RefreshCw :size="15" :class="{turning: busy}" />{{ busy ? 'Sincronizando…' : 'Sincronizar' }}</button>
    </header>
    <nav class="views" aria-label="Vistas del monitor">
      <button v-for="tab in tabs" :key="tab.id" type="button" :class="{chosen: activeTab === tab.id}" :aria-current="activeTab === tab.id ? 'page' : undefined" @click="activeTab = tab.id">
        {{ tab.label }}<small v-if="tab.id === 'grid'">{{ seleccion.length }}</small>
      </button>
    </nav>
    <div class="filters">
      <ListFilter :size="17" aria-hidden="true" />
      <select v-model="variety" aria-label="Cepa"><option value="">Todas las cepas</option><option v-for="v in variedades" :key="v">{{ v }}</option></select>
      <select v-model="status" aria-label="Estado"><option value="">Todos los estados</option><option v-for="(e, key) in estados" :key="key" :value="key">{{ e.label }}</option></select>
      <button type="button" role="switch" :aria-checked="onlyRisk" class="risk-switch" @click="onlyRisk = !onlyRisk"><span class="switch-track"></span>Solo en riesgo</button>
      <button v-if="filtrosActivos" type="button" class="clear" @click="limpiarFiltros">Limpiar filtros</button>
      <span v-if="query" class="query">Búsqueda · {{ query }}</span>
    </div>

    <div v-if="error" class="feedback" role="alert"><TriangleAlert :size="19"/><div><strong>Sin conexión con la telemetría</strong><p>{{ lastSync ? 'Mostrando los datos recibidos a las ' + hora.format(lastSync) + '.' : 'Todavía no hay una lectura disponible.' }}</p></div><button @click="sincronizar" :disabled="busy">Reintentar</button></div>
    <div v-if="!lastSync && !error" class="empty" role="status">Cargando telemetría de las cubas…</div>
    <template v-if="lastSync">
      <section v-if="!seleccion.length" class="empty">
        <Cylinder :size="23"/><h2>{{ filtrosActivos ? 'Sin cubas para esta selección' : 'Todavía no hay cubas registradas' }}</h2>
        <button v-if="filtrosActivos" class="clear" @click="limpiarFiltros">Limpiar filtros</button>
      </section>
      <section v-if="activeTab === 'overview'" class="overview">
        <div v-if="seleccion.length" class="priority-row">
          <section class="risk-panel" aria-labelledby="risk-title">
            <div class="section-head"><h2 id="risk-title">Cubas en riesgo</h2><span class="count">{{ riesgos.length }}</span></div>
            <ul v-if="riesgos.length" class="risk-list">
              <li v-for="c in riesgos" :key="c.id"><RouterLink :to="'/cubas/' + c.id" class="risk-link">
                <div class="risk-line"><strong>{{ c.codigo }}</strong><span class="state" :class="c.estado">{{ c.estadoLabel }}</span></div>
                <div class="risk-reading"><b>{{ c.temperaturaTexto }}</b><span>{{ c.diagnostico }}</span></div>
                <ChevronRight class="link-arrow" :size="15"/>
              </RouterLink></li>
            </ul>
            <div v-else class="risk-empty"><component :is="metricas.evaluadas ? Check : Activity" :size="22"/><p>{{ metricas.evaluadas ? 'Sin desvíos en las cubas evaluadas.' : 'La selección aún no tiene diagnóstico térmico.' }}</p></div>
            <button class="panel-foot" @click="activeTab='health'">Ver estado térmico <ArrowRight :size="15"/></button>
          </section>
          <TankAtlas :cubas="seleccion" />
        </div>
        <dl class="metrics" aria-label="Indicadores de las cubas seleccionadas">
          <div><dt><Thermometer/>Temperatura promedio</dt><dd>{{ metricas.promedio }}<small v-if="metricas.promedio !== '—'"> °C</small></dd><p>Cubas con lectura</p></div>
          <div><dt><Cylinder/>En fermentación</dt><dd>{{ metricas.activas }}<small> / {{ seleccion.length }}</small></dd><p>Cubas seleccionadas</p></div>
          <div><dt><TriangleAlert/>Desvíos térmicos</dt><dd>{{ riesgos.length }}</dd><p>{{ metricas.criticas }} {{ metricas.criticas === 1 ? 'cuba crítica' : 'cubas críticas' }}</p></div>
          <div><dt><Activity/>Dentro del rango</dt><dd>{{ metricas.dentro ?? '—' }}<small v-if="metricas.dentro != null"> %</small></dd><p>Con perfil evaluado</p></div>
        </dl>
        <section v-if="seleccion.length" class="register">
          <div class="section-head"><h2>Registro de cubas</h2><button class="text-action" @click="activeTab='grid'">Ver fichas <ArrowUpRight :size="15"/></button></div>
          <div class="table-wrap" tabindex="0" aria-label="Registro de cubas, desplazable">
            <table><thead><tr><th>Cuba</th><th>Cepa / lote</th><th>Temperatura</th><th>Brix</th><th>Estado</th></tr></thead>
              <tbody><tr v-for="c in porPrioridad" :key="c.id">
                <th scope="row"><RouterLink :to="'/cubas/' + c.id">{{ c.codigo }} <ArrowUpRight :size="13"/></RouterLink></th><td>{{ c.variedad || '—' }}<small>{{ c.lote || 'Sin lote' }}</small></td>
                <td>{{ c.temperaturaTexto }}</td><td>{{ medida(c.brix, '°Bx') }}</td>
                <td><span class="state" :class="c.estado">{{ c.estadoLabel }}</span><small v-if="c.prediccion?.riesgo_pct != null">{{ prediccionTexto(c.prediccion) }}</small></td>
              </tr></tbody>
            </table>
          </div>
        </section>
      </section>
      <section v-else-if="activeTab === 'health' && seleccion.length" class="register">
        <div class="section-head"><h2>Estado térmico</h2><Thermometer :size="19"/></div>
        <RouterLink v-for="c in porPrioridad" :key="c.id" :to="'/cubas/' + c.id" class="thermal-row">
          <strong>{{ c.codigo }}</strong><span class="state" :class="c.estado">{{ c.estadoLabel }}</span>
          <span>{{ c.diagnostico }}<small v-if="c.tempMin != null && c.tempMax != null">Perfil · {{ medida(c.tempMin, '°C') }} a {{ medida(c.tempMax, '°C') }}</small></span>
          <b>{{ c.temperaturaTexto }}</b><ChevronRight :size="15"/>
        </RouterLink>
      </section>
      <section v-else-if="activeTab === 'comparison' && seleccion.length" class="register">
        <div class="section-head"><h2>Brix aparente por lote</h2><RouterLink class="text-action" to="/procesos">Curvas históricas <ArrowUpRight :size="15"/></RouterLink></div>
        <RouterLink v-for="c in seleccion" :key="c.id" :to="'/cubas/' + c.id" class="compare-row">
          <span><strong>{{ c.lote || 'Sin lote' }}</strong><small>{{ c.codigo }} · {{ c.variedad || 'Sin cepa' }}</small></span>
          <span class="bar"><i :style="{width: Math.max(0, c.brix ?? 0) * 100 / escalaBrix + '%'}"></i></span><b>{{ medida(c.brix, '°Bx') }}</b><ChevronRight :size="15"/>
        </RouterLink>
      </section>
      <section v-else-if="activeTab === 'grid' && seleccion.length" class="register">
        <div class="section-head"><h2>Fichas de cubas</h2><LayoutGrid :size="18"/></div>
        <div class="sheets"><RouterLink v-for="c in porPrioridad" :key="c.id" :to="'/cubas/' + c.id" class="sheet">
          <div class="sheet-head"><h3>{{ c.codigo }}</h3><span class="state" :class="c.estado">{{ c.estadoLabel }}</span></div>
          <p>{{ c.variedad || 'Sin cepa' }} · {{ c.lote || 'Sin lote' }}</p>
          <p>{{ c.fase }}<template v-if="c.enUso && c.dia"> · Día {{ c.dia }}</template></p>
          <div class="sheet-readings"><span><Thermometer/> {{ c.temperaturaTexto }}</span><span><Droplets/> {{ medida(c.brix,'°Bx') }}</span></div>
          <p>{{ c.diagnostico }}<template v-if="c.tendencia"> · {{ c.tendencia }}</template></p>
          <p v-if="c.tempMin != null && c.tempMax != null">Perfil · {{ medida(c.tempMin, '°C') }} a {{ medida(c.tempMax, '°C') }}</p>
          <p>{{ c.volumen == null ? 'Volumen sin informar' : litros.format(c.volumen) + ' L' }}<template v-if="c.capacidad != null"> · Capacidad {{ litros.format(c.capacidad) }} L</template></p>
          <p v-if="prediccionTexto(c.prediccion)" :title="c.prediccion.mensaje">{{ prediccionTexto(c.prediccion) }}</p>
          <small>{{ horaLectura(c.lectura) }}</small><span class="sheet-foot">Ver telemetría <ArrowUpRight :size="14"/></span>
        </RouterLink></div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.dashboard {
  --atlas-display: 'Instrument Serif', Georgia, serif;
  --ink: #30232a;
  --muted: #695d61;
  --line: #dbd2cc;
  --sheet: #fffdf9;
  --wine: #763c51;
  color: var(--ink);
  max-width: 1540px;
  margin: 0 auto;
  font-variant-numeric: tabular-nums;
}
.page-head, .section-head, .sheet-head, .filters, .views, .sync, .text-action, .risk-switch,
.panel-foot, .risk-line, .risk-reading, .sheet-foot, .sheet-readings { display: flex; align-items: center; }
.page-head, .section-head, .sheet-head, .panel-foot, .sheet-foot { justify-content: space-between; gap: 12px; }
.page-head { margin: 0 0 19px; }
h1, h2, h3 { font-family: var(--atlas-display); font-weight: 400; letter-spacing: -.022em; }
h1 { font-size: 3.25rem; line-height: 1.08; }
h2 { font-size: 1.85rem; line-height: 1.15; }
.page-head p, .metrics p, .query { color: var(--muted); font-size: .77rem; }
.page-head p { margin-top: 6px; }
.sync { gap: 8px; background: var(--wine); color: #fff8f3; border-radius: 7px; padding: 10px 15px; font-weight: 650; font-size: .8rem; min-height: 40px; }
.sync:hover { background: #5e293d; }
.sync:disabled { opacity: .75; }
.views { gap: 20px; border-bottom: 1px solid var(--line); }
.views button { display: inline-flex; align-items: center; gap: 6px; padding: 8px 1px 11px; border-bottom: 2px solid transparent; margin-bottom: -1px; color: var(--muted); font-weight: 600; font-size: .83rem; }
.views button.chosen { color: var(--wine); border-color: var(--wine); }
.views small, .count { font-family: var(--font-sans); font-size: .73rem; padding: 1px 7px; border-radius: 5px; background-color: #ebe2db; }
.filters { gap: 8px; flex-wrap: wrap; margin: 14px 0 19px; color: var(--muted); }
.filters > svg { margin-right: 3px; }
.filters select { max-width: 100%; border: 1px solid var(--line); border-radius: 6px; color: var(--ink); background: var(--sheet); padding: 6px 9px; font-size: .8rem; min-height: 36px; }
.risk-switch { gap: 7px; color: var(--ink); min-height: 36px; font-size: .8rem; margin-left: 5px; }
.switch-track { width: 27px; height: 16px; padding: 2px; border-radius: 10px; background: #85797b; }
.switch-track::before { content: ''; display: block; width: 12px; height: 12px; background: white; border-radius: 50%; transition: transform .15s; }
.risk-switch[aria-checked="true"] .switch-track { background: var(--wine); }
.risk-switch[aria-checked="true"] .switch-track::before { transform: translateX(11px); }
.clear { color: var(--wine); font-size: .8rem; text-decoration: underline; min-height: 36px; padding-inline: 4px; }
.priority-row { display: grid; grid-template-columns: minmax(0,1.8fr) minmax(250px,1fr); gap: 16px; }
.priority-row > .atlas { grid-column: 1; grid-row: 1; }
.priority-row > .risk-panel { grid-column: 2; grid-row: 1; }
.risk-panel { display: flex; flex-direction: column; min-width: 0; border-radius: 14px; background: #f2e8dd; padding: 20px; }
.risk-panel .count { color: #693745; background: #e5d4c9; font-weight: 700; }
.risk-list { list-style: none; padding: 0 3px; margin: 10px -3px 8px; flex: 1; max-height: 190px; overflow: auto; }
.risk-list li + li, .panel-foot { border-top: 1px solid #d9c9bf; }
.risk-link { position: relative; display: block; padding: 11px 17px 11px 0; }
.risk-link:hover strong, .sheet:hover h3, .text-action:hover { text-decoration: underline; }
.risk-line { gap: 10px; justify-content: space-between; margin-bottom: 5px; flex-wrap: wrap; }
.risk-line strong, table th a, .thermal-row strong, .compare-row strong { font-size: .88rem; font-weight: 700; }
.risk-reading { gap: 3px 7px; flex-wrap: wrap; }
.risk-reading b { font-size: .83rem; }
.risk-reading > span { color: var(--muted); font-size: .75rem; }
.link-arrow { position: absolute; right: -2px; top: 50%; transform: translateY(-50%); color: var(--muted); }
.panel-foot, .text-action, .sheet-foot { color: var(--wine); font-size: .79rem; font-weight: 700; }
.panel-foot { margin-top: auto; min-height: 34px; padding-top: 10px; }
.text-action { gap: 5px; min-height: 32px; }
.risk-empty { flex: 1; display: flex; align-items: center; gap: 8px; font-size: .85rem; color: var(--muted); padding: 20px 0; }
.state { display: inline-flex; align-items: center; gap: 5px; border-radius: 5px; padding: 3px 7px; font: 600 .74rem/1.35 var(--font-sans); color: #5e5661; background: #ebe6eb; white-space: nowrap; }
.state::before { content: ''; width: 6px; height: 6px; background: currentColor; border-radius: 50%; }
.state.critico { color: #912c40; background: #f8dce0; }
.state.advertencia { color: #805011; background: #f5e2b6; }
.state.normal { color: #365e40; background: #e2ebda; }
.metrics { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); padding: 20px 0; border-bottom: 1px solid var(--line); margin-bottom: 22px; }
.metrics > div { padding: 0 20px; border-inline-start: 1px solid var(--line); }
.metrics > div:first-child { border: 0; padding-left: 0; }
.metrics dt { display: flex; align-items: center; gap: 6px; font-size: .79rem; font-weight: 600; }
.metrics dt svg { width: 15px; height: 15px; color: var(--wine); flex-shrink: 0; }
.metrics dd { font: 400 2.4rem/1.15 var(--atlas-display); margin: 6px 0 1px; }
.metrics dd small { font: 500 .94rem var(--font-sans); color: var(--muted); }
.register { background: var(--sheet); border: 1px solid var(--line); border-radius: 12px; padding: 18px 22px 7px; }
.register .section-head { margin-bottom: 12px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .83rem; text-align: left; }
table thead { background: #f4f0ea; }
table thead th { font-size: .74rem; color: var(--muted); font-weight: 600; }
table th, table td { padding: 10px 13px; }
table tbody tr + tr, .thermal-row + .thermal-row, .compare-row + .compare-row { border-top: 1px solid #e8e0da; }
table th a { display: inline-flex; align-items: center; gap: 5px; color: var(--wine); }
table td small, .register small { display: block; color: var(--muted); font-size: .74rem; }
.thermal-row, .compare-row { display: grid; align-items: center; gap: 12px; padding: 15px 4px; font-size: .86rem; }
.thermal-row { grid-template-columns: minmax(70px,.7fr) max-content minmax(130px,2fr) auto 16px; }
.compare-row { grid-template-columns: minmax(95px,1fr) 2fr minmax(64px,auto) 16px; }
.bar { height: 8px; background: #ece3dc; border-radius: 3px; overflow: hidden; }
.bar i { display: block; height: 100%; background: #9f6842; }
.thermal-row:hover, .compare-row:hover, table tbody tr:hover { background: #f8f3ed; }
.sheets { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,240px),1fr)); column-gap: 22px; }
.sheet { padding: 14px 2px; min-width: 0; border-top: 1px solid var(--line); }
.sheet h3 { font-size: 1.65rem; }
.sheet p, .sheet small { color: var(--muted); font-size: .8rem; margin-top: 3px; }
.sheet-readings { gap: 18px; margin: 12px 0; }
.sheet-readings span { display: inline-flex; align-items: center; gap: 5px; font-weight: 650; }
.sheet-readings svg { width: 15px; color: var(--wine); }
.sheet-foot { margin-top: 13px; }
.feedback, .empty { padding: 18px; border: 1px solid var(--line); border-radius: 10px; margin: 12px 0; font-size: .87rem; }
.feedback { display: flex; gap: 10px; align-items: center; background: #fff0de; flex-wrap: wrap; }
.feedback button { margin-left: auto; text-decoration: underline; }
.empty { background: var(--sheet); }
.empty h2 { margin-top: 6px; font-size: 1.5rem; }
@keyframes sync-turn { to { transform: rotate(360deg); } }
@media(prefers-reduced-motion:no-preference) { .turning { animation: sync-turn 1s linear infinite; } }
@media(min-width:901px) and (max-width:1190px) {
  .priority-row { grid-template-columns: minmax(0,1.5fr) minmax(225px,1fr); }
  .risk-panel { padding: 16px; }
  .metrics > div { padding-inline: 12px; }
}
@media(max-width:900px) {
  .priority-row { grid-template-columns: minmax(0,1fr); }
  .priority-row > .atlas, .priority-row > .risk-panel { grid-column: 1; grid-row: auto; }
  .risk-list { max-height: 220px; }
  .metrics > div { padding-inline: 10px; }
}
@media(max-width:650px) {
  h1 { font-size: 2.35rem; }
  h2 { font-size: 1.65rem; }
  .page-head { align-items: flex-start; flex-wrap: wrap; gap: 8px; margin-bottom: 13px; }
  .page-head p { font-size: .74rem; }
  .sync { min-height: 34px; padding: 6px 10px; }
  .views { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 0 8px; }
  .views button { justify-content: center; padding: 8px 4px; }
  .views .chosen { background: #f0e3e5; }
  .filters { margin: 12px 0; gap: 5px; }
  .filters > svg { display: none; }
  .filters select { min-width: 0; flex: 1 1 106px; }
  .risk-switch { margin-left: 0; }
  .risk-panel { padding: 16px; }
  .metrics { grid-template-columns: repeat(2,minmax(0,1fr)); row-gap: 14px; }
  .metrics > div:nth-child(odd) { border: 0; padding-left: 0; }
  .metrics dt { align-items: flex-start; }
  .metrics dd { font-size: 2rem; }
  .register { padding: 14px 12px 5px; }
  .register .section-head { flex-wrap: wrap; gap: 4px; }
  table { min-width: 540px; }
  .thermal-row { grid-template-columns: 1fr auto; }
  .thermal-row .state { justify-self: end; }
  .thermal-row > svg, .compare-row > svg { display: none; }
  .compare-row { grid-template-columns: 1fr auto; }
  .bar { grid-row: 2; grid-column: 1 / -1; }
}
@media(max-width:460px) {
  .filters select { flex-basis: 100%; }
}
</style>
