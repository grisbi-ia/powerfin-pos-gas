<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save, Plus, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  let dispId=$derived($page.params.id); let isNew=$derived(dispId==='new');
  let form=$state({code:'',name:'',emission_point_id:null as number|null,printer_ip:'',printer_port:9100,sort_order:0,is_active:true});
  let hoses=$state<{hose_id:number;side:string;fusion_pump_id:number;fusion_hose_id:number;grade_code:string;grade_name:string;is_active:boolean}[]>([]);
  let meters=$state<{meter_id:number;name:string;meter_type:string;grade_id:number|null;grade_code:string|null;grade_name:string|null;hose_id:number|null;hose_side:string|null;sort_order:number;is_active:boolean}[]>([]);
  let emissionPoints=$state<{emission_point_id:number;label:string}[]>([]);
  let grades=$state<{grade_id:number;code:string;name:string}[]>([]);
  let allHoses=$state<{hose_id:number;side:string;grade_code:string;grade_name:string;is_active:boolean}[]>([]);
  let loading=$state(false); let error=$state('');
  let newHose=$state({side:'A',fusion_pump_id:0,fusion_hose_id:0,grade_code:''});
  let savingHose=$state(false);
  let newMeter=$state({name:'',meter_type:'PRODUCT' as 'PRODUCT'|'HOSE',grade_id:null as number|null,hose_id:null as number|null});
  let savingMeter=$state(false);

  $effect(() => { (async () => {
    try{const d=await api.get<any>('/emission-points?page_size=100');emissionPoints=(d.items||[]).map((e:any)=>({emission_point_id:e.emission_point_id,label:e.label}))}catch{}
    try{const g=await api.get<any>('/grades?page_size=100');grades=(g.items||[]).map((e:any)=>({grade_id:e.grade_id,code:e.code,name:e.name}))}catch{}
    if(!isNew){try{const r=await api.get<any>(`/dispensers/${dispId}`);form={code:r.code,name:r.name,emission_point_id:r.emission_point_id,printer_ip:r.printer_ip||'',printer_port:r.printer_port,sort_order:r.sort_order,is_active:r.is_active};hoses=r.hoses||[];meters=r.mechanical_meters||[];allHoses=r.hoses||[]}catch(e:any){error=e.message}}
  })();
});

  async function handleSubmit(e:Event){e.preventDefault();loading=true;error='';
    try{const body:any={name:form.name,emission_point_id:form.emission_point_id,printer_ip:form.printer_ip||null,printer_port:form.printer_port,sort_order:form.sort_order,is_active:form.is_active};
      if(isNew){body.code=form.code;await api.post('/dispensers',body);toast.success('Surtidor creado')}
      else{await api.put(`/dispensers/${dispId}`,body);toast.success('Surtidor actualizado')}
      goto('/dispensers')}catch(e:any){error=e.message;toast.error(e.message)}finally{loading=false}
  }

  async function addHose(){if(!newHose.fusion_pump_id||!newHose.grade_code)return;savingHose=true;
    try{const r=await api.post<any>(`/dispensers/${dispId}/hoses`,newHose);hoses=[...hoses,r];newHose={side:'A',fusion_pump_id:0,fusion_hose_id:0,grade_code:''};toast.success('Manguera agregada')}catch(e:any){toast.error(e.message)}finally{savingHose=false}}

  async function addMeter(){if(!newMeter.name||(newMeter.meter_type==='PRODUCT'&&!newMeter.grade_id)||(newMeter.meter_type==='HOSE'&&!newMeter.hose_id))return;savingMeter=true;
    try{const body:any={name:newMeter.name,meter_type:newMeter.meter_type};
      if(newMeter.meter_type==='PRODUCT')body.grade_id=newMeter.grade_id;
      else body.hose_id=newMeter.hose_id;
      const r=await api.post<any>(`/dispensers/${dispId}/meters`,body);meters=[...meters,r];newMeter={name:'',meter_type:'PRODUCT',grade_id:null,hose_id:null};toast.success('Medidor agregado')}catch(e:any){toast.error(e.message)}finally{savingMeter=false}}

  async function deactivateMeter(meterId:number){try{await api.put(`/dispensers/${dispId}/meters/${meterId}`,{is_active:false});meters=meters.map(m=>m.meter_id===meterId?{...m,is_active:false}:m);toast.success('Medidor desactivado')}catch(e:any){toast.error(e.message)}}

  async function deactivateHose(hoseId:number){try{await api.put(`/dispensers/${dispId}/hoses/${hoseId}`,{is_active:false});hoses=hoses.map(h=>h.hose_id===hoseId?{...h,is_active:false}:h);toast.success('Manguera desactivada')}catch(e:any){toast.error(e.message)}}
</script>

