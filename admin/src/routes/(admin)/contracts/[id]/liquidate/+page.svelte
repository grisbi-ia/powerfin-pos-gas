<script lang="ts">
  import { page } from '$app/stores';
  import { ArrowLeft, FileText, Send, AlertTriangle, CheckCircle, Loader2 } from 'lucide-svelte';
  import { posApi } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  let contractId = $state(0);
  $effect(() => {
    contractId = Number($page.params.id);
    if (contractId) loadAll();
  });

  // Contract info
  interface ContractInfo {
    contract_id: number; contract_code: string; person_name: string;
    cupo: number; available: number; contract_type: string;
    sercop_type: string; products: { product_name: string; amount: number }[];
  }
  let contract = $state<ContractInfo | null>(null);

  // Pending dispatches
  interface PendingDispatch {
    dispatch_id: number; order_id: string; dispatch_date: string | null;
    plate: string | null; product_code: string; product_name: string;
    quantity: number; unit_price: number; subtotal: number; tax_amount: number; total: number;
  }
  let dispatches = $state<PendingDispatch[]>([]);
  let totalAmount = $state(0);

  // Emission points
  interface EmissionPoint { emission_point_id: number; establishment: string; emission_point: string; label: string; }
  let emissionPoints = $state<EmissionPoint[]>([]);
  let selectedEp = $state(0);

  // State
  let loading = $state(true);
  let sending = $state(false);
  let error = $state('');
  let result = $state<{ invoice_id: string | null; access_key: string | null; sri_status: string | null; errors: string[] } | null>(null);

  import { api } from '$lib/api/api';

  async function loadAll() {
    loading = true; error = '';
    try {
      // Load contract details
      const contracts = await posApi.get<any[]>('/credit-contracts');
      contract = contracts.find((c: any) => c.contract_id === contractId) || null;

      // Load pending dispatches
      dispatches = await posApi.get<PendingDispatch[]>(`/dispatches/pending-bulk?contract_id=${contractId}`);
      totalAmount = dispatches.reduce((sum, d) => sum + (d.total || 0), 0);

      // Load emission points
      const eps = await api.get<{ items: any[]; total: number; pages: number }>('/emission-points?page=1&page_size=50');
      emissionPoints = (eps.items || []).map((ep: any) => ({
        emission_point_id: ep.emission_point_id,
        establishment: ep.establishment,
        emission_point: ep.emission_point,
        label: `${ep.establishment}-${ep.emission_point}`,
      }));
      if (emissionPoints.length > 0 && !selectedEp) {
        selectedEp = emissionPoints[0].emission_point_id;
      }
    } catch (e: any) {
      error = e.message;
      toast.error(error);
    } finally { loading = false; }
  }

  async function handleLiquidate() {
    if (!selectedEp) { toast.error('Seleccione un punto de emisión'); return; }
    sending = true; result = null;
    try {
      const res = await posApi.post<{ invoice_id: string | null; access_key: string | null; sri_status: string | null; dispatch_count: number; errors: string[] }>('/dispatches/bulk-invoice', {
        contract_id: contractId,
        emission_point_id: selectedEp,
      });
      result = res;
      if (res.invoice_id) {
        toast.success(`Factura global emitida — ${res.dispatch_count} despachos liquidados`);
        await loadAll();
      } else if (res.errors?.length) {
        toast.error(res.errors[0]);
      }
    } catch (e: any) {
      toast.error(e.message);
    } finally { sending = false; }
  }
</script>

