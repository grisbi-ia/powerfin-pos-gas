<script lang="ts">
  import { Save, Building2 } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  let form = $state({ ruc:'', name:'', commercial_name:'', address:'', phone:'', email:'', city:'', province:'', country:'', fiscal_regime:'', sri_environment: null as number|null, emission_type: null as number|null });
  let loading = $state(true); let saving = $state(false); let error = $state('');

  $effect(() => { (async () => {
    try {
      const data = await api.get<any>('/company-info');
      form = { ruc: data.ruc || '', name: data.name || '', commercial_name: data.commercial_name || '', address: data.address || '',
               phone: data.phone || '', email: data.email || '', city: data.city || '', province: data.province || '',
               country: data.country || '', fiscal_regime: data.fiscal_regime || '', sri_environment: data.sri_environment,
               emission_type: data.emission_type };
    } catch (e: any) { error = e.message; } finally { loading = false; }
  })();
});

  async function handleSubmit(e: Event) {
    e.preventDefault(); saving = true; error = '';
    try {
      await api.put('/company-info', form);
      toast.success('Información actualizada');
    } catch (e: any) { error = e.message; toast.error(e.message); } finally { saving = false; }
  }
</script>

<div>
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Información de la Empresa</h1>
  {#if loading}
    <div class="flex justify-center py-12"><div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>
  {:else}
    {#if error}<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>{/if}
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-3xl">
      <form onsubmit={handleSubmit} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">RUC</label><input type="text" bind:value={form.ruc} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1 md:col-span-2"><label class="block text-sm font-medium text-gray-700">Razón Social</label><input type="text" bind:value={form.name} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Nombre Comercial</label><input type="text" bind:value={form.commercial_name} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Teléfono</label><input type="text" bind:value={form.phone} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Email</label><input type="email" bind:value={form.email} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1 md:col-span-2"><label class="block text-sm font-medium text-gray-700">Dirección</label><input type="text" bind:value={form.address} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Ciudad</label><input type="text" bind:value={form.city} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Provincia</label><input type="text" bind:value={form.province} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">País</label><input type="text" bind:value={form.country} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Régimen Fiscal</label><input type="text" bind:value={form.fiscal_regime} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"/></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Ambiente SRI</label><select bind:value={form.sri_environment} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"><option value={null}>--</option><option value={1}>1 - Pruebas</option><option value={2}>2 - Producción</option></select></div>
          <div class="space-y-1"><label class="block text-sm font-medium text-gray-700">Tipo Emisión</label><select bind:value={form.emission_type} class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"><option value={null}>--</option><option value={1}>1 - Normal</option></select></div>
        </div>
        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button type="submit" disabled={saving} class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"><Save class="w-4 h-4"/>{saving?'Guardando...':'Guardar'}</button>
        </div>
      </form>
    </div>
  {/if}
</div>
