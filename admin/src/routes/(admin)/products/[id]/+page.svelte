<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from 'svelte-sonner';

  let userId = $derived($page.params.id); let isNew = $derived(userId === 'new');

  interface Option { [key: string]: any; }
  let categories = $state<Option[]>([]);
  let taxTypes = $state<Option[]>([]);
  let form = $state({ code: '', name: '', category_id: 0, unit: 'UNIDAD', base_price: 0, subsidy_per_unit: null as number|null, tax_type_id: null as number|null, is_active: true });
  let loading = $state(false); let error = $state('');

  onMount(async () => {
    try { const c = await api.get<{items:Option[]}>('/products?page_size=100'); /* reuse existing */ } catch {}
    try { const r = await api.get<{items:Option[]}>('/../product-categories'); categories = Array.isArray(r)?r:(r as any).items||[]; } catch {}
    try { const t = await api.get<any[]>('/../tax-types'); taxTypes = t||[]; } catch { taxTypes = [{tax_type_id:1,code:'IVA_15',name:'IVA 15%'},{tax_type_id:2,code:'IVA_0',name:'IVA 0%'}]; }
    if (!isNew) {
      try {
        const p = await api.get<any>(`/products/${userId}`);
        form = { code: p.code, name: p.name, category_id: p.category_id, unit: p.unit, base_price: p.base_price, subsidy_per_unit: p.subsidy_per_unit, tax_type_id: p.tax_type_id, is_active: p.is_active };
      } catch (e: any) { error = e.message; }
    }
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
</div>
