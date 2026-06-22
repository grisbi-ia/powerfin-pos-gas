<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/api';
  import { formatCurrency } from '$lib/utils/format';
  import { DollarSign, ShoppingCart, Receipt, Users } from 'lucide-svelte';
  import KpiCard from '$components/KpiCard.svelte';
  import type { DashboardSummary } from '$lib/types';

  let summary = $state<DashboardSummary | null>(null);
  let loading = $state(true);
  let error = $state('');

  onMount(async () => {
    try {
      summary = await api.get<DashboardSummary>('/dashboard/summary');
    } catch (err: any) {
      error = err.message;
    } finally {
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
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <KpiCard title="Ventas Totales" value={formatCurrency(summary.total_sales)} icon={DollarSign} color="blue" />
      <KpiCard title="Despachos" value={String(summary.dispatch_count)} icon={ShoppingCart} color="green" />
      <KpiCard title="Ticket Promedio" value={formatCurrency(summary.avg_ticket)} icon={Receipt} color="purple" />
      <KpiCard title="Turnos Activos" value={String(summary.active_shifts)} icon={Users} color="orange" />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Efectivo vs No Efectivo</h3>
        <div class="space-y-3">
          <div>
            <div class="flex justify-between text-sm mb-1">
              <span class="text-gray-600">Efectivo</span>
              <span class="font-medium">{formatCurrency(summary.cash_collected)}</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div class="bg-green-500 h-2 rounded-full" style="width: {summary.total_sales > 0 ? (summary.cash_collected / summary.total_sales * 100) : 0}%"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-sm mb-1">
              <span class="text-gray-600">No Efectivo</span>
              <span class="font-medium">{formatCurrency(summary.non_cash_collected)}</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div class="bg-blue-500 h-2 rounded-full" style="width: {summary.total_sales > 0 ? (summary.non_cash_collected / summary.total_sales * 100) : 0}%"></div>
            </div>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Rango de Fechas</h3>
        <p class="text-sm text-gray-500">Desde: {summary.date_from}</p>
        <p class="text-sm text-gray-500">Hasta: {summary.date_to}</p>
      </div>
    </div>
  {/if}
</div>