<div class="p-6 max-w-4xl">
  <a href="/contracts" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-primary-600 mb-4">
    <ArrowLeft class="w-4 h-4" /> Volver a Contratos
  </a>

  <h1 class="text-2xl font-bold text-gray-800 mb-1">Liquidación — Sector Público</h1>
  <p class="text-gray-500 mb-6">Emitir factura global para todos los despachos pendientes del contrato</p>

  {#if loading}
    <div class="flex items-center gap-2 text-gray-400 py-12 justify-center">
      <Loader2 class="w-5 h-5 animate-spin" /> Cargando...
    </div>
  {:else if error}
    <div class="bg-red-50 text-red-600 p-4 rounded-xl">{error}</div>
  {:else}
    <!-- Contract Summary -->
    {#if contract}
      <div class="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div class="flex items-center gap-2 mb-2">
          <FileText class="w-5 h-5 text-primary-500" />
          <span class="font-bold text-lg">{contract.contract_code}</span>
          <span class="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
            {contract.contract_type === 'NO_INDEFINIDO' ? 'Sector Público' : contract.contract_type}
          </span>
          {#if contract.sercop_type !== 'NO_DEFINIDO'}
            <span class="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">{contract.sercop_type}</span>
          {/if}
        </div>
        <div class="text-gray-600">{contract.person_name}</div>
        <div class="grid grid-cols-3 gap-4 mt-4 text-sm">
          <div>
            <div class="text-gray-400">Cupo total</div>
            <div class="font-semibold">${contract.cupo.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
          </div>
          <div>
            <div class="text-gray-400">Disponible</div>
            <div class="font-semibold">${contract.available.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
          </div>
          <div>
            <div class="text-gray-400">Productos</div>
            <div class="font-semibold">
              {#each contract.products as p}
                <span class="mr-2">{p.product_name}</span>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}

    <!-- Pending Dispatches -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
      <div class="px-5 py-3 bg-gray-50 border-b border-gray-200">
        <h2 class="font-semibold text-gray-700">
          Despachos pendientes de facturar
          <span class="text-gray-400 font-normal">({dispatches.length})</span>
        </h2>
      </div>

      {#if dispatches.length === 0}
        <div class="p-8 text-center text-gray-400">
          {#if result?.invoice_id}
            <div class="flex items-center justify-center gap-2 text-green-600 mb-2">
              <CheckCircle class="w-5 h-5" /> ¡Liquidación completada!
            </div>
            <p class="text-sm">No hay despachos pendientes. Todos fueron facturados.</p>
            {#if result && result.access_key}
              <p class="text-xs text-gray-400 mt-2 font-mono break-all">Clave SRI: {result.access_key}</p>
            {/if}
          {:else}
            <AlertTriangle class="w-5 h-5 text-gray-300 mx-auto mb-2" />
            No hay despachos pendientes de facturar para este contrato.
          {/if}
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-gray-500 border-b border-gray-100">
                <th class="px-5 py-2 font-medium">Fecha</th>
                <th class="px-5 py-2 font-medium">Placa</th>
                <th class="px-5 py-2 font-medium">Producto</th>
                <th class="px-5 py-2 font-medium text-right">Galones</th>
                <th class="px-5 py-2 font-medium text-right">Precio</th>
                <th class="px-5 py-2 font-medium text-right">Subtotal</th>
                <th class="px-5 py-2 font-medium text-right">IVA</th>
                <th class="px-5 py-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {#each dispatches as d}
                <tr class="border-b border-gray-50 hover:bg-gray-50">
                  <td class="px-5 py-2 text-gray-600 whitespace-nowrap">
                    {d.dispatch_date ? new Date(d.dispatch_date).toLocaleDateString('es-EC') : '-'}
                  </td>
                  <td class="px-5 py-2 font-mono text-gray-700">{d.plate || '-'}</td>
                  <td class="px-5 py-2">
                    <span class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">{d.product_name}</span>
                  </td>
                  <td class="px-5 py-2 text-right text-gray-600">{d.quantity.toFixed(2)}</td>
                  <td class="px-5 py-2 text-right text-gray-600">${d.unit_price.toFixed(4)}</td>
                  <td class="px-5 py-2 text-right text-gray-700">${d.subtotal.toFixed(2)}</td>
                  <td class="px-5 py-2 text-right text-gray-500">${d.tax_amount.toFixed(2)}</td>
                  <td class="px-5 py-2 text-right font-medium text-gray-800">${d.total.toFixed(2)}</td>
                </tr>
              {/each}
            </tbody>
            <tfoot>
              <tr class="bg-gray-50 font-semibold">
                <td colspan="7" class="px-5 py-3 text-right text-gray-600">Total acumulado:</td>
                <td class="px-5 py-3 text-right text-primary-600 text-base">
                  ${totalAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      {/if}
    </div>

    <!-- Action Section -->
    {#if dispatches.length > 0}
      <div class="bg-white rounded-xl border border-gray-200 p-5">
        <h3 class="font-semibold text-gray-700 mb-3">Emitir Factura Global</h3>

        <!-- Emission Point Selector -->
        <div class="mb-4">
          <label class="block text-sm text-gray-500 mb-1">Punto de emisión para la factura</label>
          <select bind:value={selectedEp} class="w-full max-w-xs border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value={0} disabled>Seleccione...</option>
            {#each emissionPoints as ep}
              <option value={ep.emission_point_id}>{ep.label}</option>
            {/each}
          </select>
        </div>

        <div class="flex items-center gap-3">
          <button
            class="flex items-center gap-2 px-6 py-2.5 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 font-medium"
            onclick={handleLiquidate}
            disabled={sending || !selectedEp}
          >
            {#if sending}
              <Loader2 class="w-4 h-4 animate-spin" /> Enviando...
            {:else}
              <Send class="w-4 h-4" /> Emitir Factura Global al SRI
            {/if}
          </button>

          {#if result?.errors?.length}
            <span class="text-sm text-red-600 flex items-center gap-1">
              <AlertTriangle class="w-4 h-4" /> {result!.errors[0]}
            </span>
          {/if}
        </div>

        <p class="text-xs text-gray-400 mt-3">
          Se generará <strong>una sola factura electrónica</strong> con los {dispatches.length} despachos como ítems.
          Todos los despachos pasarán a estado INVOICED.
        </p>
      </div>
    {/if}
  {/if}
</div>
