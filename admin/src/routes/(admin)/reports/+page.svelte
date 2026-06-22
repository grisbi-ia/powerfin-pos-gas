<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/api';
  import { formatCurrency, formatDate } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Users, Wallet, Download } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import { toast } from 'svelte-sonner';

  let activeTab = $state<'sales'|'dispatches'|'shifts'|'cash'>('sales');
  let items=$state<any[]>([]); let total=$state(0); let page=$state(1); let pages=$state(1);
  let loading=$state(true); let error=$state(''); let search=$state(''); let dateFrom=$state(''); let dateTo=$state('');
  let exporting=$state(false);

  // Summary stats per tab
  let totalAmount=$state(0); let itemCount=$state(0);

  // Chart
  let chartCanvas: HTMLCanvasElement;
  let chartInstance: any = null;

  async function load(){
    loading=true;error='';items=[];total=0;
    try{
      let endpoint=''; let params=`search=${encodeURIComponent(search)}&page=${page}&page_size=20`;
      if(dateFrom) params+=`&date_from=${dateFrom}`; if(dateTo) params+=`&date_to=${dateTo}`;

      if(activeTab==='sales') endpoint=`/reports/sales?${params}`;
      else if(activeTab==='dispatches') endpoint=`/reports/dispatches?${params}`;
      else if(activeTab==='shifts') endpoint=`/reports/shifts?${params}`;
      else endpoint=`/reports/cash-summary?${params}`;

      const d=await api.get<any>(endpoint);items=d.items;total=d.total;pages=d.pages;

      // Calculate summary
      itemCount = total;
      if(activeTab==='sales'||activeTab==='dispatches') totalAmount=items.reduce((s:number,i:any)=>s+(i.amount||0),0);
      else if(activeTab==='shifts') totalAmount=items.reduce((s:number,i:any)=>s+(i.collected||0),0);
      else totalAmount=items.reduce((s:number,i:any)=>s+(i.amount||0),0);

      // Load chart data for sales/dispatches
      if((activeTab==='sales'||activeTab==='dispatches') && chartCanvas && items.length>0) await loadChart();
      else if(chartInstance){chartInstance.destroy();chartInstance=null;}
    }catch(e:any){error=e.message}finally{loading=false}
  }

  async function loadChart(){
    try{
      const data=await api.get<any[]>(`/dashboard/sales-by-day${dateFrom?'?date_from='+dateFrom:''}${dateFrom&&dateTo?'&':!dateFrom&&dateTo?'?':''}${dateTo?'date_to='+dateTo:''}`);
      if(data.length===0)return;
      const { Chart, registerables } = await import('chart.js');
      Chart.register(...registerables);
      if(chartInstance) chartInstance.destroy();
      chartInstance = new Chart(chartCanvas, {
        type:'bar', data:{ labels:data.map((d:any)=>d.date), datasets:[{ label:'Ventas', data:data.map((d:any)=>d.total), backgroundColor:'#3b82f6', borderRadius:4 }] },
        options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } }, scales:{ y:{ ticks:{ callback:(v:any)=>'$'+v } } } }
      });
    }catch{}
  }

  async function export_(format:'pdf'|'xlsx'){
    exporting=true;
    try{
      let endpoint='';
      if(activeTab==='sales') endpoint='/reports/sales/export';
      else if(activeTab==='dispatches') endpoint='/reports/dispatches/export';
      else if(activeTab==='shifts') endpoint='/reports/shifts/export';
      else endpoint='/reports/cash-summary/export';
      let url=`/api/admin${endpoint}?format=${format}`;
      if(dateFrom) url+=`&date_from=${dateFrom}`; if(dateTo) url+=`&date_to=${dateTo}`;
      if(search) url+=`&search=${encodeURIComponent(search)}`;
      const token = (await import('$lib/api/api')).getToken();
      const res=await fetch(url,{headers:{Authorization:`Bearer ${token}`}});
      if(!res.ok)throw new Error('Error al exportar');
      const blob=await res.blob();
      const objUrl=URL.createObjectURL(blob);
      const a=document.createElement('a');a.href=objUrl;a.download=`reporte_${activeTab}.${format}`;a.click();
      URL.revokeObjectURL(objUrl);
      toast.success(`Exportado como ${format.toUpperCase()}`);
    }catch(e:any){toast.error(e.message)}finally{exporting=false}
  }

  $effect(() => { activeTab; dateFrom; dateTo; page=1; load(); });

  const cols:Record<string,{key:string;label:string;sortable?:boolean}[]> = {
    sales: [{key:'date',label:'Fecha'},{key:'dispenser_name',label:'Surtidor'},{key:'grade',label:'Grado'},{key:'customer_name',label:'Cliente'},{key:'plate',label:'Placa'},{key:'payment_method',label:'Pago'},{key:'amount',label:'Monto'},{key:'status',label:'Estado'}],
    dispatches: [{key:'date',label:'Fecha'},{key:'dispenser_name',label:'Surtidor'},{key:'grade',label:'Grado'},{key:'customer_name',label:'Cliente'},{key:'plate',label:'Placa'},{key:'payment_method',label:'Pago'},{key:'amount',label:'Monto'},{key:'volume',label:'Volumen'},{key:'sri_status',label:'SRI'}],
    shifts: [{key:'shift_id',label:'Turno'},{key:'user_name',label:'Usuario'},{key:'opened_at',label:'Apertura'},{key:'closed_at',label:'Cierre'},{key:'status',label:'Estado'},{key:'opening_cash',label:'Caja Inicial'},{key:'collected',label:'Cobrado'},{key:'surplus',label:'Sobrante'},{key:'shortage',label:'Faltante'}],
    cash: [{key:'date',label:'Fecha'},{key:'shift_id',label:'Turno'},{key:'user_name',label:'Usuario'},{key:'type',label:'Tipo'},{key:'amount',label:'Monto'},{key:'observation',label:'Observación'}],
  };
