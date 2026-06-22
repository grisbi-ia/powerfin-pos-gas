<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  let epId=$derived($page.params.id); let isNew=$derived(epId==='new');
  let form=$state({establishment:'',emission_point:'',doc_type:'FACTURA',sequential_start:1,sequential_end:9999,current_sequential:1,is_active:true});
  let loading=$state(false); let error=$state('');

  onMount(async()=>{if(!isNew){try{const r=await api.get<any>(`/emission-points/${epId}`);form={establishment:r.establishment,emission_point:r.emission_point,doc_type:r.doc_type,sequential_start:r.sequential_start,sequential_end:r.sequential_end,current_sequential:r.current_sequential,is_active:r.is_active}}catch(e:any){error=e.message}}});

  async function handleSubmit(e:Event){e.preventDefault();loading=true;error='';
    try{const body:any={doc_type:form.doc_type,sequential_start:form.sequential_start,sequential_end:form.sequential_end,current_sequential:form.current_sequential,is_active:form.is_active};
      if(isNew){body.establishment=form.establishment;body.emission_point=form.emission_point;await api.post('/emission-points',body);toast.success('Punto creado')}
      else{await api.put(`/emission-points/${epId}`,body);toast.success('Punto actualizado')}
      goto('/emission-points')}catch(e:any){error=e.message;toast.error(e.message)}finally{loading=false}
  }
</script>
<div>
  <div class="flex items-center gap-4 mb-6"><button onclick={()=>goto('/emission-points')} class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"><ArrowLeft class="w-5 h-5"/></button><h1 class="text-2xl font-bold text-gray-900">{isNew?'Nuevo Punto':'Editar Punto'}</h1></div>
  {#if error}<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>{/if}
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-2xl">
    <form onsubmit={handleSubmit} class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Establecimiento <span class="text-red-500">*</span></label><input type="text" bind:value={form.establishment} required disabled={!isNew} maxlength={3} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md disabled:bg-gray-100 font-mono"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Punto Emisión <span class="text-red-500">*</span></label><input type="text" bind:value={form.emission_point} required disabled={!isNew} maxlength={3} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md disabled:bg-gray-100 font-mono"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Tipo Documento</label><select bind:value={form.doc_type} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"><option>FACTURA</option><option>NOTA_CREDITO</option><option>NOTA_DEBITO</option><option>GUIA_REMISION</option><option>COMPROBANTE_RETENCION</option></select></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Secuencial Actual</label><input type="number" bind:value={form.current_sequential} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Secuencial Inicio</label><input type="number" bind:value={form.sequential_start} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Secuencial Fin</label><input type="number" bind:value={form.sequential_end} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"/></div>
        <div class="space-y-1 flex items-end pb-1"><label class="inline-flex items-center gap-2 cursor-pointer"><input type="checkbox" bind:checked={form.is_active} class="w-4 h-4 text-primary-500 border-gray-300 rounded"/><span class="text-sm text-gray-700">Activo</span></label></div>
      </div>
      <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <button type="button" onclick={()=>goto('/emission-points')} class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancelar</button>
        <button type="submit" disabled={loading} class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"><Save class="w-4 h-4"/>{loading?'Guardando...':'Guardar'}</button>
      </div>
    </form>
  </div>
</div>
