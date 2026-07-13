<script lang="ts">
  import { goto } from '$app/navigation';
  import { FileText, Banknote } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import { posApi } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  interface Contract {
    contract_id: number;
    contract_code: string;
    person_name: string;
    contract_date: string;
    cupo: number;
    contract_type: string;
    sercop_type: string;
    available: number;
    is_active: boolean;
    vehicles: { plate: string }[];
    products: { product_name: string; amount: number }[];
  }

  let items = $state<Contract[]>([]);
  let loading = $state(true);
  let error = $state('');

  async function load() {
    loading = true; error = '';
    try {
      const data = await posApi.get<Contract[]>('/credit-contracts');
      items = data;
    } catch (e: any) {
      error = e.message;
      toast.error(error);
    } finally { loading = false; }
  }

  $effect(() => { load(); });

  function typeLabel(t: string) {
    return t === 'NO_INDEFINIDO' ? 'Sector Público' : t === 'INDEFINIDO' ? 'Privado' : t;
  }

  function availablePercent(c: Contract): number {
    if (c.cupo <= 0) return 0;
    return Math.round((c.available / c.cupo) * 100);
  }
</script>

<div class="p-6">
  <div class="mb-6">
    <h1 class="text-2xl font-bold text-gray-800">Contratos de Crédito</h1>
    <p class="text-gray-500 mt-1">Gestión de contratos activos y liquidación de sector público</p>
  </div>

  {#if loading}
    <div class="text-center py-12 text-gray-400">Cargando contratos...</div>
  {:else if error}
    <div class="bg-red-50 text-red-600 p-4 rounded-xl">{error}</div>
  {:else}
    <div class="grid gap-4">
      {#each items as c}
        <div class="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <FileText class="w-4 h-4 text-primary-500" />
                <span class="font-semibold text-gray-800">{c.contract_code}</span>
                <span class="text-xs px-2 py-0.5 rounded-full {c.contract_type === 'NO_INDEFINIDO' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}">
                  {typeLabel(c.contract_type)}
                </span>
                {#if c.sercop_type !== 'NO_DEFINIDO'}
                  <span class="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">{c.sercop_type}</span>
                {/if}
              </div>
              <div class="text-sm text-gray-500">{c.person_name}</div>
              <div class="flex items-center gap-4 mt-3">
                <div class="text-sm">
                  <span class="text-gray-400">Cupo total:</span>
                  <span class="font-medium text-gray-700">${c.cupo.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                </div>
                <div class="text-sm">
                  <span class="text-gray-400">Disponible:</span>
                  <span class="font-medium {c.available <= 0 ? 'text-red-600' : 'text-green-600'}">
                    ${c.available.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div class="flex-1 max-w-[200px]">
                  <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all {c.available <= 0 ? 'bg-red-500' : 'bg-primary-500'}"
                         style="width: {availablePercent(c)}%"></div>
                  </div>
                </div>
              </div>
              {#if c.products.length > 0}
                <div class="flex gap-2 mt-2 flex-wrap">
                  {#each c.products as p}
                    <span class="text-xs bg-gray-50 text-gray-600 px-2 py-0.5 rounded border border-gray-200">
                      {p.product_name}: ${p.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  {/each}
                </div>
              {/if}
            </div>
            <div class="flex-shrink-0 ml-4">
              {#if c.contract_type === 'NO_INDEFINIDO'}
                <button
                  class="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 text-sm font-medium"
                  onclick={() => goto(`/contracts/${c.contract_id}/liquidate`)}
                >
                  <Banknote class="w-4 h-4" />
                  Liquidar
                </button>
              {/if}
            </div>
          </div>
        </div>
      {/each}
      {#if items.length === 0}
        <div class="text-center py-12 text-gray-400">No hay contratos activos</div>
      {/if}
    </div>
  {/if}
</div>
