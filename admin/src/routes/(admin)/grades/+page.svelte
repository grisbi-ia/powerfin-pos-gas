<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Pencil, Trash2 } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import ConfirmDialog from '$components/ConfirmDialog.svelte';
  import { api } from '$lib/api/api';
  import { toast } from 'svelte-sonner';

  interface Item { grade_id:number; code:string; name:string; product_name:string; is_active:boolean }
  let items=$state<Item[]>([]); let total=$state(0); let page=$state(1); let pages=$state(1);
  let loading=$state(true); let error=$state(''); let search=$state(''); let sortKey=$state('name'); let sortOrder=$state<'asc'|'desc'>('asc');
  let deleteTarget=$state<Item|null>(null);

  async function load(){loading=true;error='';try{const d=await api.get<any>(`/grades?search=${encodeURIComponent(search)}&page=${page}&page_size=10&sort=${sortKey}&order=${sortOrder}`);items=d.items;total=d.total;pages=d.pages}catch(e:any){error=e.message}finally{loading=false}}
  async function handleDelete(){if(!deleteTarget)return;try{await api.delete(`/grades/${deleteTarget.grade_id}`);toast.success('Grado desactivado');deleteTarget=null;load()}catch(e:any){toast.error(e.message)}}
  onMount(load);
</script>
<DataTable title="Grados" {items} columns={[{key:'name',label:'Nombre',sortable:true},{key:'code',label:'Código',sortable:true},{key:'product_name',label:'Producto'},{key:'is_active',label:'Estado',sortable:true}]}
  {loading}{error}{total}{page}{pages}{search}{sortKey}{sortOrder}
  onSearch={(q:string)=>{search=q;page=1;load()}} onSort={(k:string)=>{sortKey=k;sortOrder=sortOrder==='asc'?'desc':'asc';load()}}
  onPage={(p:number)=>{page=p;load()}} onCreate={()=>goto('/grades/new')}>
  {#snippet children({item}:{item:Item})}
    <button class="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg" onclick={()=>goto(`/grades/${item.grade_id}`)}><Pencil class="w-4 h-4"/></button>
    <button class="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg" onclick={()=>deleteTarget=item}><Trash2 class="w-4 h-4"/></button>
  {/snippet}
</DataTable>
<ConfirmDialog open={deleteTarget!==null} title="Desactivar grado" message={`¿Desactivar "${deleteTarget?.name}"?`} confirmLabel="Desactivar" variant="danger" onConfirm={handleDelete} onCancel={()=>deleteTarget=null}/>
