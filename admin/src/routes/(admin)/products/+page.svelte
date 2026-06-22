<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Pencil, Trash2 } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import StatusBadge from '$components/StatusBadge.svelte';
  import ConfirmDialog from '$components/ConfirmDialog.svelte';
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';

  interface ProductItem { product_id: number; code: string; name: string; category_name: string; unit: string; base_price: number; is_active: boolean; }

  let items = $state<ProductItem[]>([]);
  let total = $state(0); let page = $state(1); let pages = $state(1);
  let loading = $state(true); let error = $state('');
  let search = $state(''); let sortKey = $state('name'); let sortOrder = $state<'asc'|'desc'>('asc');
  let deleteTarget = $state<ProductItem | null>(null);

  async function load() {
    loading = true; error = '';
    try {
      const data = await api.get<any>(`/products?search=${encodeURIComponent(search)}&page=${page}&page_size=10&sort=${sortKey}&order=${sortOrder}`);
      items = data.items; total = data.total; pages = data.pages;
    } catch (e: any) { error = e.message; } finally { loading = false; }
  }
  async function handleDelete() {
    if (!deleteTarget) return;
    try { await api.delete(`/products/${deleteTarget.product_id}`); toast.success('Producto desactivado'); deleteTarget = null; load(); }
    catch (e: any) { toast.error(e.message); }
  }
  onMount(load);
</script>

<DataTable title="Productos" {items} columns={[{key:'name',label:'Nombre',sortable:true},{key:'code',label:'Código',sortable:true},{key:'category_name',label:'Categoría'},{key:'unit',label:'Unidad'},{key:'is_active',label:'Estado',sortable:true}]}
  {loading} {error} {total} {page} {pages} {search} {sortKey} {sortOrder}
  onSearch={(q: string) => { search = q; page = 1; load(); }}
  onSort={(k: string) => { sortKey = k; sortOrder = sortOrder==='asc'?'desc':'asc'; load(); }}
  onPage={(p: number) => { page = p; load(); }}
  onCreate={() => goto('/products/new')}>
  {#snippet children({ item }: { item: ProductItem })}
    <button class="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg" onclick={() => goto(`/products/${item.product_id}`)}><Pencil class="w-4 h-4"/></button>
    <button class="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg" onclick={() => deleteTarget = item}><Trash2 class="w-4 h-4"/></button>
  {/snippet}
</DataTable>
<ConfirmDialog open={deleteTarget!==null} title="Desactivar producto" message={`¿Desactivar "${deleteTarget?.name}"?`} confirmLabel="Desactivar" variant="danger" onConfirm={handleDelete} onCancel={()=>deleteTarget=null}/>
