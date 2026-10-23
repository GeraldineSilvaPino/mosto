const API_ROOT = import.meta.env.VITE_API_BASE || '/api'
let token = sessionStorage.getItem('mosto_access_token') || ''
export const auth = { get token(){return token}, setToken(v){token=v||'';if(token) sessionStorage.setItem('mosto_access_token',token);else sessionStorage.removeItem('mosto_access_token')} }
export async function api(path,opts={}){
 const headers={...(opts.headers||{})};
 if(token) headers.Authorization=`Bearer ${token}`
 if(opts.body !== undefined && !(opts.body instanceof FormData)) headers['Content-Type']='application/json'
 const response=await fetch(`${API_ROOT}${path}`, {...opts, headers, body:opts.body===undefined?undefined:JSON.stringify(opts.body)})
 if(!response.ok){let msg=`Error HTTP ${response.status}`;try{const d=await response.json();msg=typeof d.detail==='string'?d.detail:msg}catch{}throw new Error(msg)}
 if(response.headers.get('content-type')?.includes('text/csv')) return response.blob()
 return response.json()
}
export async function downloadCsv(fid){const csv=await api(`/exportaciones/lecturas.csv?fermentacion_id=${fid}`);const url=URL.createObjectURL(csv);const a=document.createElement('a');a.href=url;a.download=`mosto-fermentacion-${fid}.csv`;a.click();URL.revokeObjectURL(url)}
