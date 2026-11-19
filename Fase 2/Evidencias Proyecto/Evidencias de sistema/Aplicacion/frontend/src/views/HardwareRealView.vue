<script setup>
import { ref, onBeforeUnmount } from 'vue'

import { readHardwareReport } from './readHardwareReport.js'

const supported = Boolean(navigator.serial)
const state = ref('idle')
const notice = ref('')
const cards = ref([])
let expiry
const lastRead = ref('')
let reader
let disposed = false

async function connect() {
  state.value = 'opening'
  notice.value = ''
  let port
  let opened = false
  try {
    port = await navigator.serial.requestPort()
    if (disposed) return
    await port.open({ baudRate: 115200 })
    opened = true
    if (disposed) return
    reader = port.readable.getReader()
    cards.value = []
    let buffer = ''
    lastRead.value = ''
    state.value = 'reading'
    const decoder = new TextDecoder()
    while (!disposed) {
      const { value, done } = await reader.read()
      if (done) break
      buffer = (buffer + decoder.decode(value, { stream: true })).slice(-32000)
      const end = 'MOSTO | FIN DEL REPORTE'
      const finish = buffer.lastIndexOf(end)
      if (finish < 0) continue
      const start = buffer.lastIndexOf('MOSTO | REPORTE DE MEDICION', finish)
      if (start >= 0) {
        cards.value = readHardwareReport(buffer.slice(start, finish))
        lastRead.value = new Date().toLocaleTimeString()
        clearTimeout(expiry)
        expiry = setTimeout(() => { cards.value = []; lastRead.value = '' }, 12000)
      }
      buffer = buffer.slice(finish + end.length)
    }
  } catch (error) {
    if (error.name !== 'NotFoundError') notice.value = 'Conexión interrumpida. Revisa el cable y cierra el monitor serie de Arduino antes de reintentar.'
  } finally {
    clearTimeout(expiry)
    cards.value = []
    lastRead.value = ''
    reader?.releaseLock()
    reader = null
    if (opened) await port.close().catch(() => {})
    state.value = 'idle'
  }
}

function disconnect() {
  state.value = 'closing'
  reader?.cancel().catch(() => {})
}
onBeforeUnmount(() => { disposed = true; disconnect() })
</script>

<template>
  <section>
    <h1>Hardware real</h1>

    <p v-if="!supported">Abre esta página en Chrome o Edge desde localhost o HTTPS para acceder al puerto USB.</p>
    <button v-else-if="state === 'idle'" @click="connect">Conectar ESP32 por USB</button>
    <button v-else :disabled="state !== 'reading'" @click="disconnect">Desconectar</button>
    <p role="status">{{ notice || ({idle:'Desconectado',opening:'Abriendo puerto…',reading:'ESP32 conectado',closing:'Cerrando puerto…'})[state] }}</p>
    <p v-if="lastRead">Últimos datos recibidos a las {{ lastRead }}</p>
    <p v-if="state === 'reading' && !cards.length" role="status">{{ lastRead ? 'Sin sensores con lectura válida.' : 'Esperando lecturas…' }}</p>
    <div class="sensors">
      <article v-for="card in cards" :key="card.sensor">
        <small>{{ card.sensor }}</small>
        <h2>{{ card.label }}</h2>
        <strong>{{ card.value }}</strong>
      </article>
    </div>
  </section>
</template>

<style scoped>
button { padding: .65rem 1rem; cursor: pointer; }
.sensors { display: flex; flex-wrap: wrap; gap: 1rem; }
article { padding: 1rem 1.25rem; border: 1px solid #d5e2db; border-radius: .8rem; background: white; }
article h2 { font-size: 1rem; margin: .35rem 0; }
article strong { font-size: 1.8rem; color: #15593d; }
</style>
