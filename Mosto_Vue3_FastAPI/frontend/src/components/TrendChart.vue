<script setup>
import { computed } from 'vue'
const props=defineProps({readings:{type:Array,default:()=>[]},metric:{type:String,default:'temp_mosto'},lower:{type:Number,default:null},upper:{type:Number,default:null},height:{type:Number,default:215}})
const values=computed(()=>props.readings.filter(r=>r.lectura_valida!==false && typeof r[props.metric]==='number').slice(-48))
const bounds=computed(()=>{
 const nums=values.value.map(r=>r[props.metric]);if(props.lower!==null)nums.push(props.lower);if(props.upper!==null)nums.push(props.upper)
 let min=Math.min(...nums),max=Math.max(...nums);if(!nums.length||!isFinite(min)){min=0;max=1}const pad=Math.max((max-min)*.18,.15);return {min:min-pad,max:max+pad}
})
const y=v=>190-(v-bounds.value.min)/(bounds.value.max-bounds.value.min)*165
const x=i=>50+i/Math.max(1,values.value.length-1)*665
const coords=computed(()=>values.value.map((v,i)=>[x(i),y(v[props.metric])]))
const line=computed(()=>coords.value.map((p,i)=>`${i?'L':'M'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' '))
const fill=computed(()=>coords.value.length?line.value+` L ${coords.value.at(-1)[0]} 190 L ${coords.value[0][0]} 190 Z`:'' )
const ticks=computed(()=>Array.from({length:4},(_,i)=>bounds.value.min+(bounds.value.max-bounds.value.min)*(3-i)/3))
const fmt=v=>Number(v).toLocaleString('es-CL',{maximumFractionDigits:1})
const dateLabel=s=>new Date(s).toLocaleTimeString('es-CL',{hour:'2-digit',minute:'2-digit'})
</script>
<template>
  <div v-if="!values.length" class="chart-empty"><div class="chart-empty-symbol">∿</div><strong>Sin datos registrados</strong><small>Las mediciones aparecerán cuando el dispositivo envíe lecturas válidas.</small></div>
  <div v-else class="chart-wrapper">
    <svg viewBox="0 0 750 220" role="img" :aria-label="`Gráfico de ${metric} con ${values.length} lecturas`" preserveAspectRatio="none" class="trend-svg">
      <defs><linearGradient id="mosto-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#8d5567" stop-opacity=".18"/><stop offset="100%" stop-color="#8d5567" stop-opacity=".008"/></linearGradient></defs>
      <g v-for="(t,i) in ticks" :key="i"><line x1="50" x2="715" :y1="y(t)" :y2="y(t)" stroke="#e8e4e0" stroke-dasharray="3 5"/><text x="1" :y="y(t)+4" font-size="11" fill="#928a88">{{fmt(t)}}</text></g>
      <template v-if="lower!==null"><line x1="50" x2="715" :y1="y(lower)" :y2="y(lower)" stroke="#ac9460" stroke-dasharray="6 5" stroke-width="1.2"/></template>
      <template v-if="upper!==null"><line x1="50" x2="715" :y1="y(upper)" :y2="y(upper)" stroke="#ac9460" stroke-dasharray="6 5" stroke-width="1.2"/></template>
      <path :d="fill" fill="url(#mosto-fill)"/><path :d="line" fill="none" stroke="#7a394d" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
      <circle v-if="coords.length" :cx="coords.at(-1)[0]" :cy="coords.at(-1)[1]" r="5" fill="#7a394d" stroke="#fff" stroke-width="2.5"/>
      <text x="50" y="213" font-size="11" fill="#928a88">{{dateLabel(values[0].timestamp)}}</text><text x="665" y="213" font-size="11" fill="#928a88">{{dateLabel(values.at(-1).timestamp)}}</text>
    </svg>
  </div>
</template>
