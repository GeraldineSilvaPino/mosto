<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ChevronDown, ChevronRight, Search, UserPlus, X } from 'lucide-vue-next'
import userService from '../services/userService'
import authService from '../services/authService'

const roles = { admin: 'Administrador', enologo: 'Enólogo', operador: 'Operario', lector: 'Solo lectura' }
const accounts = ref([])
const warehouses = ref([])
const warehouseId = ref(null)
const warehouse = computed(() => warehouses.value.find(row => row.id === warehouseId.value))
const loading = ref(false)
const loadError = ref('')
const feedback = ref('')
const roleFilter = ref('')
const query = ref('')
const sessionId = authService.obtenerUsuarioSesion()?.id
const team = computed(() => accounts.value.flatMap(person => {
  const membership = person.memberships?.find(m => m.bodega_id === warehouseId.value)
  if (!membership) return []
  return [{ ...person, localRole: membership.role === 'operario' ? 'operador' : membership.role }]
}).sort((a,b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name, 'es')))
const activeCount = computed(() => team.value.filter(person => person.active).length)
const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const visible = computed(() => {
  const search = fold(query.value.trim())
  return team.value.filter(person => (!roleFilter.value || person.localRole === roleFilter.value)
    && (!search || fold(person.name + ' ' + person.email).includes(search)))
})
function resetFilters() { query.value = ''; roleFilter.value = '' }
function changeWarehouse() { resetFilters(); feedback.value = '' }
async function load() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    const [people, locations] = await Promise.all([userService.listar(), userService.bodegas()])
    accounts.value = people
    warehouses.value = locations
    if (!warehouse.value) warehouseId.value = locations[0]?.id ?? null
  } catch (err) {
    accounts.value = []
    warehouses.value = []
    warehouseId.value = null
    loadError.value = err.message || 'No se pudo consultar el equipo.'
  } finally { loading.value = false }
}
onMounted(load)

const dialog = ref(null)
const mode = ref('')
const personId = ref(null)
const person = computed(() => team.value.find(row => row.id === personId.value))
const blankForm = () => ({ name: '', email: '', password: '', role: 'operador' })
const form = ref(blankForm())
const busy = ref(false)
const formError = ref('')
const title = computed(() => mode.value === 'create' ? 'Crear usuario' : mode.value === 'status'
  ? (person.value?.active ? 'Suspender cuenta' : 'Reactivar cuenta') : person.value?.name)

async function open(action, row) {
  personId.value = row?.id ?? null
  form.value = blankForm()
  if (row) form.value.role = row.localRole
  formError.value = feedback.value = ''
  mode.value = action
  await nextTick()
  dialog.value?.showModal()
}
function close() {
  if (busy.value) return
  dialog.value?.close()
  mode.value = ''
  form.value = blankForm()
  personId.value = null
}
function switchMode(action) {
  formError.value = ''
  form.value.role = person.value.localRole
  mode.value = action
}
async function save() {
  if (busy.value || !warehouse.value) return
  const action = mode.value
  busy.value = true
  formError.value = ''
  try {
    let saved
    if (action === 'create') {
      saved = await userService.crear({ ...form.value, name: form.value.name.trim(), email: form.value.email.trim().toLowerCase(), bodega_id: warehouseId.value })
      accounts.value.push(saved)
      resetFilters()
      feedback.value = 'Cuenta creada para ' + saved.name + '.'
    } else {
      if (action === 'member') {
        saved = await userService.actualizarRol(personId.value, form.value.role, warehouseId.value)
        feedback.value = 'Rol actualizado para ' + saved.name + '.'
      } else {
        saved = await userService.actualizarEstado(personId.value, !person.value.active)
        feedback.value = 'Cuenta ' + (saved.active ? 'reactivada' : 'suspendida') + ' para ' + saved.name + '.'
      }
      accounts.value = accounts.value.map(row => row.id === saved.id ? saved : row)
    }
    busy.value = false
    close()
    if (saved.id === sessionId) await load()
  } catch (err) {
    formError.value = err.message || 'No se pudo guardar el cambio. Inténtalo de nuevo.'
  } finally { busy.value = false }
}
</script>

