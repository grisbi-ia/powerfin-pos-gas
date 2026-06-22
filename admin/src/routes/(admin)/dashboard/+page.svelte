<script lang="ts">
  import { api } from '$lib/api/api';
  import { formatCurrency, formatDateTime } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Receipt, Users, TrendingUp, TrendingDown, Minus } from 'lucide-svelte';
  import KpiCard from '$components/KpiCard.svelte';

  let viewMode = $state<'month' | 'today'>('month');
  let loading = $state(true);
  let error = $state('');

  // Month data
  let summary: any = null;
  let salesByDayCanvas = $state<HTMLCanvasElement>();
  let salesByProductCanvas = $state<HTMLCanvasElement>();
  let salesByPaymentCanvas = $state<HTMLCanvasElement>();

  // Today data
  let todaySummary: any = null;
  let yesterdaySummary: any = null;
  let salesByHourCanvas = $state<HTMLCanvasElement>();
  let todayPaymentCanvas = $state<HTMLCanvasElement>();
  let lastDispatches: any[] = [];

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
      ctx.font = 'bold 11px Inter, system-ui, sans-serif';
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

  function trendIcon(current: number, previous: number) {
    if (!previous || previous === 0) return { icon: Minus, color: 'text-gray-400', pct: '—' };
    const pct = Math.round((current - previous) / previous * 100);
    if (pct > 0) return { icon: TrendingUp, color: 'text-green-500', pct: `+${pct}%` };
    if (pct < 0) return { icon: TrendingDown, color: 'text-red-500', pct: `${pct}%` };
    return { icon: Minus, color: 'text-gray-400', pct: '0%' };
  }

  $effect(() => { (async () => {
    if (viewMode === 'month') await loadMonth();
    else await loadToday();
  })();
});

  async function loadMonth() {
    loading = true; error = '';
    try {
      const [sum, byDay, byDayProduct, byProduct, byPayment] = await Promise.all([
        api.get<any>('/dashboard/summary'),
        api.get<any[]>('/dashboard/sales-by-day'),
        api.get<any[]>('/dashboard/sales-by-day-product'),
        api.get<any[]>('/dashboard/sales-by-product'),
        api.get<any[]>('/dashboard/sales-by-payment'),
      ]);
      summary = sum; loading = false;

      const { Chart, registerables } = await import('chart.js');
      Chart.register(...registerables);

      if (byDay.length && salesByDayCanvas) {
        const dates = [...new Set(byDayProduct.map((d: any) => d.date))].sort();
        const products = [...new Set(byDayProduct.map((d: any) => d.product_name))];
        const productColors = ['#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#ec4899'];
        const datasets: any[] = [
          { label: 'Total', data: dates.map(date => { const f = byDay.find((d: any) => d.date === date); return f ? f.total : 0; }), borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: false, tension: 0.3, pointRadius: 3, borderWidth: 2.5 },
        ];
        products.forEach((product, i) => {
          datasets.push({ label: product, data: dates.map(date => { const f = byDayProduct.find((d: any) => d.date === date && d.product_name === product); return f ? f.total : 0; }), borderColor: productColors[i % productColors.length], fill: false, tension: 0.3, pointRadius: 2, borderWidth: 2, borderDash: [4, 2] });
        });
        new Chart(salesByDayCanvas!, { type: 'line', data: { labels: dates, datasets }, options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } } }, scales: { y: { ticks: { callback: (v: any) => '$' + v } } } } });
      }
      if (byProduct.length && salesByProductCanvas) {
        new Chart(salesByProductCanvas!, { type: 'doughnut', data: { labels: byProduct.map((d: any) => d.product_name), datasets: [{ data: byProduct.map((d: any) => d.total_amount), backgroundColor: colors.slice(0, byProduct.length) }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 15, generateLabels: legendWithPct } } } }, plugins: [percentageLabelPlugin] });
      }
      if (byPayment.length && salesByPaymentCanvas) {
        new Chart(salesByPaymentCanvas!, { type: 'pie', data: { labels: byPayment.map((d: any) => d.method_name), datasets: [{ data: byPayment.map((d: any) => d.total), backgroundColor: colors.slice(0, byPayment.length) }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 15, generateLabels: legendWithPct } } } }, plugins: [percentageLabelPlugin] });
      }
    } catch (err: any) { error = err.message; loading = false; }
  }

  async function loadToday() {
    loading = true; error = '';
    const today = new Date().toISOString().split('T')[0];
    const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
    try {
      const [tSum, ySum, byHour, byPayment, dispatches] = await Promise.all([
        api.get<any>(`/dashboard/summary?date_from=${today}&date_to=${today}`),
        api.get<any>(`/dashboard/summary?date_from=${yesterday}&date_to=${yesterday}`).catch(() => null),
        api.get<any[]>(`/dashboard/sales-by-hour?date=${today}`),
        api.get<any[]>(`/dashboard/sales-by-payment?date_from=${today}&date_to=${today}`),
        api.get<any>(`/reports/sales?date_from=${today}&date_to=${today}&page_size=10`),
      ]);
      todaySummary = tSum; yesterdaySummary = ySum; lastDispatches = dispatches.items || []; loading = false;

      const { Chart, registerables } = await import('chart.js');
      Chart.register(...registerables);

      if (salesByHourCanvas) {
        const hours = Array.from({ length: 17 }, (_, i) => i + 6);
        new Chart(salesByHourCanvas, {
          type: 'bar', data: { labels: hours.map(h => `${h}:00`), datasets: [{ label: 'Ventas', data: hours.map(h => { const f = byHour.find((d: any) => d.hour === h); return f ? f.total : 0; }), backgroundColor: '#3b82f6', borderRadius: 4 }] },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: (v: any) => '$' + v } } } }
        });
      }
      if (byPayment.length && todayPaymentCanvas) {
        new Chart(todayPaymentCanvas, { type: 'pie', data: { labels: byPayment.map((d: any) => d.method_name), datasets: [{ data: byPayment.map((d: any) => d.total), backgroundColor: colors.slice(0, byPayment.length) }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 15, generateLabels: legendWithPct } } } }, plugins: [percentageLabelPlugin] });
      }
    } catch (err: any) { error = err.message; loading = false; }
  }
