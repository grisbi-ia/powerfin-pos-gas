<script lang="ts">
  import { api } from '$lib/api/api';
  import { formatCurrency } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Receipt, TrendingUp, TrendingDown, Droplets } from 'lucide-svelte';
  import KpiCard from '$components/KpiCard.svelte';
  import ModeSelector from '$components/dashboard/ModeSelector.svelte';
  import ChipScroller from '$components/dashboard/ChipScroller.svelte';
  import DonutChart from '$components/dashboard/DonutChart.svelte';
  import ComparisonChart from '$components/dashboard/ComparisonChart.svelte';
  import TopPeriodsChart from '$components/dashboard/TopPeriodsChart.svelte';
  import ProductLinesChart from '$components/dashboard/ProductLinesChart.svelte';
  import type { Period, ChipItem } from '$components/dashboard/types';

  // ── State ────────────────────────────────────────────────────────

  let period = $state<Period>('daily');
  let selectedDate = $state('');
  let loading = $state(true);
  let error = $state('');
  let mounted = $state(false);
  let transitionKey = $state(0);
  let firstYear = $state(2024);  // fallback, will fetch from system_config

  // API data
  let summary: any = null;
  let evolutionCompare: any = null;
  let byProduct: any[] = [];
  let byPayment: any[] = [];
  let byGallons: any[] = [];
  let compareData: any = null;
  let topPeriods: any[] = [];
  let gallonsByPeriod: any[] = [];

  // Today-only data
  let todayShifts: any[] = [];
  let lastDispatches: any[] = [];

  const monthNames = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  const monthNamesFull = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

  const isToday = $derived(period === 'daily' && selectedDate === toLocalDate(new Date()));

  // ── Date helpers ─────────────────────────────────────────────────

  function toLocalDate(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  function formatApiDate(p: Period, dateStr: string): string {
    if (p === 'monthly') { const [y, m] = dateStr.split('-'); return `${y}-${m}-01`; }
    if (p === 'annual') return `${dateStr}-01-01`;
    return dateStr;
  }

  function formatDateLabel(p: Period, dateStr: string): string {
    if (p === 'daily') {
      const d = new Date(dateStr + 'T12:00:00');
      return d.toLocaleDateString('es-EC', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    if (p === 'monthly') { const [y, m] = dateStr.split('-'); return `${monthNamesFull[parseInt(m)]} ${y}`; }
    return dateStr;
  }

  // ── Chip builder ─────────────────────────────────────────────────

  function buildChips(p: Period, anchor: string): ChipItem[] {
    if (!anchor) return [];
    const today = toLocalDate(new Date());
    const yesterday = toLocalDate(new Date(Date.now() - 86400000));

    if (p === 'daily') {
      const [y, m] = anchor.split('-').map(Number);
      const daysInMonth = new Date(y, m, 0).getDate();
      const now = new Date();
      const todayNum = now.getDate();
      const currentMonth = now.getMonth() + 1;
      const currentYear = now.getFullYear();

      return Array.from({ length: daysInMonth }, (_, i) => {
        const day = i + 1;
        const dateStr = `${y}-${String(m).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const isTodayFlag = y === currentYear && m === currentMonth && day === todayNum;
        let sublabel: string | undefined;
        if (isTodayFlag) sublabel = 'Hoy';
        else if (dateStr === yesterday) sublabel = 'Ayer';
        return { value: dateStr, label: String(day), sublabel, isToday: isTodayFlag, isPast: dateStr <= today };
      });
    }

    if (p === 'monthly') {
      const y = parseInt(anchor.split('-')[0]);
      const now = new Date();
      const cm = now.getMonth() + 1;
      const cy = now.getFullYear();
      return Array.from({ length: 12 }, (_, i) => {
        const m = i + 1;
        const dateStr = `${y}-${String(m).padStart(2,'0')}`;
        return { value: dateStr, label: monthNames[m], isToday: y === cy && m === cm, isPast: dateStr <= `${cy}-${String(cm).padStart(2,'0')}` };
      });
    }

    // annual
    const cy = new Date().getFullYear();
    return Array.from({ length: cy - firstYear + 1 }, (_, i) => {
      const y = firstYear + i;
      return { value: String(y), label: String(y), isToday: y === cy, isPast: true };
    });
  }

  let chips = $derived(buildChips(period, selectedDate));

  // ── Init ─────────────────────────────────────────────────────────

  $effect(() => {
    if (!mounted) {
      selectedDate = toLocalDate(new Date());
      // Fetch first year from system_config
      api.get<any[]>('/system-config').then(configs => {
        const fy = configs.find((c: any) => c.key === 'dashboard.first_year');
        if (fy) firstYear = parseInt(fy.value) || 2024;
      }).catch(() => {});
      mounted = true;
    }
  });

  $effect(() => { if (selectedDate) loadData(); });

  function setPeriod(p: Period) {
    period = p;
    transitionKey++;
    const today = toLocalDate(new Date());
    if (p === 'daily') selectedDate = today;
    else if (p === 'monthly') selectedDate = today.substring(0, 7);
    else selectedDate = String(new Date().getFullYear());
  }

  function selectChip(value: string) { selectedDate = value; }

  // ── Pivot gallonsByPeriod into a monthly table ──────────────────

  function pivotMonthly(data: any[]) {
    // Group by date, extract gallons per product_id (1=DIESEL, 2=SUPER, 3=ECO_PAIS)
    const byDay = new Map<string, { diesel: number; super_: number; eco: number }>();
    for (const d of data) {
      const day = d.period_label; // "2026-06-15"
      if (!byDay.has(day)) byDay.set(day, { diesel: 0, super_: 0, eco: 0 });
      const entry = byDay.get(day)!;
      if (d.product_id === 1) entry.diesel += d.gallons;
      else if (d.product_id === 2) entry.super_ += d.gallons;
      else if (d.product_id === 3) entry.eco += d.gallons;
    }

    const monthNamesShort = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const sorted = [...byDay.keys()].sort();

    const rows = sorted.map(day => {
      const e = byDay.get(day)!;
      const parts = day.split('-');
      const label = parts.length === 3 ? `${parseInt(parts[2])} ${monthNamesShort[parseInt(parts[1])]}` : day;
      return { label, diesel: e.diesel, super: e.super_, eco: e.eco, total: e.diesel + e.super_ + e.eco };
    });

    const totals = {
      diesel: rows.reduce((s, r) => s + r.diesel, 0),
      super: rows.reduce((s, r) => s + r.super, 0),
      eco: rows.reduce((s, r) => s + r.eco, 0),
      total: rows.reduce((s, r) => s + r.total, 0),
    };

    return { rows, totals };
  }

  // ── Data loading ─────────────────────────────────────────────────

  async function loadData() {
    loading = true; error = '';
    const apiDate = formatApiDate(period, selectedDate);
    try {
      const fetches: Promise<any>[] = [
        api.get<any>(`/dashboard/summary?period=${period}&date=${apiDate}`),
        api.get<any>(`/dashboard/evolution/compare?period=${period}&date=${apiDate}`),
        api.get<any[]>(`/dashboard/sales-by-product?period=${period}&date=${apiDate}`),
        api.get<any[]>(`/dashboard/sales-by-payment?period=${period}&date=${apiDate}`),
        api.get<any[]>(`/dashboard/gallons-by-product?period=${period}&date=${apiDate}`),
        api.get<any>(`/dashboard/compare?period=${period}&date=${apiDate}`).catch(() => null),
      ];
      // top-periods only for monthly/annual
      if (period !== 'daily') {
        fetches.push(api.get<any[]>(`/dashboard/top-periods?period=${period}&date=${apiDate}&limit=${period === 'annual' ? 3 : 5}`).catch(() => []));
      } else {
        fetches.push(Promise.resolve([]));
      }
      // gallons by period + product (multi-line chart)
      fetches.push(api.get<any[]>(`/dashboard/gallons-by-period?period=${period}&date=${apiDate}`).catch(() => []));

      const [sum, evoComp, prod, pay, gal, comp, topP, gbp] = await Promise.all(fetches);
      summary = sum; evolutionCompare = evoComp; byProduct = prod; byPayment = pay;
      byGallons = gal; compareData = comp; topPeriods = topP; gallonsByPeriod = gbp;

      // Today extra data
      if (isToday) {
        const todayStr = toLocalDate(new Date());
        try {
          const [dispatches, shifts] = await Promise.all([
            api.get<any>(`/reports/sales?date_from=${todayStr}&date_to=${todayStr}&page_size=10`),
            api.get<any>(`/reports/shifts?date_from=${todayStr}&date_to=${todayStr}&closed_date_from=${todayStr}&closed_date_to=${todayStr}&page_size=50`),
          ]);
          lastDispatches = dispatches.items || [];
          todayShifts = shifts.items || [];
        } catch { lastDispatches = []; todayShifts = []; }
      } else {
        lastDispatches = []; todayShifts = [];
      }

      loading = false;
    } catch (err: any) {
      error = err.message || 'Error loading dashboard';
      loading = false;
    }
  }
</script>

<div>
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
    <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
    <ModeSelector mode={period} onchange={setPeriod} />
  </div>

  <!-- Chips -->
  <div class="mb-4">
    <ChipScroller items={chips} selectedValue={selectedDate} onselect={selectChip} />
  </div>

  <h2 class="text-sm text-gray-500 mb-6 capitalize">{formatDateLabel(period, selectedDate)}</h2>

  {#if loading}
    <div class="flex justify-center py-12">
      <div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
  {:else if summary}
    <!-- Content with fade transition on period change -->
    {#key transitionKey}
    <div class="dashboard-content">
    <!-- KPI Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6">
      <KpiCard title="Ventas {period === 'daily' ? 'Hoy' : 'Totales'}" value={formatCurrency(summary.total_sales)} icon={DollarSign} color="blue" />
      <KpiCard title="Galones" value={`${summary.total_gallons.toLocaleString('es-EC')} gl`} icon={Droplets} color="green" />
      <KpiCard title="Despachos" value={String(summary.dispatch_count)} icon={ShoppingCart} color="purple" />
      <KpiCard title="Ticket Prom." value={formatCurrency(summary.avg_ticket)} icon={Receipt} color="orange" />
    </div>

    <!-- Growth badges -->
    {#if compareData && (compareData.growth_sales_pct != null || compareData.growth_gallons_pct != null)}
      <div class="flex flex-wrap gap-3 mb-6 text-sm">
        {#if compareData.growth_sales_pct != null}
          <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full {compareData.growth_sales_pct >= 0 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}">
            {#if compareData.growth_sales_pct >= 0}<TrendingUp class="w-4 h-4" />{:else}<TrendingDown class="w-4 h-4" />{/if}
            Ventas: {compareData.growth_sales_pct >= 0 ? '+' : ''}{compareData.growth_sales_pct}% vs período anterior
          </span>
        {/if}
        {#if compareData.growth_gallons_pct != null}
          <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full {compareData.growth_gallons_pct >= 0 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}">
            {#if compareData.growth_gallons_pct >= 0}<TrendingUp class="w-4 h-4" />{:else}<TrendingDown class="w-4 h-4" />{/if}
            Galones: {compareData.growth_gallons_pct >= 0 ? '+' : ''}{compareData.growth_gallons_pct}% vs período anterior
          </span>
        {/if}
      </div>
    {/if}

    <!-- Comparison charts (sales $ + gallons, previous/current/next) -->
    {#if evolutionCompare}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">
          {period === 'daily' ? 'Ventas $ por Hora' : period === 'annual' ? 'Ventas $ por Mes' : 'Ventas $ por Día'}
        </h3>
        <ComparisonChart
          metric="sales"
          {period}
          previous={evolutionCompare.previous}
          current={evolutionCompare.current}
          next={evolutionCompare.next}
          previousLabel={evolutionCompare.previous_label}
          currentLabel={evolutionCompare.current_label}
          nextLabel={evolutionCompare.next_label}
        />
      </div>

      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">
          {period === 'daily' ? 'Galones por Hora' : period === 'annual' ? 'Galones por Mes' : 'Galones por Día'}
        </h3>
        <ComparisonChart
          metric="gallons"
          {period}
          previous={evolutionCompare.previous}
          current={evolutionCompare.current}
          next={evolutionCompare.next}
          previousLabel={evolutionCompare.previous_label}
          currentLabel={evolutionCompare.current_label}
          nextLabel={evolutionCompare.next_label}
        />
      </div>
    {/if}

    <!-- Gallons by product evolution (multi-line, no comparison) -->
    {#if gallonsByPeriod.length > 0}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">
          Galones por Producto — {period === 'daily' ? 'por Hora' : period === 'annual' ? 'por Mes' : 'por Día'}
        </h3>
        <ProductLinesChart {period} data={gallonsByPeriod} />
      </div>
    {/if}

    <!-- 3 donuts/pies -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Ventas por Producto</h3>
        <DonutChart labels={byProduct.map((d: any) => d.product_name)} data={byProduct.map((d: any) => d.total_amount)} />
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Galones por Producto</h3>
        <DonutChart labels={byGallons.map((d: any) => d.product_name)} data={byGallons.map((d: any) => d.total_liters)} />
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Método de Pago</h3>
        <DonutChart type="pie" labels={byPayment.map((d: any) => d.method_name)} data={byPayment.map((d: any) => d.total)} />
      </div>
    </div>

    <!-- Monthly gallons table (per day × product) -->
    {#if period === 'monthly' && gallonsByPeriod.length > 0}
      {@const pivot = pivotMonthly(gallonsByPeriod)}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-6">
        <h3 class="text-sm font-semibold text-gray-700 px-4 md:px-6 py-4 border-b border-gray-200">Galones por Día y Producto</h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Fecha</th>
                <th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Diesel</th>
                <th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Súper</th>
                <th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Eco País</th>
                <th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              {#each pivot.rows as row}
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-1.5 font-medium text-gray-900">{row.label}</td>
                  <td class="px-4 py-1.5 text-right font-mono text-gray-600">{row.diesel > 0 ? row.diesel.toLocaleString('es-EC', {minimumFractionDigits:1}) : '—'}</td>
                  <td class="px-4 py-1.5 text-right font-mono text-gray-600">{row.super > 0 ? row.super.toLocaleString('es-EC', {minimumFractionDigits:1}) : '—'}</td>
                  <td class="px-4 py-1.5 text-right font-mono text-gray-600">{row.eco > 0 ? row.eco.toLocaleString('es-EC', {minimumFractionDigits:1}) : '—'}</td>
                  <td class="px-4 py-1.5 text-right font-mono font-semibold text-gray-900">{row.total.toLocaleString('es-EC', {minimumFractionDigits:1})}</td>
                </tr>
              {/each}
            </tbody>
            <tfoot class="bg-gray-50 border-t-2 border-gray-200">
              <tr>
                <td class="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Total</td>
                <td class="px-4 py-2 text-right font-mono font-bold text-gray-900">{pivot.totals.diesel.toLocaleString('es-EC', {minimumFractionDigits:1})}</td>
                <td class="px-4 py-2 text-right font-mono font-bold text-gray-900">{pivot.totals.super.toLocaleString('es-EC', {minimumFractionDigits:1})}</td>
                <td class="px-4 py-2 text-right font-mono font-bold text-gray-900">{pivot.totals.eco.toLocaleString('es-EC', {minimumFractionDigits:1})}</td>
                <td class="px-4 py-2 text-right font-mono font-bold text-gray-900">{pivot.totals.total.toLocaleString('es-EC', {minimumFractionDigits:1})}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    {/if}

    <!-- Top periods (monthly/annual only) -->
    {#if period !== 'daily' && topPeriods.length > 0}
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6 mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">
          {period === 'annual' ? 'Mejores Meses' : 'Mejores Días'}
        </h3>
        <TopPeriodsChart {period} data={topPeriods} limit={period === 'annual' ? 3 : 5} />
      </div>
    {/if}

    <!-- Today-only sections -->
    {#if isToday}
      {#if todayShifts.length > 0}
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-6">
          <h3 class="text-sm font-semibold text-gray-700 px-4 md:px-6 py-4 border-b border-gray-200">Turnos de Hoy</h3>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 text-sm">
              <thead class="bg-gray-50"><tr><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Turno</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Usuario</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Apertura</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Cierre</th><th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Estado</th><th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Sobrante</th><th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Faltante</th></tr></thead>
              <tbody class="divide-y divide-gray-100">
                {#each todayShifts as s}
                  <tr class="hover:bg-gray-50">
                    <td class="px-4 py-2 font-mono text-gray-900">#{s.shift_id}</td>
                    <td class="px-4 py-2 text-gray-700">{s.user_name || '—'}</td>
                    <td class="px-4 py-2 text-gray-600">{s.opened_at ? new Date(s.opened_at).toLocaleTimeString('es-EC', {hour:'2-digit',minute:'2-digit'}) : '—'}</td>
                    <td class="px-4 py-2 text-gray-600">{s.closed_at ? new Date(s.closed_at).toLocaleTimeString('es-EC', {hour:'2-digit',minute:'2-digit'}) : '—'}</td>
                    <td class="px-4 py-2">{#if s.status === 'OPEN'}<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700"><span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>Abierto</span>{:else}<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600"><span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>Cerrado</span>{/if}</td>
                    <td class="px-4 py-2 text-right font-mono text-green-600">{s.surplus > 0 ? formatCurrency(s.surplus) : '—'}</td>
                    <td class="px-4 py-2 text-right font-mono text-red-600">{s.shortage > 0 ? formatCurrency(s.shortage) : '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

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
    {/key}
  {/if}
</div>

<style>
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .dashboard-content {
    animation: fadeIn 0.25s ease-out;
  }
</style>
