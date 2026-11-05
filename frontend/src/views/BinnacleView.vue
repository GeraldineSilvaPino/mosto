<script setup>
/**
 * 📋 08. [FRONT - VUE] Pantalla de Bitácora Enológica
 * Módulo 4: Hardware y Configuración Operativa
 *
 * Conectado con la API FastAPI y Supabase PostgreSQL (/api/bitacora):
 * 1. Timeline vertical con entradas agrupadas por día y ordenadas cronológicamente.
 * 2. 4 tipos de entrada diferenciados por icono y color (Nota, Alerta, Config, Lectura).
 * 3. Formulario funcional para registrar y persistir notas e intervenciones en la BD.
 * 4. Filtro por tipo de entrada (botones toggle reactivos).
 * 5. Búsqueda por texto libre.
 * 6. Selectores dinámicos de cubas y autores cargados desde la base de datos.
 */

import { ref, computed, nextTick, onMounted } from 'vue'
import {
  Plus,
  Search,
  FileText,
  AlertTriangle,
  Settings,
  Thermometer,
  X,
  Cylinder,
  User,
  Clock,
  ChevronDown,
  ChevronUp,
  Pencil
} from 'lucide-vue-next'
import binnacleService from '../services/binnacleService.js'
import cubaService from '../services/cubaService.js'
import userService from '../services/userService.js'

// ==========================================
// TIPOS DE ENTRADA
// ==========================================
const entryTypes = {
  nota:    { label: 'Nota',    icon: FileText,      colorClass: 'type-nota' },
  alerta:  { label: 'Alerta',  icon: AlertTriangle,  colorClass: 'type-alerta' },
  config:  { label: 'Config',  icon: Settings,       colorClass: 'type-config' },
  lectura: { label: 'Lectura', icon: Thermometer,    colorClass: 'type-lectura' }
}

// ==========================================
// CATÁLOGOS DINÁMICOS (Cubas y Autores)
// ==========================================
const cubasOptions = ref([
  { id: 'general', label: 'General' },
  { id: 'cuba-01', label: 'Cuba 01' },
  { id: 'cuba-02', label: 'Cuba 02' },
  { id: 'cuba-03', label: 'Cuba 03' },
  { id: 'cuba-04', label: 'Cuba 04' }
])

const authorOptions = ref(['María González', 'Alejandro Rojas', 'Administrador General', 'Sistema IoT'])

// ==========================================
// ENTRADAS DE BITÁCORA REACTIVAS
// ==========================================
const entries = ref([])
const isLoading = ref(false)
const isSubmitting = ref(false)

async function loadBitacora() {
  isLoading.value = true
  try {
    const data = await binnacleService.listarEntradas()
    if (Array.isArray(data)) {
      entries.value = data.map((item) => ({
        ...item,
        timestamp: new Date(item.timestamp)
      }))
    }

    // Cargar cubas reales si están disponibles
    try {
      const cubasData = await cubaService.listarCubas()
      if (Array.isArray(cubasData) && cubasData.length > 0) {
        const opts = [{ id: 'general', label: 'General' }]
        cubasData.forEach((c) => {
          opts.push({
            id: `cuba-${String(c.id).padStart(2, '0')}`,
            label: c.nombre || `Cuba ${c.codigo_cuba || c.id}`
          })
        })
        cubasOptions.value = opts
      }
    } catch {
      // Usar cubas por defecto si falla
    }

    // Cargar autores reales
    try {
      const usersData = await userService.listar()
      if (Array.isArray(usersData) && usersData.length > 0) {
        authorOptions.value = usersData.map((u) => u.name).concat(['Sistema IoT'])
      }
    } catch {
      // Usar autores por defecto
    }
  } catch (err) {
    console.error('Error al cargar bitácora:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadBitacora()
})

// ==========================================
// FILTROS Y BÚSQUEDA
// ==========================================
const activeFilter = ref('todos')
const searchQuery = ref('')

const filterCounts = computed(() => {
  const all = entries.value.length
  const nota = entries.value.filter(e => e.type === 'nota').length
  const alerta = entries.value.filter(e => e.type === 'alerta').length
  const config = entries.value.filter(e => e.type === 'config').length
  const lectura = entries.value.filter(e => e.type === 'lectura').length
  return { all, nota, alerta, config, lectura }
})

const filteredEntries = computed(() => {
  return entries.value
    .filter(e => {
      if (activeFilter.value !== 'todos' && e.type !== activeFilter.value) return false
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase()
        const cubaLabel = getCubaLabel(e.cuba).toLowerCase()
        return (
          e.message.toLowerCase().includes(q) ||
          e.author.toLowerCase().includes(q) ||
          cubaLabel.includes(q) ||
          (entryTypes[e.type]?.label || '').toLowerCase().includes(q)
        )
      }
      return true
    })
    .sort((a, b) => b.timestamp - a.timestamp)
})

