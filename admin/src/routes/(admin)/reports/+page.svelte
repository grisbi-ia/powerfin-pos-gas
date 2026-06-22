<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/api';
  import { formatCurrency } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Users, Wallet, Download } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import { toast } from 'svelte-sonner';

  let activeTab = $state<'sales'|'dispatches'|'shifts'|'cash'>('sales');
  let items=$state<any[]>([]); let total=$state(0); let page=$state(1); let pages=$state(1);
  let loading=$state(true); let error=$state(''); let search=$state(''); let dateFrom=$state(''); let dateTo=$state('');
  let exporting=$state(false);

  async function load(){
    loading=true;error='';
    try{
      let endpoint='';
      if(activeTab==='sales') endpoint=`/reports/sales?search=${encodeURIComponent(search)}&page=${page}&page_size=20&${dateFrom?'date_from='+dateFrom:''}&${dateTo?'date_to='+dateTo:''}`;
      else if(activeTab==='dispatches') endpoint=`/reports/dispatches?search=${encodeURIComponent(search)}&page=${page}&page_size=20&${dateFrom?'date_from='+dateFrom:''}&${dateTo?'date_to='+dateTo:''}`;
      else if(activeTab==='shifts') endpoint=`/reports/shifts?search=${encodeURIComponent(search)}&page=${page}&page_size=20&${dateFrom?'date_from='+dateFrom:''}&${dateTo?'date_to='+dateTo:''}`;
      else endpoint=`/reports/cash-summary?search=${encodeURIComponent(search)}&page=${page}&page_size=20&${dateFrom?'date_from='+dateFrom:''}&${dateTo?'date_to='+dateTo:''}`;
      const d=await api.get<any>(endpoint);items=d.items;total=d.total;pages=d.pages;
    }catch(e:any){error=e.message}finally{loading=false}
  }

  async function export_(format:'pdf'|'xlsx'){
    exporting=true;
    try{
      let endpoint='';
      if(activeTab==='sales') endpoint='/reports/sales/export';
      else if(activeTab==='dispatches') endpoint='/reports/dispatches/export';
      else if(activeTab==='shifts') endpoint='/reports/shifts/export';
      else endpoint='/reports/cash-summary/export';
      const token = (await import('$lib/api/api')).getToken();
      const res=await fetch(`/api/admin${endpoint}?format=${format}`,{headers:{Authorization:`Bearer ${token}`}});
      if(!res.ok)throw new Error('Error al exportar');
      const blob=await res.blob();
      const url=URL.createObjectURL(blob);
      const a=document.createElement('a');a.href=url;a.download=`reporte.${format}`;a.click();
      URL.revokeObjectURL(url);
      toast.success('Exportado correctamente');
    }catch(e:any){toast.error(e.message)}finally{exporting=false}
  }

  $effect(() => { activeTab; dateFrom; dateTo; load(); });

  const cols:Record<string,{key:string;label:string;sortable?:boolean}[]> = {
    sales: [{key:'date',label:'Fecha'},{key:'dispenser_name',label:'Surtidor'},{key:'grade',label:'Grado'},{key:'customer_name',label:'Cliente'},{key:'plate',label:'Placa'},{key:'payment_method',label:'Pago'},{key:'amount',label:'Monto'},{key:'status',label:'Estado'}],
    dispatches: [{key:'date',label:'Fecha'},{key:'shift_id',label:'Turno'},{key:'dispenser_name',label:'Surtidor'},{key:'grade',label:'Grado'},{key:'customer_name',label:'Cliente'},{key:'amount',label:'Monto'},{key:'volume',label:'Volumen'},{key:'status',label:'Estado'},{key:'sri_status',label:'SRI'}],
    shifts: [{key:'shift_id',label:'Turno'},{key:'user_name',label:'Usuario'},{key:'opened_at',label:'Apertura'},{key:'closed_at',label:'Cierre'},{key:'status',label:'Estado'},{key:'collected',label:'Cobrado'},{key:'surplus',label:'Sobrante'},{key:'shortage',label:'Faltante'}],
    cash: [{key:'shift_id',label:'Turno'},{key:'user_name',label:'Usuario'},{key:'type',label:'Tipo'},{key:'amount',label:'Monto'},{key:'observation',label:'Observación'},{key:'date',label:'Fecha'}],
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

  <div class="flex gap-2 mb-4 flex-wrap">
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='sales'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='sales'}><DollarSign class="w-4 h-4 inline mr-1"/>Ventas</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='dispatches'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='dispatches'}><ShoppingCart class="w-4 h-4 inline mr-1"/>Despachos</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='shifts'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='shifts'}><Users class="w-4 h-4 inline mr-1"/>Turnos</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='cash'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>activeTab='cash'}><Wallet class="w-4 h-4 inline mr-1"/>Caja</button>
    <div class="flex-1"></div>
    <input type="date" bind:value={dateFrom} onchange={load} class="px-3 py-2 text-sm border border-gray-300 rounded-md"/>
    <span class="text-sm text-gray-500 py-2">a</span>
    <input type="date" bind:value={dateTo} onchange={load} class="px-3 py-2 text-sm border border-gray-300 rounded-md"/>
  </div>

  <DataTable title="" {items} columns={cols[activeTab]} {loading}{error}{total}{page}{pages}{search} sortKey="" sortOrder="asc"
    onSearch={(q:string)=>{search=q;page=1;load()}} onSort={()=>{}}
    onPage={(p:number)=>{page=p;load()}} onCreate={()=>{}} createLabel="" />
</div>
