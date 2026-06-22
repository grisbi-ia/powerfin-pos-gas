<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft, Save } from 'lucide-svelte';
  import { api } from '$lib/api/api';
  import { toast } from 'svelte-sonner';
  import type { UserDetail, RoleOption } from '$lib/types';

  let userId = $derived($page.params.id);
  let isNew = $derived(userId === 'new');

  let form = $state({
    username: '',
    name: '',
    password: '',
    role_id: 0,
    accounting_cash_code: '',
    is_active: true,
  });
  let roles = $state<RoleOption[]>([]);
  let loading = $state(false);
  let error = $state('');

  onMount(async () => {
    try {
      const rolesData = await api.get<{ items: RoleOption[] }>('/roles?page_size=100');
      roles = rolesData.items;
    } catch { /* ignore */ }

    if (!isNew) {
      try {
        const user = await api.get<UserDetail>(`/users/${userId}`);
        form = {
          username: user.username,
          name: user.name,
          password: '',
          role_id: user.role_id,
          accounting_cash_code: user.accounting_cash_code || '',
          is_active: user.is_active,
        };
      } catch (err: any) {
        error = err.message;
      }
    }
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    loading = true;
    error = '';
    try {
      const body: any = { name: form.name, role_id: form.role_id, is_active: form.is_active };
      if (form.accounting_cash_code !== undefined) body.accounting_cash_code = form.accounting_cash_code || null;
      if (isNew) {
        body.username = form.username;
        body.password = form.password;
        await api.post('/users', body);
        toast.success('Usuario creado');
      } else {
        if (form.password) body.password = form.password;
        await api.put(`/users/${userId}`, body);
        toast.success('Usuario actualizado');
      }
      goto('/users');
    } catch (err: any) {
      error = err.message;
      toast.error(err.message);
    } finally {
      loading = false;
    }
  }
</script>

<div>
  <div class="flex items-center gap-4 mb-6">
    <button onclick={() => goto('/users')}
            class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
      <ArrowLeft class="w-5 h-5" />
    </button>
    <h1 class="text-2xl font-bold text-gray-900">{isNew ? 'Nuevo Usuario' : 'Editar Usuario'}</h1>
  </div>

  {#if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">{error}</div>
  {/if}

  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-2xl">
    <form onsubmit={handleSubmit} class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-1">
          <label for="username" class="block text-sm font-medium text-gray-700">Usuario <span class="text-red-500">*</span></label>
          <input id="username" type="text" bind:value={form.username} required disabled={!isNew}
                 class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                        focus:outline-none focus:ring-2 focus:ring-primary-500
                        disabled:bg-gray-100" />
        </div>
        <div class="space-y-1">
          <label for="name" class="block text-sm font-medium text-gray-700">Nombre <span class="text-red-500">*</span></label>
          <input id="name" type="text" bind:value={form.name} required
                 class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                        focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div class="space-y-1">
          <label for="password" class="block text-sm font-medium text-gray-700">
            Contraseña {isNew ? '<span class="text-red-500">*</span>' : ''}
          </label>
          <input id="password" type="password" bind:value={form.password}
                 required={isNew} minlength={isNew ? 4 : 0}
                 class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                        focus:outline-none focus:ring-2 focus:ring-primary-500"
                 placeholder={isNew ? 'Mínimo 4 caracteres' : '•••• (dejar vacío para no cambiar)'} />
        </div>
        <div class="space-y-1">
          <label for="role" class="block text-sm font-medium text-gray-700">Rol <span class="text-red-500">*</span></label>
          <select id="role" bind:value={form.role_id} required
                  class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                         focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value={0}>Seleccionar rol...</option>
            {#each roles as r}
              <option value={r.role_id}>{r.name}</option>
            {/each}
          </select>
        </div>
        <div class="space-y-1">
          <label for="cash_code" class="block text-sm font-medium text-gray-700">Código Contable Caja</label>
          <input id="cash_code" type="text" bind:value={form.accounting_cash_code}
                 class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md
                        focus:outline-none focus:ring-2 focus:ring-primary-500" />
        </div>
        <div class="space-y-1 flex items-end pb-1">
          <label class="inline-flex items-center gap-2 cursor-pointer">
            <input type="checkbox" bind:checked={form.is_active}
                   class="w-4 h-4 text-primary-500 border-gray-300 rounded focus:ring-primary-500" />
            <span class="text-sm text-gray-700">Activo</span>
          </label>
        </div>
      </div>

      <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <button type="button" onclick={() => goto('/users')}
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300
                       rounded-lg hover:bg-gray-50 transition-colors">
          Cancelar
        </button>
        <button type="submit" disabled={loading}
                class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm
                       font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors">
          <Save class="w-4 h-4" />
          {loading ? 'Guardando...' : 'Guardar'}
        </button>
      </div>
    </form>
  </div>
</div>