// ==========================================
// AGRUPAMIENTO POR DÍA
// ==========================================
const groupedEntries = computed(() => {
  const groups = []
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  let currentLabel = null
  let currentGroup = null

  for (const entry of filteredEntries.value) {
    const label = getDayLabel(entry.timestamp, today, yesterday)
    if (label !== currentLabel) {
      currentLabel = label
      currentGroup = { label, entries: [] }
      groups.push(currentGroup)
    }
    currentGroup.entries.push(entry)
  }

  return groups
})

function getDayLabel(date, today, yesterday) {
  if (isSameDay(date, today)) return 'Hoy'
  if (isSameDay(date, yesterday)) return 'Ayer'
  return date.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' })
}

function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
         a.getMonth() === b.getMonth() &&
         a.getDate() === b.getDate()
}

function formatTime(date) {
  return date.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
}

function getCubaLabel(cubaId) {
  const found = cubasOptions.value.find(c => c.id === cubaId)
  return found ? found.label : cubaId
}

// ==========================================
// FORMULARIO NUEVA ENTRADA
// ==========================================
const showForm = ref(false)
const newEntry = ref({
  type: 'nota',
  cuba: 'general',
  message: '',
  author: 'María González'
})

function toggleForm() {
  showForm.value = !showForm.value
  if (showForm.value) {
    nextTick(() => {
      const textarea = document.querySelector('.form-textarea')
      if (textarea) textarea.focus()
    })
  }
}

async function submitEntry() {
  if (!newEntry.value.message.trim() || isSubmitting.value) return

  isSubmitting.value = true
  try {
    const res = await binnacleService.registrarEntrada({
      type: newEntry.value.type,
      cuba: newEntry.value.cuba,
      message: newEntry.value.message.trim(),
      author: newEntry.value.author
    })

    entries.value.unshift({
      id: res.id,
      type: res.type,
      timestamp: new Date(res.timestamp),
      cuba: res.cuba,
      message: res.message,
      author: res.author,
      dosis: res.dosis
    })

    // Reset form
    newEntry.value.message = ''
    newEntry.value.type = 'nota'
    newEntry.value.cuba = 'general'
    showForm.value = false
  } catch (err) {
    alert(err.message || 'Error al registrar la entrada en la bitácora.')
  } finally {
    isSubmitting.value = false
  }
}

function cancelForm() {
  showForm.value = false
  newEntry.value.message = ''
}
</script>