<template>
  <div class="users-page">
    <header class="page-head">
      <h1>Usuarios y roles</h1>
      <button class="button primary" :disabled="!warehouse || loading" @click="open('create')"><UserPlus :size="16" aria-hidden="true"/>Crear usuario</button>
    </header>
    <p v-if="loadError" role="alert" class="error">{{ loadError }} <button class="text-action" @click="load">Reintentar</button></p>
    <p v-if="feedback" class="feedback" role="status">{{ feedback }}</p>
    <section v-if="!loadError" class="directory" aria-labelledby="team-title">
      <header class="directory-head">
        <div>
          <h2 id="team-title">Equipo de bodega</h2>
          <p v-if="warehouse">{{ activeCount }} {{ activeCount === 1 ? 'cuenta activa' : 'cuentas activas' }} · {{ team.length - activeCount }} suspendidas</p>
        </div>
        <div v-if="warehouses.length" class="scope">
          <label for="warehouse">Bodega</label>
          <span class="select-wrap"><select id="warehouse" v-model="warehouseId" @change="changeWarehouse">
            <option v-for="w in warehouses" :key="w.id" :value="w.id">{{ w.nombre }}</option>
          </select><ChevronDown :size="16" aria-hidden="true"/></span>
        </div>
      </header>
      <template v-if="warehouse">
        <div class="toolbar">
          <label class="search"><Search :size="16" aria-hidden="true"/><input v-model="query" aria-label="Buscar por nombre o correo" type="search" placeholder="Buscar por nombre o correo"/></label>
          <label class="select-wrap"><select v-model="roleFilter" aria-label="Filtrar por rol"><option value="">Todos los roles</option><option v-for="(label,key) in roles" :key="key" :value="key">{{ label }}</option></select><ChevronDown :size="15" aria-hidden="true"/></label>
          <button v-if="roleFilter || query" class="text-action" @click="resetFilters">Limpiar filtros</button>
        </div>
        <div v-if="visible.length">
          <div aria-hidden="true" class="columns"><span>Persona</span><span>Rol en esta bodega</span><span>Estado de cuenta</span></div>
          <ul class="roster">
            <li v-for="row in visible" :key="row.id">
              <button class="member" @click="open('member', row)">
                <span class="identity"><strong>{{ row.name }}</strong><small>{{ row.email }}</small></span>
                <span class="role">{{ roles[row.localRole] || row.localRole }}</span>
                <span class="state" :class="{suspended: !row.active}">{{ row.active ? 'Activa' : 'Suspendida' }}</span>
                <ChevronRight :size="17" aria-hidden="true"/>
              </button>
            </li>
          </ul>
        </div>
        <p v-else class="empty" role="status">{{ team.length ? 'Ninguna persona coincide con estos filtros.' : 'Todavía no hay personas asignadas a esta bodega.' }}</p>
      </template>
      <p v-else class="empty" role="status">{{ loading ? 'Consultando el equipo…' : 'Sin bodegas disponibles.' }}</p>
    </section>

    <dialog ref="dialog" aria-labelledby="member-title" @cancel.prevent="close" @click.self="close">
      <div class="dialog-content">
        <header class="dialog-head">
          <div><h2 id="member-title">{{ title }}</h2><p>{{ mode === 'create' ? warehouse?.nombre : person?.email }}</p></div>
          <button class="close" aria-label="Cerrar ficha" :disabled="busy" @click="close"><X :size="18"/></button>
        </header>
        <form v-if="mode" @submit.prevent="save">
          <template v-if="mode === 'create'">
            <label>Nombre completo<input v-model.trim="form.name" required minlength="2" autocomplete="off" :disabled="busy"/></label>
            <label>Correo electrónico<input v-model.trim="form.email" type="email" required autocomplete="off" :disabled="busy"/></label>
            <label>Contraseña inicial<input v-model="form.password" type="password" required minlength="12" maxlength="256" autocomplete="new-password" aria-describedby="password-help" :disabled="busy"/></label>
            <p class="hint" id="password-help">Usa al menos 12 caracteres y comparte las credenciales directamente con la persona.</p>
          </template>
          <template v-if="mode === 'member'">
            <div class="account-line"><span>Estado de cuenta</span><span class="state" :class="{suspended: !person.active}">{{ person.active ? 'Activa' : 'Suspendida' }}</span></div>
          </template>
          <div v-if="mode !== 'status'" class="field">
            <label for="member-role">Rol en {{ warehouse?.nombre }}</label>
            <select id="member-role" v-model="form.role" :disabled="busy"><option v-for="(label,key) in roles" :key="key" :value="key">{{ label }}</option></select>
          </div>
          <p v-else class="status-copy">{{ person.active ? 'Se suspenderá el acceso de' : 'Se reactivará el acceso de' }} <b>{{ person.name }}</b> en todas sus bodegas.</p>
          <p v-if="formError" role="alert" class="error">{{ formError }}</p>
          <footer>
            <button v-if="mode === 'member'" type="button" class="text-action status-action" :disabled="busy" @click="switchMode('status')">{{ person.active ? 'Suspender cuenta' : 'Reactivar cuenta' }}</button>
            <button class="button" type="button" :disabled="busy" @click="mode === 'status' ? switchMode('member') : close()">Cancelar</button>
            <button class="button primary" :disabled="busy || (mode === 'member' && form.role === person?.localRole)">
              {{ busy ? 'Guardando…' : mode === 'create' ? 'Crear cuenta' : mode === 'member' ? 'Guardar rol' : person?.active ? 'Confirmar suspensión' : 'Confirmar reactivación' }}
            </button>
          </footer>
        </form>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.users-page {
  --ink:#30232a; --muted:#695d61; --wine:#763c51; --rule:#dbd2ca; --paper:#fffdf9;
  --display:'Instrument Serif', Georgia, serif;
  max-width:1540px; margin-inline:auto; color:var(--ink);
}
h1,h2 { font-family:var(--display); font-weight:400; line-height:1.1; letter-spacing:-.02em; }
h1 { font-size:clamp(2.55rem,4vw,3.25rem); }
h2 { font-size:clamp(1.7rem,2.8vw,2.15rem); }
.page-head,.directory-head,.dialog-head,.toolbar,.search,.scope,.button,.account-line,footer { display:flex; align-items:center; gap:10px; }
.page-head,.directory-head,.dialog-head,.account-line { justify-content:space-between; }
.page-head,.directory-head,.toolbar,footer { flex-wrap:wrap; }
.page-head { margin-bottom:19px; }
.button { justify-content:center; min-height:38px; padding:8px 13px; border:1px solid var(--rule); border-radius:7px; background:var(--paper); color:var(--ink); font:600 .83rem/1.4 var(--font-sans); }
.button:hover:enabled { border-color:var(--wine); }
.primary { color:var(--paper); background:var(--wine); border-color:var(--wine); }
.primary:hover:enabled { background:#603044; }
button:disabled { opacity:.55; cursor:default; }
.users-page :focus-visible { outline:2px solid var(--wine); outline-offset:2px; }
.directory { overflow:clip; border:1px solid var(--rule); border-radius:12px; background:var(--paper); }
.directory-head { padding:20px clamp(16px,2vw,28px); background:#32232d; color:#fff6ee; }
.directory-head p { color:#e5cfd8; font-size:.82rem; margin-top:6px; }
.scope { min-width:0; max-width:100%; gap:8px; color:#efdee3; }
.scope label { font-size:.8rem; }
.select-wrap { position:relative; display:inline-flex; min-width:0; max-width:100%; }
.select-wrap select { min-width:0; max-width:100%; appearance:none; color:var(--wine); font:600 .84rem/1.5 var(--font-sans); border:0; border-radius:0; border-bottom:1px solid #bda1ac; padding:7px 23px 7px 2px; background:transparent; cursor:pointer; }
.select-wrap svg { position:absolute; right:1px; top:50%; transform:translateY(-50%); pointer-events:none; }
.scope select { color:#fff6ee; }
.scope option { color:var(--ink); background:var(--paper); }
.scope select:focus-visible { outline-color:#efc4cf; }
.toolbar { padding:14px clamp(16px,2vw,28px); gap:12px 18px; }
.search { flex:1 1 180px; color:var(--muted); min-width:0; }
input[type=search] { width:100%; min-width:0; border:0; padding:7px 2px; background:transparent; font:400 .86rem var(--font-sans); color:var(--ink); }
input::placeholder { color:var(--muted); }
.text-action { color:var(--wine); font:600 .82rem/1.5 var(--font-sans); text-decoration:underline; text-underline-offset:3px; }
.columns,.member { display:grid; align-items:center; grid-template-columns:minmax(0,1.6fr) minmax(0,1fr) minmax(90px,.65fr) 16px; gap:12px; padding-inline:clamp(16px,2vw,28px); }
.columns { background:#f1ebe3; color:var(--muted); font-size:.77rem; padding-block:8px; }
.roster { list-style:none; }
.roster li { border-top:1px solid var(--rule); }
.member { width:100%; text-align:left; color:inherit; padding-block:14px; }
.member:hover { background:#f9f3ed; }
.member:focus-visible { outline-offset:-3px; }
.identity { min-width:0; overflow-wrap:anywhere; }
.identity strong,.identity small { display:block; }
.identity strong { font-size:.94rem; }
.identity small { margin-top:3px; color:var(--muted); font-size:.79rem; }
.role { font-size:.84rem; }
.state { display:inline-flex; align-items:center; gap:7px; font-size:.8rem; color:#3f5a44; }
.state::before { content:''; width:7px; height:7px; border:1px solid currentColor; border-radius:50%; background:currentColor; flex:none; }
.state.suspended { color:#7b4e41; }
.suspended::before { background:transparent; }
.member svg { color:var(--wine); }
.empty,.error,.feedback { font-size:.85rem; padding:15px; }
.error { color:#892c40; }
.feedback { color:var(--wine); }
dialog { margin:auto; padding:0; width:min(465px,calc(100% - 24px)); max-height:90dvh; overflow:auto; border:0; border-radius:12px; color:var(--ink); background:var(--paper); }
dialog::backdrop { background:rgba(40,25,34,.55); }
.dialog-head { align-items:flex-start; padding:19px 21px; background:#efe8df; overflow-wrap:anywhere; }
.dialog-head p { margin-top:5px; font-size:.82rem; color:var(--muted); }
.close { color:var(--wine); width:34px; height:34px; display:grid; place-items:center; flex:none; }
form { display:grid; gap:14px; padding:19px 21px; }
form label,.field { display:grid; gap:6px; font-size:.85rem; font-weight:600; }
form input,form select { width:100%; min-width:0; color:var(--ink); font:400 .9rem/1.5 var(--font-sans); background:var(--paper); border:1px solid #b9aca4; border-radius:6px; padding:9px 10px; }
.hint,.account-line,.status-copy { font-size:.84rem; line-height:1.55; }
.hint { color:var(--muted); margin-top:-8px; }
form .error { padding:0; }
footer { justify-content:flex-end; border-top:1px solid var(--rule); padding-top:14px; margin-top:3px; }
.status-action { margin-right:auto; }
@media(max-width:680px) {
  .columns { display:none; }
  .member { grid-template-columns:minmax(0,1fr) auto 14px; gap:5px 8px; }
  .identity { grid-column:1/3; }
  .role { grid-column:1; color:var(--muted); }
  .state { grid-column:2; }
  .member svg { grid-row:1/3; grid-column:3; }
  .directory-head { align-items:flex-start; }
  .directory-head,.toolbar { padding:14px; }
  .toolbar { gap:5px 10px; }
}
@media(max-width:400px) {
  .dialog-head,form { padding:14px; }
  .toolbar .search { flex-basis:100%; }
}
</style>
