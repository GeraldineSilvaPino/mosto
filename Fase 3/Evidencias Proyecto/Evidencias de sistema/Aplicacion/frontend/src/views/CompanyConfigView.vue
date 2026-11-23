<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ArrowUpRight, Grape, Mail, MapPin, Pencil, Phone, X } from 'lucide-vue-next'
import companyService, { wineryDisplayName } from '../services/companyService'

const identityFields = [
  { key: 'brandName', label: 'Nombre comercial' },
  { key: 'facility', label: 'Bodega o sede' },
  { key: 'valley', label: 'Valle vitivinícola' },
  { key: 'address', label: 'Dirección de la bodega' },
  { key: 'region', label: 'Comuna y región' },
  { key: 'contactEmail', label: 'Correo administrativo', type: 'email' },
  { key: 'contactPhone', label: 'Teléfono de contacto', type: 'tel' }
]
const fiscalFields = [
  { key: 'legalName', label: 'Razón social' },
  { key: 'taxId', label: 'RUT de la empresa' },
  { key: 'taxCategory', label: 'Giro comercial' }
]
const channels = [
  { key: 'dailyEnologyReport', label: 'Reporte diario a enología', detail: 'Resumen de las 07:00 h' },
  { key: 'smsCriticalAlerts', label: 'Alertas críticas por SMS', detail: 'Paradas o sobrecalentamiento' }
]
const titles = {
  identity: 'Editar ficha de la viña', fiscal: 'Editar datos fiscales',
  channels: 'Editar notificaciones', upgrade: 'Ampliar capacidad'
}
const savedCompany = ref(null)
const company = computed(() => savedCompany.value && ({
  ...savedCompany.value,
  brandName: wineryDisplayName(savedCompany.value.brandName)
}))
const loading = ref(true)
const loadError = ref('')
const message = ref('')
const dialog = ref(null)
const section = ref('')
const draft = ref({})
const extra = ref(6)
const saving = ref(false)
const readingLogo = ref(false)
const formError = ref('')
const fields = computed(() => section.value === 'identity' ? identityFields : fiscalFields)
const quota = computed(() => company.value?.saasQuota)
const changes = computed(() => Object.fromEntries(
  Object.entries(draft.value).filter(([key, value]) => company.value[key] !== value)
))
const address = computed(() => [company.value?.address, company.value?.region].filter(Boolean).join(', '))

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    savedCompany.value = await companyService.obtenerConfiguracion()
  } catch {
    loadError.value = 'No se pudo cargar la configuración de la viña.'
  } finally {
    loading.value = false
  }
}

async function openEditor(target) {
  section.value = target
  formError.value = ''
  message.value = ''
  extra.value = 6
  const keys = target === 'channels' ? channels.map(item => item.key)
    : target === 'identity' ? [...identityFields.map(item => item.key), 'logoUrl']
    : target === 'fiscal' ? fiscalFields.map(item => item.key) : []
  draft.value = Object.fromEntries(keys.map(key => [key, company.value[key]]))
  await nextTick()
  dialog.value.showModal()
}

function readLogo(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file) return
  formError.value = ''
  if (!['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'].includes(file.type) || file.size > 2 * 1024 * 1024) {
    formError.value = 'Elige una imagen PNG, JPG, WebP o SVG de hasta 2 MB.'
    return
  }
  const reader = new FileReader()
  readingLogo.value = true
  reader.onload = () => { draft.value.logoUrl = reader.result }
  reader.onerror = () => { formError.value = 'No se pudo leer el logotipo. Vuelve a elegir la imagen.' }
  reader.onloadend = () => { readingLogo.value = false }
  reader.readAsDataURL(file)
}