<template>
  <div class="binnacle-page">
    <!-- Encabezado -->
    <header class="binnacle-header">
      <div>
        <div class="header-pretitle">
          <Pencil :size="14" />
          <span>Registro Cronológico</span>
        </div>
        <h1 class="header-title">Bitácora de Bodega</h1>
        <p class="header-description">
          Registro de notas, alertas y eventos operativos de las cubas y la bodega.
        </p>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="btn-new-entry"
          @click="toggleForm"
        >
          <Plus :size="16" />
          <span>Nueva entrada</span>
        </button>
      </div>
    </header>

    <!-- Formulario rápido -->
    <transition name="form-slide">
      <section v-if="showForm" class="form-card">
        <div class="form-card-header">
          <h3>Agregar entrada</h3>
          <button type="button" class="form-close-btn" @click="cancelForm">
            <X :size="16" />
          </button>
        </div>

        <div class="form-body">
          <!-- Fila: tipo + cuba + autor -->
          <div class="form-row-trio">
            <div class="form-field">
              <label class="form-label">Tipo</label>
              <div class="form-type-pills">
                <button
                  v-for="(cfg, key) in entryTypes"
                  :key="key"
                  type="button"
                  class="type-pill"
                  :class="[cfg.colorClass, { active: newEntry.type === key }]"
                  @click="newEntry.type = key"
                >
                  <component :is="cfg.icon" :size="14" />
                  <span>{{ cfg.label }}</span>
                </button>
              </div>
            </div>

            <div class="form-field">
              <label class="form-label">Cuba</label>
              <select v-model="newEntry.cuba" class="form-select">
                <option v-for="c in cubasOptions" :key="c.id" :value="c.id">{{ c.label }}</option>
              </select>
            </div>

            <div class="form-field">
              <label class="form-label">Autor</label>
              <select v-model="newEntry.author" class="form-select">
                <option v-for="a in authorOptions" :key="a" :value="a">{{ a }}</option>
              </select>
            </div>
          </div>

          <!-- Descripción -->
          <div class="form-field">
            <label class="form-label">Descripción</label>
            <textarea
              v-model="newEntry.message"
              class="form-textarea"
              rows="3"
              placeholder="Ej: Remontaje realizado en Cuba 01, color y extracto en buenas condiciones..."
              @keydown.ctrl.enter="submitEntry"
            ></textarea>
            <span class="form-hint">Ctrl + Enter para guardar</span>
          </div>

          <!-- Acciones -->
          <div class="form-actions">
            <button type="button" class="btn-secondary" @click="cancelForm">Cancelar</button>
            <button
              type="button"
              class="btn-primary"
              :disabled="!newEntry.message.trim()"
              @click="submitEntry"
            >
              <Plus :size="14" />
              Registrar entrada
            </button>
          </div>
        </div>
      </section>
    </transition>

    <!-- Barra de herramientas: Búsqueda + Filtros -->
    <section class="toolbar-section">
      <div class="search-input-wrapper">
        <Search :size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="Buscar por texto, autor, cuba..."
        />
        <button
          v-if="searchQuery"
          type="button"
          class="clear-search-btn"
          @click="searchQuery = ''"
        >
          ×
        </button>
      </div>

      <div class="filter-pills">
        <button
          type="button"
          class="pill-btn"
          :class="{ active: activeFilter === 'todos' }"
          @click="activeFilter = 'todos'"
        >
          Todos ({{ filterCounts.all }})
        </button>
        <button
          type="button"
          class="pill-btn pill-nota"
          :class="{ active: activeFilter === 'nota' }"
          @click="activeFilter = 'nota'"
        >
          <FileText :size="13" />
          {{ filterCounts.nota }}
        </button>
        <button
          type="button"
          class="pill-btn pill-alerta"
          :class="{ active: activeFilter === 'alerta' }"
          @click="activeFilter = 'alerta'"
        >
          <AlertTriangle :size="13" />
          {{ filterCounts.alerta }}
        </button>
        <button
          type="button"
          class="pill-btn pill-config"
          :class="{ active: activeFilter === 'config' }"
          @click="activeFilter = 'config'"
        >
          <Settings :size="13" />
          {{ filterCounts.config }}
        </button>
        <button
          type="button"
          class="pill-btn pill-lectura"
          :class="{ active: activeFilter === 'lectura' }"
          @click="activeFilter = 'lectura'"
        >
          <Thermometer :size="13" />
          {{ filterCounts.lectura }}
        </button>
      </div>
    </section>

    <!-- Timeline -->
    <section class="timeline-section">
      <template v-if="groupedEntries.length">
        <div v-for="group in groupedEntries" :key="group.label" class="timeline-group">
          <!-- Separador de día -->
          <div class="day-separator">
            <Clock :size="14" />
            <span>{{ group.label }}</span>
            <span class="day-count">{{ group.entries.length }}</span>
          </div>

          <!-- Línea del timeline -->
          <div class="timeline-track">
            <div
              v-for="entry in group.entries"
              :key="entry.id"
              class="timeline-entry"
              :class="entryTypes[entry.type].colorClass"
            >
              <!-- Nodo del timeline -->
              <div class="entry-node" :class="entryTypes[entry.type].colorClass">
                <component :is="entryTypes[entry.type].icon" :size="14" />
              </div>

              <!-- Contenido -->
              <div class="entry-card">
                <div class="entry-meta">
                  <span class="entry-time">{{ formatTime(entry.timestamp) }}</span>
                  <span class="entry-cuba-badge">
                    <Cylinder :size="12" />
                    {{ getCubaLabel(entry.cuba) }}
                  </span>
                  <span class="entry-author">
                    <User :size="12" />
                    {{ entry.author }}
                  </span>
                </div>
                <p class="entry-message">{{ entry.message }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Estado vacío -->
      <div v-else class="empty-state">
        <FileText :size="40" />
        <h3>Sin resultados</h3>
        <p>No hay entradas que coincidan con los filtros actuales.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* =========================================
   BITÁCORA - LAYOUT GENERAL
   ========================================= */
.binnacle-page {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* =========================================
   ENCABEZADO
   ========================================= */
.binnacle-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.header-pretitle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.73rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.3rem;
}

.header-title {
  font-family: var(--font-serif);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.15;
  letter-spacing: -0.01em;
}

.header-description {
  font-size: 0.88rem;
  color: var(--text-secondary);
  margin-top: 0.35rem;
}

.header-actions {
  flex-shrink: 0;
  padding-top: 0.5rem;
}

.btn-new-entry {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background-color: var(--wine-700);
  color: #FFFFFF;
  padding: 0.55rem 1.15rem;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 600;
  transition: background-color 0.15s ease, transform 0.1s ease;
}

.btn-new-entry:hover {
  background-color: var(--wine-800);
  transform: translateY(-1px);
}

/* =========================================
   FORMULARIO RÁPIDO
   ========================================= */
.form-slide-enter-active,
.form-slide-leave-active {
  transition: all 0.25s ease;
}
.form-slide-enter-from,
.form-slide-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}

