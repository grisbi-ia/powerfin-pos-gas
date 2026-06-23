<script lang="ts">
  import { api } from '$lib/api/api';
  import { RefreshCw, Wifi, WifiOff, Power } from 'lucide-svelte';

  let dispensers: any[] = $state([]);
  let fusionConnected = $state(false);
  let loading = $state(true);
  let error = $state('');
  let lastRefresh = $state('');

  function statusColor(status: string): string {
    switch (status) {
      case 'IDLE': return 'bg-green-500';
      case 'CALLING': return 'bg-blue-500';
      case 'AUTHORIZED': return 'bg-yellow-500';
      case 'STARTING':
      case 'FUELLING': return 'bg-orange-500 animate-pulse';
      case 'STOPPED':
      case 'ERROR':
      case 'CLOSED': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  }

  function statusLabel(status: string): string {
    const labels: Record<string, string> = {
      IDLE: 'Disponible', CALLING: 'Llamando', AUTHORIZED: 'Autorizado',
      STARTING: 'Iniciando', FUELLING: 'Despachando', STOPPED: 'Detenido',
      CLOSED: 'Cerrado', ERROR: 'Error',
    };
    return labels[status] ?? status;
  }

  function statusBg(status: string): string {
    switch (status) {
      case 'IDLE': return 'bg-green-50 border-green-200';
      case 'CALLING': return 'bg-blue-50 border-blue-200';
      case 'AUTHORIZED': return 'bg-yellow-50 border-yellow-200';
      case 'STARTING':
      case 'FUELLING': return 'bg-orange-50 border-orange-200';
      case 'STOPPED':
      case 'ERROR':
      case 'CLOSED': return 'bg-red-50 border-red-200';
      default: return 'bg-gray-50 border-gray-200';
    }
  }

  function hasActiveHose(status: string): boolean {
    return ['AUTHORIZED', 'CALLING', 'STARTING', 'FUELLING'].includes(status);
  }

  async function refresh() {
    loading = true; error = '';
    try {
      const data = await api.get<any>('/dispensers/status');
      dispensers = data.dispensers || [];
      fusionConnected = data.fusion_connected || false;
      const now = new Date();
      lastRefresh = now.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e: any) {
      error = e.message || 'Error al consultar estado';
    } finally {
      loading = false;
    }
  }

  $effect(() => { refresh(); });
</script>

<div>
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Surtidores — Estado Vivo</h1>
    <div class="flex items-center gap-3">
      {#if lastRefresh}
        <span class="text-xs text-gray-400 hidden sm:inline">Actualizado: {lastRefresh}</span>
      {/if}
      <button onclick={refresh} disabled={loading}
              class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors">
        <RefreshCw class="w-4 h-4 {loading ? 'animate-spin' : ''}" />
        Refrescar
      </button>
    </div>
  </div>

  <!-- Fusion connection indicator -->
  <div class="flex items-center gap-2 mb-4">
    {#if fusionConnected}
      <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
        <Wifi class="w-3.5 h-3.5" /> FusionBridge conectado
      </span>
    {:else}
      <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
        <WifiOff class="w-3.5 h-3.5" /> FusionBridge desconectado
      </span>
    {/if}
  </div>

  {#if loading && dispensers.length === 0}
    <div class="flex justify-center py-12">
      <div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-4">{error}</div>
    {#if dispensers.length === 0}
      <div class="text-center py-12 text-gray-400">
        <Power class="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p class="text-sm">No se pudo obtener el estado de los surtidores.</p>
        <p class="text-xs mt-1">Verifique que FusionBridge esté corriendo en el servidor.</p>
      </div>
    {/if}
  {:else if dispensers.length === 0}
    <div class="text-center py-12 text-gray-400">
      <Power class="w-12 h-12 mx-auto mb-3 opacity-30" />
      <p class="text-sm">No hay surtidores configurados.</p>
    </div>
  {:else}
    <!-- Dispenser cards grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {#each dispensers as d}
        <div class="rounded-xl border-2 shadow-sm overflow-hidden {statusBg(d.status)} {!d.connected ? 'opacity-60' : ''}">
          <!-- Header -->
          <div class="px-4 py-3 flex items-center justify-between border-b {d.connected ? 'border-gray-200' : 'border-red-200'}">
            <div>
              <h3 class="font-semibold text-gray-900 text-sm">{d.name}</h3>
              <p class="text-xs text-gray-500">#{d.dispenser_id}</p>
            </div>
            <div class="flex items-center gap-2">
              {#if !d.connected}
                <span class="text-xs text-red-500 font-medium flex items-center gap-1"><WifiOff class="w-3 h-3"/>Offline</span>
              {:else}
                <span class="text-xs text-green-600 font-medium flex items-center gap-1"><Wifi class="w-3 h-3"/>Online</span>
              {/if}
            </div>
          </div>

          <!-- Status indicator -->
          <div class="px-4 py-3">
            <div class="flex items-center gap-2 mb-3">
              <span class="w-2.5 h-2.5 rounded-full flex-shrink-0 {statusColor(d.status)}"></span>
              <span class="text-sm font-medium text-gray-700">{statusLabel(d.status)}</span>
              {#if d.preset_amount > 0 && hasActiveHose(d.status)}
                <span class="text-xs bg-white/60 text-gray-600 px-2 py-0.5 rounded-full">${d.preset_amount.toFixed(2)}</span>
              {/if}
            </div>

            <!-- Hoses -->
            <div class="space-y-1.5">
              {#each d.hoses as h}
                <div class="flex items-center justify-between text-xs py-1 px-2 rounded {h.active ? 'bg-white/70 font-medium' : ''}">
                  <span>
                    <span class="text-gray-500">Lado</span>
                    <span class="ml-1.5 font-mono text-gray-800">{h.side}</span>
                  </span>
                  <span class="text-gray-500">{h.grade}</span>
                  {#if h.active && hasActiveHose(d.status)}
                    <span class="text-orange-600 font-medium">● Activo</span>
                  {:else}
                    <span class="text-gray-400">—</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