</script>

<div>
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Reportes</h1>
    <div class="flex gap-2">
      <button onclick={()=>export_('xlsx')} disabled={exporting} class="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"><Download class="w-4 h-4"/>Excel</button>
      <button onclick={()=>export_('pdf')} disabled={exporting} class="inline-flex items-center gap-2 px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50"><Download class="w-4 h-4"/>PDF</button>
    </div>
  </div>

  <!-- Tab bar + date filters -->
  <div class="flex flex-wrap gap-2 mb-4 items-center">
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='sales'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='sales'}><DollarSign class="w-4 h-4 inline mr-1"/>Ventas</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='dispatches'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='dispatches'}><ShoppingCart class="w-4 h-4 inline mr-1"/>Despachos</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='shifts'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='shifts'}><Users class="w-4 h-4 inline mr-1"/>Turnos</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='cash'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='cash'}><Wallet class="w-4 h-4 inline mr-1"/>Caja</button>
    <div class="flex-1 hidden sm:block"></div>
    <input type="date" bind:value={dateFrom} class="px-3 py-2 text-sm border border-gray-300 rounded-md"/>
    <span class="text-sm text-gray-500 py-2">a</span>
    <input type="date" bind:value={dateTo} class="px-3 py-2 text-sm border border-gray-300 rounded-md"/>
  </div>

  <!-- Summary cards -->
  {#if !loading && !error && items.length > 0}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Total Registros</p><p class="text-xl font-bold text-gray-900 mt-1">{itemCount}</p></div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Monto Total</p><p class="text-xl font-bold text-gray-900 mt-1">{formatCurrency(totalAmount)}</p></div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Promedio</p><p class="text-xl font-bold text-gray-900 mt-1">{formatCurrency(items.length>0?totalAmount/items.length:0)}</p></div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Página</p><p class="text-xl font-bold text-gray-900 mt-1">{page} de {pages||1}</p></div>
    </div>
  {/if}

  <!-- Chart (only for sales/dispatches) -->
  {#if (activeTab==='sales'||activeTab==='dispatches') && !loading && !error && items.length > 0}
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
      <h3 class="text-sm font-semibold text-gray-700 mb-4">Tendencia de Ventas</h3>
      <div class="relative h-48 md:h-56">
        <canvas bind:this={chartCanvas}></canvas>
      </div>
    </div>
  {/if}

  <DataTable title="" {items} columns={cols[activeTab]} {loading}{error}{total}{page}{pages}{search} sortKey="" sortOrder="asc"
    onSearch={(q:string)=>{search=q;page=1;load()}} onSort={()=>{}}
    onPage={(p:number)=>{page=p;load()}} onCreate={()=>{}} createLabel="" />
</div>
