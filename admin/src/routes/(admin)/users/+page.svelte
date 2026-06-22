<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Pencil, Trash2 } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import StatusBadge from '$components/StatusBadge.svelte';
  import ConfirmDialog from '$components/ConfirmDialog.svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';
  import type { PaginatedResponse, UserListItem } from '$lib/types';

  let items = $state<UserListItem[]>([]);
  let total = $state(0);
  let page = $state(1);
  let pages = $state(1);
  let loading = $state(true);
  let error = $state('');
  let search = $state('');
  let sortKey = $state('name');
  let sortOrder = $state<'asc' | 'desc'>('asc');

  let deleteTarget = $state<UserListItem | null>(null);

  const columns = [
    { key: 'name', label: 'Nombre', sortable: true },
    { key: 'username', label: 'Usuario', sortable: true },
    { key: 'role_name', label: 'Rol', sortable: true },
    { key: 'is_active', label: 'Estado', sortable: true },
  ];

  async function load() {
    loading = true;
    error = '';
    try {
      const data = await api.get<PaginatedResponse>(
        `/users?search=${encodeURIComponent(search)}&page=${page}&page_size=10&sort=${sortKey}&order=${sortOrder}`
      );
      items = data.items;
      total = data.total;
      pages = data.pages;
    } catch (err: any) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await api.delete(`/users/${deleteTarget.user_id}`);
      toast.success(`Usuario ${deleteTarget.name} desactivado`);
      deleteTarget = null;
      load();
    } catch (err: any) {
      toast.error(err.message);
    }
  }

  onMount(load);
</script>

<DataTable title="Usuarios" {items} {columns} {loading} {error} {total} {page} {pages}
  {search} {sortKey} {sortOrder}
  onSearch={(q: string) => { search = q; page = 1; load(); }}
  onSort={(k: string) => { sortKey = k; sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'; load(); }}
  onPage={(p: number) => { page = p; load(); }}
  onCreate={() => goto('/users/new')}
>
  {#snippet children({ item }: { item: UserListItem })}
    <button class="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
            onclick={() => goto(`/users/${item.user_id}`)}>
      <Pencil class="w-4 h-4" />
    </button>
    <button class="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
            onclick={() => deleteTarget = item}>
      <Trash2 class="w-4 h-4" />
    </button>
  {/snippet}
</DataTable>

<ConfirmDialog open={deleteTarget !== null}
  title="Desactivar usuario"
  message={`¿Está seguro de desactivar a "${deleteTarget?.name}"?`}
  confirmLabel="Desactivar"
  variant="danger"
  onConfirm={handleDelete}
  onCancel={() => deleteTarget = null}
/>
