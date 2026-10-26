<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save, Plus, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { formatCurrency, formatDate } from '$lib/utils/format';
  import { toast } from '$lib/utils/toast';

  let userId = $derived($page.params.id); let isNew = $derived(userId === 'new');

  interface Option { [key: string]: any; }
  let categories = $state<Option[]>([]);
  let taxTypes = $state<Option[]>([]);
  let form = $state({ code: '', name: '', category_id: 0, unit: 'UNIDAD', base_price: 0, subsidy_per_unit: null as number|null, tax_type_id: null as number|null, is_active: true });
  let loading = $state(false); let error = $state('');

  // Effective-dated purchase costs (net of VAT)
  let costs = $state<any[]>([]);
  let costLoading = $state(false);
  let costError = $state('');
  let savingCost = $state(false);
  let costForm = $state({ valid_from: toLocalDate(new Date()), cost_price: 0, notes: '' });

  function toLocalDate(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  async function loadCosts() {
    if (isNew) return;
    costLoading = true; costError = '';
    try { costs = await api.get<any[]>(`/products/${userId}/costs`); }
    catch (e: any) { costError = e.message; }
    finally { costLoading = false; }
  }

  async function addCost(e: Event) {
    e.preventDefault();
    savingCost = true; costError = '';
    try {
      await api.post(`/products/${userId}/costs`, {
        valid_from: costForm.valid_from,
        cost_price: costForm.cost_price,
        notes: costForm.notes || null,
        source: 'MANUAL',
      });
      toast.success('Costo agregado');
      costForm.cost_price = 0; costForm.notes = '';
      await loadCosts();
    } catch (e: any) {
      costError = e.message; toast.error(e.message);
    } finally { savingCost = false; }
  }

  async function removeCost(cost: any) {
    if (!confirm(`¿Eliminar el costo de ${formatCurrency(cost.cost_price)} desde ${formatDate(cost.valid_from)}?`)) return;
    try {
      await api.delete(`/products/${userId}/costs/${cost.product_cost_id}`);
      toast.success('Costo eliminado');
      await loadCosts();
    } catch (e: any) { toast.error(e.message); }
  }

  $effect(() => { (async () => {
    try { const c = await api.get<{items:Option[]}>('/products?page_size=100'); /* reuse existing */ } catch {}
    try { const r = await api.get<{items:Option[]}>('/../product-categories'); categories = Array.isArray(r)?r:(r as any).items||[]; } catch {}
    try { const t = await api.get<any[]>('/../tax-types'); taxTypes = t||[]; } catch { taxTypes = [{tax_type_id:1,code:'IVA_15',name:'IVA 15%'},{tax_type_id:2,code:'IVA_0',name:'IVA 0%'}]; }
    if (!isNew) {
      try {
        const p = await api.get<any>(`/products/${userId}`);
        form = { code: p.code, name: p.name, category_id: p.category_id, unit: p.unit, base_price: p.base_price, subsidy_per_unit: p.subsidy_per_unit, tax_type_id: p.tax_type_id, is_active: p.is_active };
        await loadCosts();
      } catch (e: any) { error = e.message; }
    }
  })();
});

  async function handleSubmit(e: Event) {
    e.preventDefault(); loading = true; error = '';
    try {
      const body: any = { name: form.name, category_id: form.category_id, unit: form.unit, base_price: form.base_price, subsidy_per_unit: form.subsidy_per_unit, tax_type_id: form.tax_type_id, is_active: form.is_active };
      if (isNew) { body.code = form.code; await api.post('/products', body); toast.success('Producto creado'); }
      else { await api.put(`/products/${userId}`, body); toast.success('Producto actualizado'); }
      goto('/products');
    } catch (e: any) { error = e.message; toast.error(e.message); } finally { loading = false; }
  }
</script>

<div>
  <div class="flex items-center gap-4 mb-6">
    <button onclick={() => goto('/products')} class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"><ArrowLeft class="w-5 h-5"/></button>
    <h1 class="text-2xl font-bold text-gray-900">{isNew ? 'Nuevo Producto' : 'Editar Producto'}</h1>
  </div>
  {#if error}<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>{/if}
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-2xl">
    <form onsubmit={handleSubmit} class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Código <span class="text-red-500">*</span></label><input type="text" bind:value={form.code} required disabled={!isNew} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Nombre <span class="text-red-500">*</span></label><input type="text" bind:value={form.name} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Categoría <span class="text-red-500">*</span></label><select bind:value={form.category_id} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"><option value={0}>Seleccionar...</option>{#each categories as c}<option value={c.category_id}>{c.name}</option>{/each}</select></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Unidad</label><input type="text" bind:value={form.unit} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Precio Base</label><input type="number" step="0.0001" bind:value={form.base_price} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Subsidio por Unidad</label><input type="number" step="0.0001" bind:value={form.subsidy_per_unit} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
        <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Tipo de Impuesto</label><select bind:value={form.tax_type_id} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"><option value={null}>Ninguno</option>{#each taxTypes as t}<option value={t.tax_type_id}>{t.name} ({(t.rate*100).toFixed(0)}%)</option>{/each}</select></div>
        <div class="space-y-1 flex items-end pb-1"><label class="inline-flex items-center gap-2 cursor-pointer"><input type="checkbox" bind:checked={form.is_active} class="w-4 h-4 text-primary-500 border-gray-300 rounded"/><span class="text-sm text-gray-700">Activo</span></label></div>
      </div>
      <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <button type="button" onclick={()=>goto('/products')} class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancelar</button>
        <button type="submit" disabled={loading} class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"><Save class="w-4 h-4"/>{loading?'Guardando...':'Guardar'}</button>
      </div>
    </form>
  </div>

  {#if isNew}
    <div class="mt-6 bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-600">
      Guarda el producto para poder cargar su historial de costos de compra.
    </div>
  {:else}
    <div class="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-4xl">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">Historial de costos de compra</h2>
          <p class="text-xs text-gray-500 mt-1">
            Costos <strong>netos (sin IVA)</strong> por unidad. Cada fila rige desde su fecha
            hasta el día anterior a la siguiente. Los despachos ya cobrados conservan el costo
            congelado al momento de la venta.
          </p>
        </div>
      </div>

      {#if costError}
        <div class="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm mb-4">{costError}</div>
      {/if}

      <form onsubmit={addCost} class="grid grid-cols-1 md:grid-cols-4 gap-3 items-end mb-5">
        <div class="space-y-1">
          <label class="block text-xs font-medium text-gray-600">Desde</label>
          <input type="date" bind:value={costForm.valid_from} required class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/>
        </div>
        <div class="space-y-1">
          <label class="block text-xs font-medium text-gray-600">Costo sin IVA</label>
          <input type="number" step="0.0001" min="0" bind:value={costForm.cost_price} required placeholder="0.0000" class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/>
        </div>
        <div class="space-y-1">
          <label class="block text-xs font-medium text-gray-600">Nota (opcional)</label>
          <input type="text" bind:value={costForm.notes} maxlength="255" class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/>
        </div>
        <button type="submit" disabled={savingCost} class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50">
          <Plus class="w-4 h-4"/>{savingCost ? 'Guardando...' : 'Agregar vigencia'}
        </button>
      </form>

      {#if costLoading}
        <p class="text-sm text-gray-500">Cargando costos...</p>
      {:else if costs.length === 0}
        <p class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
          No hay costos cargados. Sin costo, la utilidad del dashboard queda marcada como incompleta.
        </p>
      {:else}
        <div class="overflow-x-auto border border-gray-200 rounded-lg">
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Desde</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Hasta</th>
                <th class="px-4 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Costo sin IVA</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Origen</th>
                <th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Nota</th>
                <th class="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              {#each costs as cost}
                <tr class={cost.is_current ? 'bg-teal-50/60' : 'hover:bg-gray-50'}>
                  <td class="px-4 py-2 font-medium text-gray-900">{formatDate(cost.valid_from)}</td>
                  <td class="px-4 py-2 text-gray-600">{cost.valid_to ? formatDate(cost.valid_to) : 'Vigente'}</td>
                  <td class="px-4 py-2 text-right font-mono font-semibold text-gray-900">{formatCurrency(cost.cost_price)}</td>
                  <td class="px-4 py-2">
                    <span class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium {cost.source === 'EXAMPLE' ? 'bg-amber-100 text-amber-800' : cost.source === 'ERP' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'}">
                      {cost.source}
                    </span>
                    {#if cost.is_current}<span class="ml-1 text-xs text-teal-700 font-medium">vigente</span>{/if}
                  </td>
                  <td class="px-4 py-2 text-gray-500 text-xs">{cost.notes || '—'}</td>
                  <td class="px-4 py-2 text-right">
                    <button type="button" onclick={() => removeCost(cost)} class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded" title="Eliminar vigencia">
                      <Trash2 class="w-4 h-4"/>
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>
