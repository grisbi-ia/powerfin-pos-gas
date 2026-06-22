<script lang="ts">
  import { goto } from '$app/navigation';
  import { Pencil } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import StatusBadge from '$components/StatusBadge.svelte';
  import { api } from '$lib/api/api';
  import type { PaginatedResponse } from '$lib/types';

  interface Item { role_id: number; code: string; name: string; is_active: boolean; }
  let items = $state<Item[]>([]); let total=$state(0); let page=$state(1); let pages=$state(1);
  let loading=$state(true); let error=$state(''); let search=$state(''); let sortKey=$state('name'); let sortOrder=$state<'asc'|'desc'>('asc');

  async function load() {
    loading=true; error='';
    try { const d=await api.get<PaginatedResponse>(`/roles?search=${encodeURIComponent(search)}&page=${page}&page_size=10&sort=${sortKey}&order=${sortOrder}`); items=d.items; total=d.total; pages=d.pages; }
    catch(e:any){error=e.message;} finally{loading=false;}
  }
  $effect(() => { load(); });
</script>
<DataTable title="Roles" {items} columns={[{key:'name',label:'Nombre',sortable:true},{key:'code',label:'Código',sortable:true},{key:'is_active',label:'Estado',sortable:true}]}
  {loading}{error}{total}{page}{pages}{search}{sortKey}{sortOrder}
  onSearch={(q:string)=>{search=q;page=1;load()}} onSort={(k:string)=>{sortKey=k;sortOrder=sortOrder==='asc'?'desc':'asc';load()}}
  onPage={(p:number)=>{page=p;load()}} onCreate={()=>goto('/roles/new')}>
  {#snippet children({item}:{item:Item})}
    <button class="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg" onclick={()=>goto(`/roles/${item.role_id}`)}><Pencil class="w-4 h-4"/></button>
  {/snippet}
</DataTable>
