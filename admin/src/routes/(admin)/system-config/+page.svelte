<script lang="ts">
  import { Check, X, Save } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  interface ConfigItem { key:string; value:string; description:string|null }
  let configs = $state<ConfigItem[]>([]);
  let loading = $state(true); let error = $state('');
  let editKey = $state(''); let editValue = $state(''); let editDesc = $state(''); let saving = $state(false);

  $effect(() => { (async () => {
    try { configs = await api.get<ConfigItem[]>('/system-config'); } catch(e:any) { error=e.message; } finally { loading=false; }
  })();
});

  function startEdit(item:ConfigItem) { editKey=item.key; editValue=item.value; editDesc=item.description||''; }
  function cancelEdit() { editKey=''; }

  async function saveEdit() {
    saving=true;
    try {
      const result = await api.put<ConfigItem>(`/system-config/${encodeURIComponent(editKey)}`, {value:editValue,description:editDesc});
      const idx = configs.findIndex(c=>c.key===editKey);
      if(idx>=0) configs[idx] = result; else configs.push(result);
      configs = [...configs];
      editKey=''; toast.success('Configuración actualizada');
    } catch(e:any) { toast.error(e.message); } finally { saving=false; }
  }
</script>

<div>
  <h1 class="text-2xl font-bold text-gray-900 mb-6">Configuración del Sistema</h1>
  {#if loading}
    <div class="flex justify-center py-12"><div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div></div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
  {:else}
    <div class="bg-white rounded-lg shadow-sm border border-gray-200">
      <div class="hidden md:block overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50"><tr><th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Key</th><th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Valor</th><th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Descripción</th><th class="px-4 py-3 w-24"></th></tr></thead>
          <tbody class="divide-y divide-gray-100">
            {#each configs as item}
              {#if editKey === item.key}
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-2 text-sm font-mono text-gray-900">{item.key}</td>
                  <td class="px-4 py-2"><input type="text" bind:value={editValue} class="w-full px-2 py-1 text-sm border border-primary-300 rounded focus:outline-none focus:ring-2 focus:ring-primary-500"/></td>
                  <td class="px-4 py-2"><input type="text" bind:value={editDesc} class="w-full px-2 py-1 text-sm border border-primary-300 rounded focus:outline-none focus:ring-2 focus:ring-primary-500"/></td>
                  <td class="px-4 py-2 flex gap-1">
                    <button class="p-1.5 text-green-600 hover:bg-green-50 rounded" onclick={saveEdit} disabled={saving}><Check class="w-4 h-4"/></button>
                    <button class="p-1.5 text-gray-400 hover:bg-gray-100 rounded" onclick={cancelEdit}><X class="w-4 h-4"/></button>
                  </td>
                </tr>
              {:else}
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-3 text-sm font-mono text-gray-900">{item.key}</td>
                  <td class="px-4 py-3 text-sm text-gray-700 max-w-xs truncate">{item.value}</td>
                  <td class="px-4 py-3 text-sm text-gray-500">{item.description || '—'}</td>
                  <td class="px-4 py-3"><button class="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded" onclick={()=>startEdit(item)}><Save class="w-4 h-4"/></button></td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
      <div class="md:hidden divide-y divide-gray-100">
        {#each configs as item}
          <div class="px-4 py-3"><div class="text-sm font-mono text-gray-900">{item.key}</div><div class="text-sm text-gray-700 mt-1">{item.value}</div></div>
        {/each}
      </div>
    </div>
  {/if}
</div>
