<script setup>
defineProps({
  id: { type: [String, Number], required: true },
  nivel: { type: Number, default: null }
})
const altura = porcentaje => Math.min(100, porcentaje) * 1.04
</script>

<template>
  <svg viewBox="0 0 120 145" aria-hidden="true" focusable="false">
          <defs>
            <clipPath :id="'vessel-' + id"><path d="M24 34 Q60 9 96 34 V103 Q93 111 60 123 Q27 111 24 103Z" /></clipPath>
            <pattern :id="'hatch-' + id" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M-1 1L1 -1M0 5L5 0M4 6L6 4" stroke="#edb7a0" stroke-opacity=".33" stroke-width=".8"/></pattern>
          </defs>
          <g fill="none" stroke="#d8b6ab" stroke-width="1.5" stroke-linejoin="round">
            <path d="M30 108v24h4l3-20m46 0 3 20h4v-24M56 122v6h10v-4h5" />
            <path d="M52 20v-5h16v5M49 15h22M59 15V9h8" />
            <path d="M24 34 Q60 9 96 34 V103 Q93 111 60 123 Q27 111 24 103Z" fill="#3d2834" />
            <g v-if="nivel != null && nivel > 0" :clip-path="'url(#vessel-' + id + ')'">
              <rect x="25" :y="123 - altura(nivel)" width="70" :height="altura(nivel)" fill="#935369" stroke="none" />
              <rect x="25" :y="123 - altura(nivel)" width="70" :height="altura(nivel)" :fill="'url(#hatch-' + id + ')'" stroke="none" />
              <path :d="'M24 ' + (123 - altura(nivel)) + 'h72'" stroke="#f4b9a9"/>
            </g>
            <path d="M24 34q36 9 72 0M24 102q36 10 72 0" />
            <path d="M29 41v52m62-52v52" stroke-opacity=".38"/>
            <path d="M96 48h4v41h-4m4-35h3m-3 8h3m-3 8h3m-3 8h3" stroke-width="1"/>
            <path d="M17 133h87" stroke="#aa828d" stroke-opacity=".55"/>
          </g>
        </svg>
</template>
