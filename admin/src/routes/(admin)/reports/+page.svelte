<script lang="ts">
  import { api, getToken } from '$lib/api/api';
  import { formatCurrency, formatDate } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Users, Wallet, Download, FileText, FileSpreadsheet } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import { toast } from '$lib/utils/toast';

  let activeTab = $state<'sales'|'dispatches'|'shifts'|'cash'>('sales');
  let items=$state<any[]>([]); let total=$state(0); let page=$state(1); let pages=$state(1);
  let loading=$state(true); let error=$state(''); let search=$state('');

  function todayStr(d: Date = new Date()): string {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }
  let dateFrom=$state(todayStr());
  let dateTo=$state(todayStr());
  let exporting=$state(false);
  let actionLoading = $state<number | null>(null);  // shift_id being actioned

  // Summary stats per tab
  let totalAmount=$state(0); let itemCount=$state(0);

  // Charts
  let chartCanvas = $state<HTMLCanvasElement>();
  let chartInstance: any = null;
  let productCanvas = $state<HTMLCanvasElement>();
  let productInstance: any = null;
  let paymentCanvas = $state<HTMLCanvasElement>();
  let paymentInstance: any = null;
  let chartDataReady = $state(false);
  let chartSkip = $state(false);

  const colors = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#f97316','#ec4899'];

  const percentageLabelPlugin = {
    id: 'percentageLabel',
    afterDatasetsDraw(chart: any) {
      const { ctx, data: chartData } = chart;
      const dataset = chartData.datasets[0];
      const total = dataset.data.reduce((a: number, b: number) => a + b, 0);
      if (total === 0) return;
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.font = 'bold 10px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      meta.data.forEach((arc: any, i: number) => {
        const pct = Math.round((dataset.data[i] / total) * 100);
        if (pct < 5) return;
        const { x, y } = arc.tooltipPosition();
        ctx.fillStyle = '#fff';
        ctx.shadowColor = 'rgba(0,0,0,0.3)';
        ctx.shadowBlur = 2;
        ctx.fillText(`${pct}%`, x, y);
        ctx.shadowBlur = 0;
      });
      ctx.restore();
    }
  };

  function legendWithPct(chart: any) {
    const data = chart.data;
    const total = data.datasets[0].data.reduce((a: number, b: number) => a + b, 0);
    return data.labels.map((label: string, i: number) => ({
      text: `${label} (${Math.round(data.datasets[0].data[i] / total * 100)}%)`,
      fillStyle: data.datasets[0].backgroundColor[i],
      strokeStyle: data.datasets[0].backgroundColor[i],
      index: i, hidden: !chart.getDataVisibility(i), pointStyle: 'circle',
    }));
  }

  async function downloadShiftReceipt(shiftId: number) {
    actionLoading = shiftId;
    try {
      const token = getToken();
      const res = await fetch(`/api/admin/reports/shifts/${shiftId}/receipt`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail || 'Error al generar PDF');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cierre_turno_${shiftId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`PDF del turno #${shiftId} generado`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      actionLoading = null;
    }
  }

  async function downloadShiftTransactions(shiftId: number) {
    actionLoading = shiftId;
    try {
      const token = getToken();
      const res = await fetch(`/api/admin/reports/shifts/${shiftId}/transactions/export?format=xlsx`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail || 'Error al generar Excel');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transacciones_turno_${shiftId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Excel del turno #${shiftId} generado`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      actionLoading = null;
    }
  }

  async function load(){
    loading=true;error='';items=[];total=0;chartDataReady=false;chartSkip=false;
    try{
      let endpoint=''; let params=`search=${encodeURIComponent(search)}&page=${page}&page_size=10`;
      if(dateFrom) params+=`&date_from=${dateFrom}`; if(dateTo) params+=`&date_to=${dateTo}`;

      if(activeTab==='sales') endpoint=`/reports/sales?${params}`;
      else if(activeTab==='dispatches') endpoint=`/reports/dispatches?${params}`;
      else if(activeTab==='shifts') endpoint=`/reports/shifts?${params}`;
      else endpoint=`/reports/cash-summary?${params}`;

      const d=await api.get<any>(endpoint);items=d.items;total=d.total;pages=d.pages;

      itemCount = total;
      if(activeTab==='sales'||activeTab==='dispatches') totalAmount=items.reduce((s:number,i:any)=>s+(i.amount||0),0);
      else if(activeTab==='shifts') totalAmount=items.reduce((s:number,i:any)=>s+(i.collected||0),0);
      else totalAmount=items.reduce((s:number,i:any)=>s+(i.amount||0),0);

      chartDataReady = (activeTab==='sales'||activeTab==='dispatches') && items.length>0;
    }catch(e:any){error=e.message}finally{loading=false}
  }

  // Render charts when data is ready and canvas is mounted (after loading=false)
  $effect(() => {
    if ((activeTab==='sales'||activeTab==='dispatches') && !loading && !error && items.length > 0 && !chartSkip) {
      renderCharts();
    } else {
      if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
      if (productInstance) { productInstance.destroy(); productInstance = null; }
      if (paymentInstance) { paymentInstance.destroy(); paymentInstance = null; }
    }
  });

  async function renderCharts(){
    chartSkip = true;  // prevent double-render from $effect reactivity

    try {
      const { Chart, registerables } = await import('chart.js');
      Chart.register(...registerables);

      const params = [];
      if (dateFrom) params.push(`date_from=${dateFrom}`);
      if (dateTo) params.push(`date_to=${dateTo}`);
      const qs = params.length ? '?' + params.join('&') : '';

      if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
      if (productInstance) { productInstance.destroy(); productInstance = null; }
      if (paymentInstance) { paymentInstance.destroy(); paymentInstance = null; }

      // 1. Sales by Day (bar) — both sales & dispatch tabs
      const byDay = await api.get<any[]>(`/dashboard/sales-by-day${qs}`);
      if (byDay.length && chartCanvas) {
        chartInstance = new Chart(chartCanvas, {
          type: 'bar',
          data: { labels: byDay.map((d: any) => d.date), datasets: [{ label: 'Ventas', data: byDay.map((d: any) => d.total), backgroundColor: '#3b82f6', borderRadius: 4 }] },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: (v: any) => '$' + v } } } },
        });
      }

      // 2 & 3: Product + Payment distribution (donut + pie) — sales tab only
      if (activeTab === 'sales') {
        const byProduct = await api.get<any[]>(`/dashboard/sales-by-product${qs}`);
        if (byProduct.length && productCanvas) {
          productInstance = new Chart(productCanvas, {
            type: 'doughnut',
            data: { labels: byProduct.map((d: any) => d.product_name), datasets: [{ data: byProduct.map((d: any) => d.total_amount), backgroundColor: colors.slice(0, byProduct.length) }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, generateLabels: legendWithPct } } } },
            plugins: [percentageLabelPlugin],
          });
        }

        const byPayment = await api.get<any[]>(`/dashboard/sales-by-payment${qs}`);
        if (byPayment.length && paymentCanvas) {
          paymentInstance = new Chart(paymentCanvas, {
            type: 'pie',
            data: { labels: byPayment.map((d: any) => d.method_name), datasets: [{ data: byPayment.map((d: any) => d.total), backgroundColor: colors.slice(0, byPayment.length) }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, generateLabels: legendWithPct } } } },
            plugins: [percentageLabelPlugin],
          });
        }
      }
    } catch { /* chart failure is non-blocking */ }
  }

  async function export_(format:'pdf'|'xlsx'){
    // Validate date range: max 31 days
    if (dateFrom && dateTo) {
      const from = new Date(dateFrom + 'T00:00:00');
      const to = new Date(dateTo + 'T00:00:00');
      const diffDays = Math.round((to.getTime() - from.getTime()) / 86400000);
      if (diffDays > 31) {
        toast.info('El rango máximo es de 31 días. Ajuste las fechas.');
        return;
      }
    }

    exporting=true;
    try{
      let endpoint='';
      if(activeTab==='sales') endpoint='/reports/sales/export';
      else if(activeTab==='shifts') endpoint='/reports/shifts/export';
      else endpoint='/reports/cash-summary/export';
      let url=`/api/admin${endpoint}?format=${format}`;
      if(dateFrom) url+=`&date_from=${dateFrom}`; if(dateTo) url+=`&date_to=${dateTo}`;
      if(search) url+=`&search=${encodeURIComponent(search)}`;
      const token = (await import('$lib/api/api')).getToken();
      const res=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${token}`}});
      if(!res.ok)throw new Error('Error al exportar');
      const blob=await res.blob();
      const objUrl=URL.createObjectURL(blob);
      const a=document.createElement('a');a.href=objUrl;a.download=`reporte_${activeTab}.${format}`;a.click();
      URL.revokeObjectURL(objUrl);
      toast.success(`Exportado como ${format.toUpperCase()}`);
    }catch(e:any){toast.error(e.message)}finally{exporting=false}
  }

  // Reset page to 1 when tab or date filters change
  $effect(() => { activeTab; dateFrom; dateTo; page = 1; });

  // Load data when page, tab, or date filters change
  $effect(() => {
    page; activeTab; dateFrom; dateTo;

    // Validate date range: max 31 days
    if (dateFrom && dateTo) {
      const from = new Date(dateFrom + 'T00:00:00');
      const to = new Date(dateTo + 'T00:00:00');
      const diffDays = Math.round((to.getTime() - from.getTime()) / 86400000);
      if (diffDays > 31) {
        toast.info('El rango máximo es de 31 días. Ajuste las fechas.');
        return;
      }
      if (diffDays < 0) {
        toast.error('La fecha "desde" no puede ser posterior a "hasta".');
        dateTo = dateFrom;
        return;
      }
    }

    load();
  });

  const cols:Record<string,{key:string;label:string;sortable?:boolean;type?:string}[]> = {
    sales: [{key:'date',label:'Fecha',type:'datetime'},{key:'dispenser_name',label:'Surtidor'},{key:'hose_side',label:'Lado'},{key:'grade',label:'Grado'},{key:'customer_name',label:'Cliente'},{key:'plate',label:'Placa'},{key:'payment_method',label:'Pago'},{key:'amount',label:'Monto',type:'currency'},{key:'volume',label:'Volumen'},{key:'sri_status',label:'SRI'},{key:'authorized_by',label:'Usuario'},{key:'status',label:'Estado'}],
    shifts: [{key:'shift_id',label:'Turno'},{key:'user_name',label:'Usuario'},{key:'opened_at',label:'Apertura',type:'datetime'},{key:'closed_at',label:'Cierre',type:'datetime'},{key:'status',label:'Estado'},{key:'opening_cash',label:'Caja Inicial',type:'currency'},{key:'collected',label:'Cobrado Total',type:'currency'},{key:'collected_cash',label:'Efectivo Ventas',type:'currency'},{key:'efectivo_actual',label:'Efectivo Actual',type:'currency'},{key:'surplus',label:'Sobrante',type:'currency'},{key:'shortage',label:'Faltante',type:'currency'}],
    cash: [{key:'date',label:'Fecha',type:'date'},{key:'shift_id',label:'Turno'},{key:'user_name',label:'Usuario'},{key:'type',label:'Tipo'},{key:'amount',label:'Monto',type:'currency'},{key:'observation',label:'Observación'}],
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
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='sales'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>{if(activeTab==='sales') load(); else activeTab='sales'}}><DollarSign class="w-4 h-4 inline mr-1"/>Ventas</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='shifts'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>{if(activeTab==='shifts') load(); else activeTab='shifts'}}><Users class="w-4 h-4 inline mr-1"/>Turnos</button>
    <button class="px-4 py-2 text-sm font-medium rounded-lg {activeTab==='cash'?'bg-primary-500 text-white':'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}" onclick={()=>{if(activeTab==='cash') load(); else activeTab='cash'}}><Wallet class="w-4 h-4 inline mr-1"/>Caja</button>
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

  <!-- Charts (only for sales) -->
  {#if activeTab === 'sales' && !loading && !error && items.length > 0}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Producto</h3>
        <div class="relative h-60 md:h-64"><canvas bind:this={productCanvas}></canvas></div>
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Método de Pago</h3>
        <div class="relative h-60 md:h-64"><canvas bind:this={paymentCanvas}></canvas></div>
      </div>
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
    onSearch={(q:string)=>{search=q;page=1}} onSort={()=>{}}
    onPage={(p:number)=>{page=p}} onCreate={()=>{}} createLabel="">
    {#snippet children(row: { item: any })}
      {#if activeTab === 'shifts' && row.item.status === 'CLOSED'}
        <button
          onclick={() => downloadShiftReceipt(row.item.shift_id)}
          disabled={actionLoading === row.item.shift_id}
          class="p-1.5 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
          title="Reimprimir cierre de turno (PDF)"
        >
          {#if actionLoading === row.item.shift_id}
            <span class="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin inline-block"></span>
          {:else}
            <FileText class="w-4 h-4" />
          {/if}
        </button>
        <button
          onclick={() => downloadShiftTransactions(row.item.shift_id)}
          disabled={actionLoading === row.item.shift_id}
          class="p-1.5 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
          title="Exportar transacciones del turno (Excel)"
        >
          {#if actionLoading === row.item.shift_id}
            <span class="w-4 h-4 border-2 border-green-500 border-t-transparent rounded-full animate-spin inline-block"></span>
          {:else}
            <FileSpreadsheet class="w-4 h-4" />
          {/if}
        </button>
      {/if}
    {/snippet}
  </DataTable>
</div>