.form-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.form-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
  background-color: var(--bg-subtle);
}

.form-card-header h3 {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--wine-800);
}

.form-close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all 0.12s ease;
}

.form-close-btn:hover {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.form-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row-trio {
  display: grid;
  grid-template-columns: auto 1fr 1fr;
  gap: 1rem;
  align-items: flex-start;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.form-type-pills {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.65rem;
  border-radius: var(--radius-full);
  font-size: 0.76rem;
  font-weight: 600;
  border: 1px solid var(--border-color);
  background-color: var(--bg-canvas);
  color: var(--text-secondary);
  transition: all 0.12s ease;
}

.type-pill:hover {
  background-color: var(--bg-hover);
}

/* Nota */
.type-pill.type-nota.active {
  background-color: #EDF4FC;
  border-color: #B8D4F0;
  color: #1A5296;
}

/* Alerta */
.type-pill.type-alerta.active {
  background-color: var(--status-warn-bg);
  border-color: var(--status-warn-border);
  color: var(--status-warn);
}

/* Config */
.type-pill.type-config.active {
  background-color: #F0ECF8;
  border-color: #D0C4E8;
  color: #5B3EA6;
}

/* Lectura */
.type-pill.type-lectura.active {
  background-color: var(--status-good-bg);
  border-color: var(--status-good-border);
  color: var(--status-good);
}

.form-select {
  height: 36px;
  padding: 0 0.75rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.82rem;
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s ease;
  cursor: pointer;
}

.form-select:focus {
  border-color: var(--wine-600);
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.08);
}

.form-textarea {
  width: 100%;
  padding: 0.65rem 0.85rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.85rem;
  color: var(--text-primary);
  outline: none;
  resize: vertical;
  min-height: 72px;
  transition: border-color 0.15s ease;
  line-height: 1.5;
}

.form-textarea:focus {
  border-color: var(--wine-600);
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.08);
  background-color: #FFFFFF;
}

.form-textarea::placeholder {
  color: var(--text-light);
}

.form-hint {
  font-size: 0.7rem;
  color: var(--text-light);
  text-align: right;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  padding-top: 0.25rem;
}

/* =========================================
   BARRA DE HERRAMIENTAS
   ========================================= */
.toolbar-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  padding: 0.7rem 1rem;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-subtle);
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 200px;
  max-width: 320px;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 36px;
  padding: 0 2rem 0 2.2rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.82rem;
  color: var(--text-primary);
  outline: none;
  transition: all 0.15s ease;
}

.search-input:focus {
  border-color: var(--wine-600);
  background-color: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.08);
}

.clear-search-btn {
  position: absolute;
  right: 0.65rem;
  font-size: 1.1rem;
  color: var(--text-muted);
  line-height: 1;
}

