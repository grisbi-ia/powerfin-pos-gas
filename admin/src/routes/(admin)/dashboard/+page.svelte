<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/api';
  import { formatCurrency } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Receipt, Users } from 'lucide-svelte';
  import KpiCard from '$components/KpiCard.svelte';

  let summary: any = null;
  let loading = $state(true);
  let error = $state('');

  // Chart refs
  let salesByDayCanvas: HTMLCanvasElement;
  let salesByProductCanvas: HTMLCanvasElement;
  let salesByPaymentCanvas: HTMLCanvasElement;
  let topCustomersCanvas: HTMLCanvasElement;

  const colors = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#f97316','#ec4899'];

  onMount(async () => {
    try {
      const [sum, byDay, byProduct, byPayment, topCust] = await Promise.all([
        api.get<any>('/dashboard/summary'),
        api.get<any[]>('/dashboard/sales-by-day'),
        api.get<any[]>('/dashboard/sales-by-product'),
        api.get<any[]>('/dashboard/sales-by-payment'),
        api.get<any[]>('/dashboard/top-customers?limit=8'),
      ]);
      summary = sum;
      loading = false;

      // Import Chart.js dynamically
      const { Chart, registerables } = await import('chart.js');
      Chart.register(...registerables);

      // Sales by Day — Line
      if (byDay.length && salesByDayCanvas) {
        new Chart(salesByDayCanvas, {
          type: 'line',
          data: { labels: byDay.map((d:any)=>d.date), datasets: [{ label:'Ventas', data:byDay.map((d:any)=>d.total), borderColor:'#3b82f6', backgroundColor:'rgba(59,130,246,0.1)', fill:true, tension:0.3, pointRadius:3 }] },
          options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } }, scales:{ y:{ ticks:{ callback:(v:any)=>'$'+v } } } }
        });
      }

      // Sales by Product — Donut
      if (byProduct.length && salesByProductCanvas) {
        new Chart(salesByProductCanvas, {
          type: 'doughnut',
          data: { labels: byProduct.map((d:any)=>d.product_name), datasets: [{ data:byProduct.map((d:any)=>d.total_amount), backgroundColor:colors.slice(0,byProduct.length) }] },
          options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, padding:15 } } } }
        });
      }

      // Sales by Payment — Pie
      if (byPayment.length && salesByPaymentCanvas) {
        new Chart(salesByPaymentCanvas, {
          type: 'pie',
          data: { labels: byPayment.map((d:any)=>d.method_name), datasets: [{ data:byPayment.map((d:any)=>d.total), backgroundColor:colors.slice(0,byPayment.length) }] },
          options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, padding:15 } } } }
        });
      }

      // Top Customers — Horizontal Bar
      if (topCust.length && topCustomersCanvas) {
        new Chart(topCustomersCanvas, {
          type: 'bar',
          data: { labels: topCust.map((d:any)=>d.customer_name), datasets: [{ label:'Total', data:topCust.map((d:any)=>d.total), backgroundColor:colors.slice(0,topCust.length) }] },
          options: { indexAxis:'y', responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } }, scales:{ x:{ ticks:{ callback:(v:any)=>'$'+v } } } }
        });
      }
    } catch (err: any) {
      error = err.message;
      loading = false;
    }
  });
</script>

<div>
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

  {#if loading}
    <div class="flex justify-center py-12">
      <div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
  {:else if summary}
    <!-- KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <KpiCard title="Ventas Totales" value={formatCurrency(summary.total_sales)} icon={DollarSign} color="blue" />
      <KpiCard title="Despachos" value={String(summary.dispatch_count)} icon={ShoppingCart} color="green" />
      <KpiCard title="Ticket Promedio" value={formatCurrency(summary.avg_ticket)} icon={Receipt} color="purple" />
      <KpiCard title="Turnos Activos" value={String(summary.active_shifts)} icon={Users} color="orange" />
    </div>

    <!-- Charts Row 1: Line + Donut -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Día</h3>
        <div class="relative h-64 md:h-72">
          <canvas bind:this={salesByDayCanvas}></canvas>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Producto</h3>
        <div class="relative h-64 md:h-72">
          <canvas bind:this={salesByProductCanvas}></canvas>
        </div>
      </div>
    </div>

    <!-- Charts Row 2: Pie + Bar -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Métodos de Pago</h3>
        <div class="relative h-64 md:h-72">
          <canvas bind:this={salesByPaymentCanvas}></canvas>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Top Clientes</h3>
        <div class="relative h-64 md:h-72" style="min-height: {summary.dispatch_count > 0 ? '300px' : '100px'}">
          <canvas bind:this={topCustomersCanvas}></canvas>
        </div>
      </div>
    </div>
  {/if}
</div>
