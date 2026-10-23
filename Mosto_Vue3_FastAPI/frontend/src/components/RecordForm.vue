<script setup>
import { reactive, watch } from 'vue'
import { X } from 'lucide-vue-next'
const props=defineProps({title:String,description:String,fields:Array,submitLabel:{type:String,default:'Guardar registro'},busy:Boolean})
const emit=defineEmits(['close','submit'])
const model=reactive({})
watch(()=>props.fields,fields=>{Object.keys(model).forEach(k=>delete model[k]);for(const f of fields||[])model[f.key]=f.default??(f.type==='checkbox'?false:'')},{immediate:true})
function submit(){const payload={};for(const f of props.fields) {const v=model[f.key];payload[f.key]=f.type==='number'?(v===''?null:Number(v)):f.type==='checkbox'?Boolean(v):v}emit('submit',payload)}
</script>
<template><div class="modal-scrim" @click.self="emit('close')"><form class="dialog" @submit.prevent="submit">
  <div class="dialog-header"><div><div class="overline">MOSTO · GESTIÓN</div><h2>{{title}}</h2><p>{{description}}</p></div><button type="button" class="icon-button" @click="emit('close')" aria-label="Cerrar"><X :size="19"/></button></div>
  <div class="dialog-fields"><label v-for="f in fields" :key="f.key" class="field-label" :class="{'wide':f.wide}">{{f.label}}<span v-if="f.required" class="req"> *</span>
    <select v-if="f.type==='select'" v-model="model[f.key]" :required="f.required"><option value="" disabled>Seleccionar opción</option><option v-for="opt in f.options||[]" :key="opt.value" :value="opt.value">{{opt.label}}</option></select>
    <textarea v-else-if="f.type==='textarea'" v-model="model[f.key]" :required="f.required" rows="3" :placeholder="f.placeholder||''"/>
    <div v-else-if="f.type==='checkbox'" class="checkbox-field"><input type="checkbox" v-model="model[f.key]"/><span>Activo</span></div>
    <input v-else :type="f.type||'text'" v-model="model[f.key]" :required="f.required" :min="f.min" :max="f.max" :step="f.step||'any'" :placeholder="f.placeholder||''"/>
    <small v-if="f.hint">{{f.hint}}</small>
  </label></div>
  <div class="dialog-footer"><button type="button" class="btn-outline" @click="emit('close')">Cancelar</button><button type="submit" class="btn-primary" :disabled="busy">{{busy?'Guardando…':submitLabel}}</button></div>
</form></div></template>