<div>
  <div class="flex items-center gap-4 mb-6"><button onclick={()=>goto('/dispensers')} class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"><ArrowLeft class="w-5 h-5"/></button><h1 class="text-2xl font-bold text-gray-900">{isNew?'Nuevo Surtidor':'Editar Surtidor'}</h1></div>
  {#if error}<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>{/if}
  <div class="space-y-6">
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-2xl">
      <form onsubmit={handleSubmit} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Código <span class="text-red-500">*</span></label><input type="text" bind:value={form.code} required disabled={!isNew} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Nombre <span class="text-red-500">*</span></label><input type="text" bind:value={form.name} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Punto Emisión</label><select bind:value={form.emission_point_id} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"><option value={null}>--</option>{#each emissionPoints as ep}<option value={ep.emission_point_id}>{ep.label}</option>{/each}</select></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">IP Impresora</label><input type="text" bind:value={form.printer_ip} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Puerto Impresora</label><input type="number" bind:value={form.printer_port} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Orden</label><input type="number" bind:value={form.sort_order} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"/></div>
          <div class="space-y-1 flex items-end pb-1"><label class="inline-flex items-center gap-2 cursor-pointer"><input type="checkbox" bind:checked={form.is_active} class="w-4 h-4 text-primary-500 border-gray-300 rounded"/><span class="text-sm text-gray-700">Activo</span></label></div>
        </div>
        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button type="button" onclick={()=>goto('/dispensers')} class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancelar</button>
          <button type="submit" disabled={loading} class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"><Save class="w-4 h-4"/>{loading?'Guardando...':'Guardar'}</button>
        </div>
      </form>
    </div>

    {#if !isNew}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Mangueras</h3>
        <div class="flex flex-wrap gap-2 mb-4">
          <select bind:value={newHose.side} class="px-3 py-2 text-sm border border-gray-300 rounded-md"><option value="A">Lado A</option><option value="B">Lado B</option></select>
          <input type="number" bind:value={newHose.fusion_pump_id} placeholder="Pump ID" class="w-24 px-3 py-2 text-sm border border-gray-300 rounded-md"/>
          <input type="number" bind:value={newHose.fusion_hose_id} placeholder="Hose ID" class="w-24 px-3 py-2 text-sm border border-gray-300 rounded-md"/>
          <input type="text" bind:value={newHose.grade_code} placeholder="Grado (DIESEL)" class="w-32 px-3 py-2 text-sm border border-gray-300 rounded-md"/>
          <button onclick={addHose} disabled={savingHose} class="inline-flex items-center gap-1 px-3 py-2 bg-primary-500 text-white text-sm rounded-lg hover:bg-primary-600"><Plus class="w-4 h-4"/></button>
        </div>
        {#if hoses.length > 0}
          <div class="divide-y divide-gray-100">
            {#each hoses as h}
              <div class="flex items-center justify-between py-2">
                <div class="flex items-center gap-3"><span class="text-xs font-medium bg-gray-100 px-2 py-0.5 rounded">{h.side}</span><span class="text-sm text-gray-700">{h.grade_name} (Pump {h.fusion_pump_id})</span></div>
                <div class="flex items-center gap-3">
                  {#if h.is_active}<span class="text-xs text-green-600">Activo</span>{:else}<span class="text-xs text-red-500">Inactivo</span>{/if}
                  {#if h.is_active}<button class="p-1 text-gray-400 hover:text-red-600 rounded" onclick={()=>deactivateHose(h.hose_id)}><Trash2 class="w-3.5 h-3.5"/></button>{/if}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-sm text-gray-500 py-4 text-center">Sin mangueras. Agregue lados A/B con sus Fusion IDs.</p>
        {/if}
      </div>

      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Medidores Mecánicos</h3>
        <p class="text-sm text-gray-500 mb-4">Lecturas físicas del contador mecánico. Puede ser por producto (un medidor para todas las mangueras de ese combustible) o por manguera (un medidor por cada pistola).</p>
        <div class="flex flex-wrap gap-2 mb-4">
          <input type="text" bind:value={newMeter.name} placeholder="Nombre (ej: Medidor Súper)" class="w-56 px-3 py-2 text-sm border border-gray-300 rounded-md"/>
          <select bind:value={newMeter.meter_type} class="px-3 py-2 text-sm border border-gray-300 rounded-md">
            <option value="PRODUCT">Por Producto</option>
            <option value="HOSE">Por Manguera</option>
          </select>
          {#if newMeter.meter_type === 'PRODUCT'}
            <select bind:value={newMeter.grade_id} class="px-3 py-2 text-sm border border-gray-300 rounded-md">
              <option value={null}>-- Grado --</option>
              {#each grades as g}<option value={g.grade_id}>{g.name}</option>{/each}
            </select>
          {:else}
            <select bind:value={newMeter.hose_id} class="px-3 py-2 text-sm border border-gray-300 rounded-md">
              <option value={null}>-- Manguera --</option>
              {#each allHoses.filter(h=>h.is_active!==false) as h}<option value={h.hose_id}>Lado {h.side} — {h.grade_name}</option>{/each}
            </select>
          {/if}
          <button onclick={addMeter} disabled={savingMeter} class="inline-flex items-center gap-1 px-3 py-2 bg-primary-500 text-white text-sm rounded-lg hover:bg-primary-600"><Plus class="w-4 h-4"/></button>
        </div>
        {#if meters.length > 0}
          <div class="divide-y divide-gray-100">
            {#each meters as m}
              <div class="flex items-center justify-between py-2">
                <div class="flex items-center gap-3">
                  <span class="text-xs font-medium px-2 py-0.5 rounded {m.meter_type==='PRODUCT'?'bg-blue-100 text-blue-700':'bg-purple-100 text-purple-700'}">{m.meter_type==='PRODUCT'?'Producto':'Manguera'}</span>
                  <span class="text-sm text-gray-700">{m.name}</span>
                  {#if m.grade_name}<span class="text-xs text-gray-400">({m.grade_name})</span>{/if}
                  {#if m.hose_side}<span class="text-xs text-gray-400">Lado {m.hose_side}</span>{/if}
                </div>
                <div class="flex items-center gap-3">
                  {#if m.is_active}<span class="text-xs text-green-600">Activo</span>{:else}<span class="text-xs text-red-500">Inactivo</span>{/if}
                  {#if m.is_active}<button class="p-1 text-gray-400 hover:text-red-600 rounded" onclick={()=>deactivateMeter(m.meter_id)}><Trash2 class="w-3.5 h-3.5"/></button>{/if}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-sm text-gray-500 py-4 text-center">Sin medidores mecánicos. Agregue los contadores físicos del dispensador.</p>
        {/if}
      </div>
    {/if}
  </div>
</div>
