<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save, Plus, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  let plId=$derived($page.params.id); let isNew=$derived(plId==='new');
  let form=$state({code:'',name:'',is_default:false,is_active:true});
  let items=$state<{price_list_item_id:number;product_id:number;product_name:string;unit_price:number;is_active:boolean}[]>([]);
  let products=$state<{product_id:number;name:string}[]>([]);
  let loading=$state(false); let error=$state('');
  let newItem=$state({product_id:0,unit_price:0});
  let savingItem=$state(false);

  onMount(async()=>{
    try{const d=await api.get<any>('/products?page_size=100');products=d.items||[]}catch{}
    if(!isNew){try{const r=await api.get<any>(`/price-lists/${plId}`);form={code:r.code,name:r.name,is_default:r.is_default,is_active:r.is_active};items=r.items||[]}catch(e:any){error=e.message}}
  });

  async function handleSubmit(e:Event){e.preventDefault();loading=true;error='';
    try{const body:any={name:form.name,is_default:form.is_default,is_active:form.is_active};
      if(isNew){body.code=form.code;await api.post('/price-lists',body);toast.success('Lista creada')}
      else{await api.put(`/price-lists/${plId}`,body);toast.success('Lista actualizada')}
      goto('/price-lists')}catch(e:any){error=e.message;toast.error(e.message)}finally{loading=false}
  }

  async function addItem(){if(!newItem.product_id||newItem.unit_price<=0)return;savingItem=true;
    try{const r=await api.post<any>(`/price-lists/${plId}/items`,{product_id:newItem.product_id,unit_price:newItem.unit_price});items=[...items,r];newItem={product_id:0,unit_price:0};toast.success('Item agregado')}catch(e:any){toast.error(e.message)}finally{savingItem=false}}

  async function removeItem(itemId:number){try{await api.delete(`/price-lists/${plId}/items/${itemId}`);items=items.filter(i=>i.price_list_item_id!==itemId);toast.success('Item removido')}catch(e:any){toast.error(e.message)}}
</script>

<div>
  <div class="flex items-center gap-4 mb-6"><button onclick={()=>goto('/price-lists')} class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"><ArrowLeft class="w-5 h-5"/></button><h1 class="text-2xl font-bold text-gray-900">{isNew?'Nueva Lista':'Editar Lista'}</h1></div>
  {#if error}<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>{/if}
  <div class="space-y-6">
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-2xl">
      <form onsubmit={handleSubmit} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Código <span class="text-red-500">*</span></label><input type="text" bind:value={form.code} required disabled={!isNew} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Nombre <span class="text-red-500">*</span></label><input type="text" bind:value={form.name} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1 flex items-end pb-1"><label class="inline-flex items-center gap-2 cursor-pointer"><input type="checkbox" bind:checked={form.is_default} class="w-4 h-4 text-primary-500 border-gray-300 rounded"/><span class="text-sm text-gray-700">Default</span></label></div>
          <div class="space-y-1 flex items-end pb-1"><label class="inline-flex items-center gap-2 cursor-pointer"><input type="checkbox" bind:checked={form.is_active} class="w-4 h-4 text-primary-500 border-gray-300 rounded"/><span class="text-sm text-gray-700">Activo</span></label></div>
        </div>
        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button type="button" onclick={()=>goto('/price-lists')} class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancelar</button>
          <button type="submit" disabled={loading} class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"><Save class="w-4 h-4"/>{loading?'Guardando...':'Guardar'}</button>
        </div>
      </form>
    </div>

    {#if !isNew}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Items de Precio</h3>
        <div class="flex gap-2 mb-4">
          <select bind:value={newItem.product_id} class="px-3 py-2 text-sm border border-gray-300 rounded-md flex-1"><option value={0}>Producto...</option>{#each products as p}<option value={p.product_id}>{p.name}</option>{/each}</select>
          <input type="number" step="0.0001" bind:value={newItem.unit_price} placeholder="Precio" class="w-32 px-3 py-2 text-sm border border-gray-300 rounded-md"/>
          <button onclick={addItem} disabled={savingItem} class="inline-flex items-center gap-1 px-3 py-2 bg-primary-500 text-white text-sm rounded-lg hover:bg-primary-600"><Plus class="w-4 h-4"/>Agregar</button>
        </div>
        {#if items.length > 0}
          <div class="divide-y divide-gray-100">
            {#each items as it}
              <div class="flex items-center justify-between py-2"><span class="text-sm text-gray-700">{it.product_name}</span><div class="flex items-center gap-3"><span class="text-sm font-mono font-medium">${it.unit_price.toFixed(4)}</span><button class="p-1 text-gray-400 hover:text-red-600 rounded" onclick={()=>removeItem(it.price_list_item_id)}><Trash2 class="w-3.5 h-3.5"/></button></div></div>
            {/each}
          </div>
        {:else}
          <p class="text-sm text-gray-500 py-4 text-center">Sin items. Agregue productos con sus precios.</p>
        {/if}
      </div>
    {/if}
  </div>
</div>