async function save() {
  if (saving.value || readingLogo.value) return
  saving.value = true
  formError.value = ''
  try {
    if (section.value === 'upgrade') {
      const result = await companyService.solicitarAmpliacion(extra.value)
      quota.value.maxCubas = result.nueva_capacidad
      message.value = 'Capacidad ampliada a ' + result.nueva_capacidad + ' cubas.'
    } else {
      const patch = changes.value
      savedCompany.value = await companyService.actualizarConfiguracion(patch)
      if ('brandName' in patch) {
        window.dispatchEvent(new CustomEvent('mosto:winery-renamed', { detail: company.value.brandName }))
      }
      message.value = 'Cambios guardados.'
    }
    dialog.value.close()
  } catch (error) {
    formError.value = error.message || 'No se pudo guardar. Vuelve a intentarlo.'
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="winery">
    <header class="page-head">
      <h1>Configuración de la viña</h1>
      <button v-if="company" class="btn primary" @click="openEditor('identity')">
        <Pencil :size="15" /> Editar ficha
      </button>
    </header>
    <p v-if="loading" role="status">Cargando ficha de la viña…</p>
    <div v-else-if="loadError" class="load-error">
      <p role="alert">{{ loadError }}</p><button class="btn" @click="load">Reintentar</button>
    </div>
    <template v-else-if="company">
      <p v-if="message" class="feedback" role="status">{{ message }}</p>
      <section class="identity" aria-labelledby="winery-name">
        <div class="identity-name">
          <img v-if="company.logoUrl" class="brand-logo" :src="company.logoUrl" alt="Logotipo de la viña" />
          <Grape v-else class="brand-mark" aria-hidden="true" :size="39" :stroke-width="1.3" />
          <h2 id="winery-name">{{ company.brandName || 'Viña sin nombre' }}</h2>
          <p>{{ [company.facility, company.valley].filter(Boolean).join(' · ') || 'Bodega sin identificar' }}</p>
        </div>
        <div class="contact">
          <h2>Contacto de la bodega</h2>
          <ul>
            <li><MapPin aria-hidden="true" /><span>{{ address || 'Sin dirección registrada' }}</span></li>
            <li><Mail aria-hidden="true" /><a v-if="company.contactEmail" :href="'mailto:' + company.contactEmail">{{ company.contactEmail }}</a><span v-else>Sin correo registrado</span></li>
            <li><Phone aria-hidden="true" /><a v-if="company.contactPhone" :href="'tel:' + company.contactPhone.replace(/[^+\d]/g, '')">{{ company.contactPhone }}</a><span v-else>Sin teléfono registrado</span></li>
          </ul>
        </div>
      </section>

      <div class="details">
        <div class="records">
          <section>
            <header class="section-head"><h2>Datos fiscales</h2><button class="text-action" aria-label="Editar datos fiscales" @click="openEditor('fiscal')">Editar <Pencil :size="14" /></button></header>
            <dl class="ledger">
              <div v-for="item in fiscalFields" :key="item.key"><dt>{{ item.label }}</dt><dd>{{ company[item.key] || 'Sin registrar' }}</dd></div>
            </dl>
          </section>
          <section>
            <header class="section-head"><h2>Notificaciones</h2><button class="text-action" aria-label="Editar notificaciones" @click="openEditor('channels')">Editar <Pencil :size="14" /></button></header>
            <dl class="channels">
              <div v-for="item in channels" :key="item.key">
                <dt>{{ item.label }}<small>{{ item.detail }}</small></dt>
                <dd>{{ company[item.key] ? 'Activado' : 'Desactivado' }}</dd>
              </div>
            </dl>
          </section>
        </div>

        <section v-if="quota" class="plan">
          <div class="section-head"><h2>Plan y capacidad</h2><span class="state">{{ quota.status }}</span></div>
          <p class="plan-name">{{ quota.planName }}</p><p class="cycle">{{ quota.billingCycle }}</p>
          <dl class="limits">
            <div v-for="item in [{ label: 'Cubas registradas', used: quota.usedCubas, max: quota.maxCubas }, { label: 'Cuentas activas', used: quota.usedUsers, max: quota.maxUsers }]" :key="item.label">
              <dt>{{ item.label }}</dt><dd><strong>{{ item.used }}</strong> de {{ item.max }}</dd>
              <progress v-if="item.max > 0" aria-hidden="true" :max="item.max" :value="item.used"></progress>
            </div>
          </dl>
          <button class="text-action" @click="openEditor('upgrade')">Ampliar capacidad de cubas <ArrowUpRight :size="16" /></button>
        </section>
      </div>

      <dialog ref="dialog" aria-labelledby="editor-title" @cancel="(saving || readingLogo) && $event.preventDefault()">
        <form @submit.prevent="save">
          <header class="dialog-head"><h2 id="editor-title">{{ titles[section] }}</h2><button type="button" class="close" :disabled="saving || readingLogo" aria-label="Cerrar" @click="dialog.close()"><X :size="19" /></button></header>
          <fieldset :disabled="saving" class="dialog-body">
            <template v-if="section === 'upgrade'">
              <p>Selecciona cuántas cubas quieres añadir al plan de {{ company.brandName }}.</p>
              <div class="choices">
                <label v-for="qty in [6, 12, 24]" :key="qty"><input v-model="extra" type="radio" name="extra" :value="qty" /> +{{ qty }} cubas</label>
              </div>
              <dl class="ledger"><div><dt>Capacidad actual</dt><dd>{{ quota.maxCubas }} cubas</dd></div><div><dt>Al confirmar</dt><dd><strong>{{ quota.maxCubas + extra }} cubas</strong></dd></div></dl>
            </template>
            <div v-else-if="section === 'channels'" class="channel-options">
              <label v-for="item in channels" :key="item.key"><input type="checkbox" v-model="draft[item.key]" /><span>{{ item.label }}<small>{{ item.detail }}</small></span></label>
            </div>
            <template v-else>
              <div v-if="section === 'identity'" class="logo-editor">
                <img v-if="draft.logoUrl" :src="draft.logoUrl" class="logo-thumb" alt="Logotipo seleccionado" />
                <div><label for="winery-logo">Logotipo</label><input id="winery-logo" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" :disabled="readingLogo" @change="readLogo" /><small>PNG, JPG, WebP o SVG · Hasta 2 MB</small></div>
                <button v-if="draft.logoUrl" type="button" class="text-action" :disabled="readingLogo" @click="draft.logoUrl = ''">Quitar</button>
              </div>
              <div class="field-grid"><label v-for="item in fields" :key="item.key">{{ item.label }}<input v-model="draft[item.key]" :type="item.type || 'text'" /></label></div>
            </template>
            <p v-if="formError" class="error" role="alert">{{ formError }}</p>
          </fieldset>
          <footer><button type="button" class="btn" :disabled="saving || readingLogo" @click="dialog.close()">Cancelar</button><button class="btn primary" :disabled="saving || readingLogo || (section !== 'upgrade' && !Object.keys(changes).length)">{{ saving ? 'Guardando…' : section === 'upgrade' ? 'Confirmar ampliación' : 'Guardar cambios' }}</button></footer>
        </form>
      </dialog>
    </template>
  </div>
</template>

<style scoped>
.winery {
  --ink: #30232a;
  --wine: #763c51;
  --muted: #695d61;
  --line: #dbd2cc;
  --paper: #fffdf9;
  --display: 'Instrument Serif', Georgia, serif;
  max-width: 1540px;
  margin-inline: auto;
  color: var(--ink);
  overflow-wrap: anywhere;
}
h1, h2, .plan-name { font-family: var(--display); font-weight: 400; letter-spacing: -.022em; line-height: 1.08; }
h1 { font-size: clamp(2.55rem, 4vw, 3.25rem); }
h2 { font-size: clamp(1.75rem, 2.6vw, 2.1rem); }
.page-head, .section-head, .dialog-head, footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.page-head { margin-bottom: 20px; flex-wrap: wrap; }
.btn, .text-action, .close { display: inline-flex; align-items: center; justify-content: center; gap: 7px; cursor: pointer; font: 600 .83rem/1.4 var(--font-sans); }
.btn { min-height: 40px; border: 1px solid var(--line); border-radius: 7px; padding: 8px 14px; color: var(--ink); background: var(--paper); }
.btn:hover { border-color: var(--wine); }
.btn.primary { color: #fffaf6; border-color: var(--wine); background: var(--wine); }
.btn.primary:hover { background: #633247; }
button:disabled { opacity: .55; cursor: default; }
.text-action, .close { color: var(--wine); background: none; border: 0; padding: 8px 1px; }
.text-action:hover, a:hover { text-decoration: underline; text-underline-offset: 3px; }
:where(button, input, a):focus-visible { outline: 2px solid #985d75; outline-offset: 3px; }
.identity { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); border-radius: 14px; overflow: hidden; }
.identity-name, .contact { padding: clamp(22px, 2.3vw, 36px); }
.identity-name { background: #32232d; color: #fff5eb; display: flex; flex-direction: column; justify-content: flex-end; align-items: flex-start; }
.brand-mark { color: #dab9c3; margin-bottom: 17px; }
.brand-logo { display: block; max-width: 130px; height: 50px; object-fit: contain; padding: 3px; border-radius: 5px; background: var(--paper); margin-bottom: 12px; }
.identity-name h2 { font-size: clamp(2.2rem, 3.55vw, 3.5rem); text-wrap: balance; }
.identity-name p { font-size: .91rem; color: #e4ced6; margin-top: 10px; }
.contact { background: #eee7dd; display: grid; align-content: center; gap: 16px; }
.contact ul { list-style: none; display: grid; gap: 10px; margin: 0; padding: 0; }
.contact li { display: flex; gap: 10px; align-items: baseline; font-size: .89rem; }
.contact li svg { align-self: flex-start; width: 16px; height: 16px; margin-top: 3px; color: var(--wine); flex: none; }
.contact a { color: inherit; }
.details { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, .88fr); align-items: start; gap: clamp(22px, 3vw, 54px); margin-top: 26px; }
.records { display: grid; gap: 24px; }
.records section { border-top: 1px solid var(--line); }
.records .section-head { padding: 14px 0 9px; }
dl { margin: 0; font-size: .88rem; }
.ledger div, .channels div { padding: 10px 0; display: grid; grid-template-columns: minmax(115px, .62fr) minmax(0, 1.38fr); gap: 10px 20px; }
.ledger div + div, .channels div + div { border-top: 1px solid var(--line); }
.ledger dt, small, .cycle, .channels dd { color: var(--muted); }
dd { margin: 0; }
.channels div { grid-template-columns: 1fr auto; align-items: center; }
small { display: block; margin-top: 3px; font-size: .78rem; line-height: 1.5; font-weight: 400; }
.channels dd, .state { font-size: .8rem; }
.plan { padding: clamp(18px, 2vw, 28px); border: 1px solid var(--line); border-radius: 12px; background: var(--paper); }
.plan .section-head { align-items: baseline; flex-wrap: wrap; padding-bottom: 13px; border-bottom: 1px solid var(--line); }
.state { color: var(--muted); }
.plan-name { font-size: 1.65rem; margin: 16px 0 4px; }
.cycle { font-size: .82rem; }
.limits { margin-top: 20px; display: grid; gap: 14px; }
.limits div { display: grid; grid-template-columns: 1fr auto; align-items: baseline; gap: 7px; }
.limits dd { font-variant-numeric: tabular-nums; }
progress { grid-column: 1/-1; width: 100%; height: 5px; border: 0; border-radius: 3px; overflow: hidden; appearance: none; background: #e8e0d8; color: var(--wine); }
progress::-webkit-progress-bar { background: #e8e0d8; }
progress::-webkit-progress-value { background: var(--wine); }
progress::-moz-progress-bar { background: var(--wine); }
.plan > button { margin-top: 17px; }
.feedback, .load-error { margin-bottom: 12px; font-size: .88rem; }
.feedback { color: #435543; }
.load-error, .error { color: #8c3446; }
dialog { width: min(560px, calc(100% - 24px)); max-height: 90dvh; margin: auto; padding: 0; border: 0; border-radius: 12px; background: var(--paper); color: var(--ink); scrollbar-color: #b7a9ac var(--paper); overflow: auto; }
dialog::backdrop { background: rgb(43 29 37 / .55); }
.dialog-head { background: #eee7dd; padding: 18px 22px; }
.close { width: 36px; height: 36px; flex: none; }
.dialog-body { min-width: 0; margin: 0; padding: 20px 22px; display: grid; gap: 18px; border: 0; font-size: .91rem; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 13px; }
.field-grid label:first-child { grid-column: 1/-1; }
.field-grid label, .logo-editor label { display: grid; gap: 5px; font-size: .81rem; font-weight: 600; }
.field-grid input { min-width: 0; width: 100%; border: 1px solid #baaaa3; border-radius: 6px; padding: 9px 10px; color: var(--ink); background: var(--paper); font: inherit; font-weight: 400; caret-color: var(--wine); }
.logo-editor { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; border-bottom: 1px solid var(--line); padding-bottom: 14px; }
.logo-editor > div { min-width: 0; flex: 1 1 190px; }
.logo-editor input { width: 100%; margin-top: 5px; font-size: .78rem; }
.logo-editor input::file-selector-button { color: var(--wine); border: 1px solid var(--line); border-radius: 5px; padding: 7px; background: var(--paper); cursor: pointer; }
.logo-thumb { width: 54px; height: 54px; object-fit: contain; }
.choices, .channel-options { display: flex; gap: 12px; flex-wrap: wrap; }
.choices label, .channel-options label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.choices label { padding: 9px; border: 1px solid var(--line); border-radius: 6px; }
.choices label:has(:checked) { border-color: var(--wine); background: #f6edf0; }
.channel-options { flex-direction: column; }
input[type=checkbox], input[type=radio] { accent-color: var(--wine); width: 17px; height: 17px; }
footer { justify-content: flex-end; padding: 14px 22px; border-top: 1px solid var(--line); }
@media (max-width: 1000px) {
  .details { grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 20px; }
}
@media (max-width: 750px) {
  .identity, .details { grid-template-columns: minmax(0, 1fr); }
  .identity-name, .contact { padding: 20px; }
  .brand-mark { width: 30px; height: 30px; margin-bottom: 12px; }
}
@media (max-width: 480px) {
  .ledger div { grid-template-columns: 1fr; gap: 3px; }
  .field-grid { grid-template-columns: 1fr; }
  .dialog-head, .dialog-body, footer { padding: 14px; }
  .choices { gap: 5px; }
}
</style>