</script>

<div>
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
    <div class="flex bg-gray-100 rounded-lg p-1">
      <button class="px-4 py-1.5 text-sm font-medium rounded-md transition-colors {viewMode==='month'?'bg-white text-gray-900 shadow-sm':'text-gray-500 hover:text-gray-700'}" onclick={()=>viewMode='month'}>Mes</button>
      <button class="px-4 py-1.5 text-sm font-medium rounded-md transition-colors {viewMode==='today'?'bg-white text-gray-900 shadow-sm':'text-gray-500 hover:text-gray-700'}" onclick={()=>viewMode='today'}>Hoy</button>
    </div>
  </div>

  {#if loading}
    <div class="flex justify-center py-12"><div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>

  {:else if viewMode === 'month' && summary}
    <!-- MONTH VIEW -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <KpiCard title="Ventas Totales" value={formatCurrency(summary.total_sales)} icon={DollarSign} color="blue"/>
      <KpiCard title="Despachos" value={String(summary.dispatch_count)} icon={ShoppingCart} color="green"/>
      <KpiCard title="Ticket Promedio" value={formatCurrency(summary.avg_ticket)} icon={Receipt} color="purple"/>
      <KpiCard title="Turnos Activos" value={String(summary.active_shifts)} icon={Users} color="orange"/>
    </div>
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
      <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Día</h3>
      <div class="relative h-72 md:h-80"><canvas bind:this={salesByDayCanvas}></canvas></div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6"><h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Producto</h3><div class="relative h-64 md:h-72"><canvas bind:this={salesByProductCanvas}></canvas></div></div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6"><h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Método de Pago</h3><div class="relative h-64 md:h-72"><canvas bind:this={salesByPaymentCanvas}></canvas></div></div>
    </div>

  {:else if viewMode === 'today' && todaySummary}
    <!-- TODAY VIEW -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {@const t = trendIcon(todaySummary.total_sales, yesterdaySummary?.total_sales || 0)}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Ventas Hoy</p><p class="text-xl font-bold text-gray-900 mt-1">{formatCurrency(todaySummary.total_sales)}</p><span class="text-xs {t.color}">{t.pct} vs ayer</span></div>
      {@const d = trendIcon(todaySummary.dispatch_count, yesterdaySummary?.dispatch_count || 0)}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Despachos</p><p class="text-xl font-bold text-gray-900 mt-1">{todaySummary.dispatch_count}</p><span class="text-xs {d.color}">{d.pct} vs ayer</span></div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Ticket Promedio</p><p class="text-xl font-bold text-gray-900 mt-1">{formatCurrency(todaySummary.avg_ticket)}</p></div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><p class="text-xs text-gray-500 uppercase">Turnos Activos</p><p class="text-xl font-bold text-gray-900 mt-1">{todaySummary.active_shifts}</p></div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Hora</h3>
        <div class="relative h-64 md:h-72"><canvas bind:this={salesByHourCanvas}></canvas></div>
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Método de Pago</h3>
        <div class="relative h-64 md:h-72"><canvas bind:this={todayPaymentCanvas}></canvas></div>
      </div>
    </div>

    <!-- Last dispatches -->
    {#if lastDispatches.length > 0}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <h3 class="text-sm font-semibold text-gray-700 px-4 md:px-6 py-4 border-b border-gray-200">Últimos Despachos</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead class="bg-gray-50"><tr><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Hora</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Grado</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Cliente</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Placa</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Pago</th><th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Monto</th></tr></thead>
            <tbody class="divide-y divide-gray-100">
              {#each lastDispatches as d}
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-2 text-gray-600">{d.date ? new Date(d.date).toLocaleTimeString('es-EC', {hour:'2-digit',minute:'2-digit'}) : ''}</td>
                  <td class="px-4 py-2 font-medium text-gray-900">{d.grade || '—'}</td>
                  <td class="px-4 py-2 text-gray-700">{d.customer_name || '—'}</td>
                  <td class="px-4 py-2 font-mono text-gray-600">{d.plate || '—'}</td>
                  <td class="px-4 py-2 text-gray-600">{d.payment_method || '—'}</td>
                  <td class="px-4 py-2 text-right font-mono text-gray-900">{formatCurrency(d.amount || 0)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  {/if}
</div>
