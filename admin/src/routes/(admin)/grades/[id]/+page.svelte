<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from 'svelte-sonner';

  let gradeId=$derived($page.params.id); let isNew=$derived(gradeId==='new');
  let form=$state({code:'',name:'',product_id:0,is_active:true});
  let products=$state<{product_id:number;name:string}[]>([]);
  let loading=$state(false); let error=$state('');

  onMount(async()=>{
    try{const d=await api.get<any>('/products?page_size=100');products=d.items||[]}catch{}
    if(!isNew){try{const g=await api.get<any>(`/grades/${gradeId}`);form={code:g.code,name:g.name,product_id:g.product_id,is_active:g.is_active}}catch(e:any){error=e.message}}
  });

  async function handleSubmit(e:Event){e.preventDefault();loading=true;error='';
    try{const body:any={name:form.name,product_id:form.product_id,is_active:form.is_active};
      if(isNew){body.code=form.code;await api.post('/grades',body);toast.success('Grado creado')}
      else{await api.put(`/grades/${gradeId}`,body);toast.success('Grado actualizado')}
      goto('/grades')}catch(e:any){error=e.message;toast.error(e.message)}finally{loading=false}
  }
</script>
<div>
  <div class="flex items-center gap-4 mb-6"><button onclick={()=>goto('/grades')} class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"><ArrowLeft class="w-5 h-5"/></button><h1 class="text-2xl font-bold text-gray-900">{isNew?'Nuevo Grado':'Editar Grado'}</h1></div>
  {#if error}<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>{/if}
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-2xl">
    <form onsubmit={handleSubmit} class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Código <span class="text-red-500">*</span></label><input type="text" bind:value={form.code} required disabled={!isNew} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Nombre <span class="text-red-500">*</span></label><input type="text" bind:value={form.name} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Producto <span class="text-red-500">*</span></label><select bind:value={form.product_id} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"><option value={0}>Seleccionar...</option>{#each products as p}<option value={p.product_id}>{p.name} ({p.code})</option>{/each}</select></div>
        <div class="space-y-1 flex items-end pb-1"><label class="inline-flex items-center gap-2 cursor-pointer"><input type="checkbox" bind:checked={form.is_active} class="w-4 h-4 text-primary-500 border-gray-300 rounded"/><span class="text-sm text-gray-700">Activo</span></label></div>
      </div>
      <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <button type="button" onclick={()=>goto('/grades')} class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancelar</button>
        <button type="submit" disabled={loading} class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"><Save class="w-4 h-4"/>{loading?'Guardando...':'Guardar'}</button>
      </div>
    </form>
  </div>
</div>
