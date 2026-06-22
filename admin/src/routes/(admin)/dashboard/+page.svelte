<script lang="ts">
  import { api } from '$lib/api/api';
  import { formatCurrency } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Receipt, Users } from 'lucide-svelte';
  import KpiCard from '$components/KpiCard.svelte';

  let summary: any = null;
  let loading = $state(true);
  let error = $state('');

  let salesByDayCanvas = $state<HTMLCanvasElement>();
  let salesByProductCanvas = $state<HTMLCanvasElement>();
  let salesByPaymentCanvas = $state<HTMLCanvasElement>();
  let topCustomersCanvas = $state<HTMLCanvasElement>();

  const colors = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#f97316','#ec4899'];

  // Plugin: draw percentage on donut/pie slices
  const percentageLabelPlugin = {
    id: 'percentageLabel',
    afterDatasetsDraw(chart: any) {
      const { ctx, data: chartData } = chart;
      const dataset = chartData.datasets[0];
      const total = dataset.data.reduce((a: number, b: number) => a + b, 0);
      if (total === 0) return;
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.font = 'bold 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      meta.data.forEach((arc: any, i: number) => {
        const pct = Math.round((dataset.data[i] / total) * 100);
        if (pct < 5) return; // skip tiny slices
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

  $effect(() => { (async () => {
    loadDashboard();
  })();
});

  async function loadDashboard() {
    try {
      const [sum, byDay, byDayProduct, byProduct, byPayment, topCust] = await Promise.all([
        api.get<any>('/dashboard/summary'),
        api.get<any[]>('/dashboard/sales-by-day'),
        api.get<any[]>('/dashboard/sales-by-day-product'),
        api.get<any[]>('/dashboard/sales-by-product'),
        api.get<any[]>('/dashboard/sales-by-payment'),
        api.get<any[]>('/dashboard/top-customers?limit=8'),
      ]);
      summary = sum;
      loading = false;

      const { Chart, registerables } = await import('chart.js');
      Chart.register(...registerables);

      if (byDay.length && salesByDayCanvas) {
        // Build datasets: total line + one line per product
        const dates = [...new Set(byDayProduct.map((d:any)=>d.date))].sort();
        const products = [...new Set(byDayProduct.map((d:any)=>d.product_name))];
        const productColors = ['#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#f97316','#ec4899','#3b82f6'];

        const datasets: any[] = [
          { label:'Total', data:dates.map(date=>{ const found=byDay.find((d:any)=>d.date===date); return found?found.total:0 }), borderColor:'#3b82f6', backgroundColor:'rgba(59,130,246,0.1)', fill:false, tension:0.3, pointRadius:3, borderWidth:2.5 },
        ];
        products.forEach((product,i)=>{
          datasets.push({
            label:product, data:dates.map(date=>{ const found=byDayProduct.find((d:any)=>d.date===date&&d.product_name===product); return found?found.total:0 }),
            borderColor:productColors[i%productColors.length], backgroundColor:'transparent', fill:false, tension:0.3, pointRadius:2, borderWidth:2, borderDash:[4,2]
          });
        });

        new Chart(salesByDayCanvas, {
          type: 'line', data: { labels:dates, datasets },
          options: { responsive:true, maintainAspectRatio:false, interaction:{ mode:'index', intersect:false }, plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, padding:12, font:{ size:11 } } } }, scales:{ y:{ ticks:{ callback:(v:any)=>'$'+v } } } }
        });
      }
      if (byProduct.length && salesByProductCanvas) {
        new Chart(salesByProductCanvas, {
          type: 'doughnut', data: { labels: byProduct.map((d:any)=>d.product_name), datasets: [{ data:byProduct.map((d:any)=>d.total_amount), backgroundColor:colors.slice(0,byProduct.length) }] },
          options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, padding:15, generateLabels(chart:any){ const data=chart.data; return data.labels.map((label:string,i:number)=>({text:`${label} (${Math.round(data.datasets[0].data[i]/data.datasets[0].data.reduce((a:number,b:number)=>a+b,0)*100)}%)`,fillStyle:data.datasets[0].backgroundColor[i],strokeStyle:data.datasets[0].backgroundColor[i],index:i,hidden:!chart.getDataVisibility(i),pointStyle:'circle'})); } } } } },
          plugins: [percentageLabelPlugin]
        });
      }
      if (byPayment.length && salesByPaymentCanvas) {
        new Chart(salesByPaymentCanvas, {
          type: 'pie', data: { labels: byPayment.map((d:any)=>d.method_name), datasets: [{ data:byPayment.map((d:any)=>d.total), backgroundColor:colors.slice(0,byPayment.length) }] },
          options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, padding:15, generateLabels(chart:any){ const data=chart.data; return data.labels.map((label:string,i:number)=>({text:`${label} (${Math.round(data.datasets[0].data[i]/data.datasets[0].data.reduce((a:number,b:number)=>a+b,0)*100)}%)`,fillStyle:data.datasets[0].backgroundColor[i],strokeStyle:data.datasets[0].backgroundColor[i],index:i,hidden:!chart.getDataVisibility(i),pointStyle:'circle'})); } } } } },
          plugins: [percentageLabelPlugin]
        });
      }
    } catch (err: any) {
      error = err.message;
      loading = false;
    }
  }
</script>

<div>
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>
  {#if loading}
    <div class="flex justify-center py-12"><div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
  {:else if summary}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <KpiCard title="Ventas Totales" value={formatCurrency(summary.total_sales)} icon={DollarSign} color="blue"/>
      <KpiCard title="Despachos" value={String(summary.dispatch_count)} icon={ShoppingCart} color="green"/>
      <KpiCard title="Ticket Promedio" value={formatCurrency(summary.avg_ticket)} icon={Receipt} color="purple"/>
      <KpiCard title="Turnos Activos" value={String(summary.active_shifts)} icon={Users} color="orange"/>
    </div>

    <!-- Ventas por Día — full width -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
      <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Día</h3>
      <div class="relative h-72 md:h-80">
        <canvas bind:this={salesByDayCanvas}></canvas>
      </div>
    </div>

    <!-- Ventas por Producto | Ventas por Método de Pago -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Producto</h3>
        <div class="relative h-64 md:h-72">
          <canvas bind:this={salesByProductCanvas}></canvas>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Método de Pago</h3>
        <div class="relative h-64 md:h-72">
          <canvas bind:this={salesByPaymentCanvas}></canvas>
        </div>
      </div>
    </div>
  {/if}
</div>