.filter-pills {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.7rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all 0.12s ease;
  cursor: pointer;
}

.pill-btn:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.pill-btn.active {
  background-color: var(--wine-700);
  border-color: var(--wine-700);
  color: #FFFFFF;
}

/* Colores activos de pills por tipo */
.pill-btn.pill-nota.active {
  background-color: #1A5296;
  border-color: #1A5296;
}

.pill-btn.pill-alerta.active {
  background-color: var(--status-warn);
  border-color: var(--status-warn);
}

.pill-btn.pill-config.active {
  background-color: #5B3EA6;
  border-color: #5B3EA6;
}

.pill-btn.pill-lectura.active {
  background-color: var(--status-good);
  border-color: var(--status-good);
}

/* =========================================
   TIMELINE
   ========================================= */
.timeline-section {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.timeline-group {
  display: flex;
  flex-direction: column;
}

/* Separador de día */
.day-separator {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.65rem 0.5rem;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.day-count {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--text-muted);
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  padding: 0.1rem 0.45rem;
  border-radius: var(--radius-full);
  margin-left: auto;
}

/* Track vertical */
.timeline-track {
  display: flex;
  flex-direction: column;
  position: relative;
  padding-left: 1.6rem;
  margin-left: 0.85rem;
}

.timeline-track::before {
  content: '';
  position: absolute;
  left: 0.85rem;
  top: 0;
  bottom: 0;
  width: 2px;
  background-color: var(--border-color);
  border-radius: 1px;
}

/* Cada entrada */
.timeline-entry {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  position: relative;
  padding: 0.5rem 0;
}

/* Nodo circular */
.entry-node {
  position: absolute;
  left: -1.6rem;
  top: 0.65rem;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: 1;
  border: 2px solid var(--bg-canvas);
  transform: translateX(-50%);
  left: -0.75rem;
}

.entry-node.type-nota {
  background-color: #EDF4FC;
  color: #1A5296;
}

.entry-node.type-alerta {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.entry-node.type-config {
  background-color: #F0ECF8;
  color: #5B3EA6;
}

.entry-node.type-lectura {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

/* Tarjeta de contenido */
.entry-card {
  flex: 1;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0.75rem 1rem;
  transition: all 0.15s ease;
  box-shadow: var(--shadow-subtle);
}

.entry-card:hover {
  border-color: var(--text-light);
  box-shadow: var(--shadow-card);
}

/* Borde izquierdo de color por tipo */
.timeline-entry.type-nota .entry-card {
  border-left: 3px solid #B8D4F0;
}

.timeline-entry.type-alerta .entry-card {
  border-left: 3px solid var(--status-warn-border);
}

.timeline-entry.type-config .entry-card {
  border-left: 3px solid #D0C4E8;
}

.timeline-entry.type-lectura .entry-card {
  border-left: 3px solid var(--status-good-border);
}

/* Meta de la entrada */
.entry-meta {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 0.4rem;
  flex-wrap: wrap;
}

.entry-time {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.entry-cuba-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--wine-700);
  background-color: var(--wine-50);
  border: 1px solid var(--wine-100);
  padding: 0.1rem 0.5rem;
  border-radius: var(--radius-full);
}

.entry-author {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

/* Mensaje */
.entry-message {
  font-size: 0.86rem;
  line-height: 1.55;
  color: var(--text-primary);
}

/* =========================================
   ESTADO VACÍO
   ========================================= */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
  color: var(--text-muted);
  background-color: var(--bg-surface);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
}

.empty-state h3 {
  font-family: var(--font-serif);
  font-size: 1.3rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 1rem;
  margin-bottom: 0.3rem;
}

.empty-state p {
  font-size: 0.86rem;
  max-width: 360px;
}

/* =========================================
   RESPONSIVE
   ========================================= */
@media (max-width: 680px) {
  .binnacle-header {
    flex-direction: column;
  }

  .header-actions {
    padding-top: 0;
  }

  .form-row-trio {
    grid-template-columns: 1fr;
  }

  .toolbar-section {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input-wrapper {
    max-width: 100%;
  }

  .filter-pills {
    justify-content: flex-start;
  }

  .entry-meta {
    gap: 0.4rem;
  }
}
</style>
