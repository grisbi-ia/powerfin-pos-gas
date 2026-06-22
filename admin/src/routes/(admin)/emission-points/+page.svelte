<script lang="ts">
  import { goto } from '$app/navigation';
  import { Pencil } from 'lucide-svelte';
  import DataTable from '$components/DataTable.svelte';
  import StatusBadge from '$components/StatusBadge.svelte';
  import { api } from '$lib/api/api';

  interface Item { emission_point_id:number; label:string; establishment:string; emission_point:string; doc_type:string; current_sequential:number; is_active:boolean }
  let items=$state<Item[]>([]); let total=$state(0); let page=$state(1); let pages=$state(1);
  let loading=$state(true); let error=$state(''); let search=$state(''); let sortKey=$state('establishment'); let sortOrder=$state<'asc'|'desc'>('asc');

  async function load(){loading=true;error='';try{const d=await api.get<any>(`/emission-points?search=${encodeURIComponent(search)}&page=${page}&page_size=10&sort=${sortKey}&order=${sortOrder}`);items=d.items;total=d.total;pages=d.pages}catch(e:any){error=e.message}finally{loading=false}}
  $effect(() => { load(); });
</script>
<DataTable title="Puntos de Emisión" {items} columns={[{key:'label',label:'Punto',sortable:true},{key:'doc_type',label:'Tipo Doc.',sortable:true},{key:'current_sequential',label:'Secuencial Actual'},{key:'is_active',label:'Estado',sortable:true}]}
  {loading}{error}{total}{page}{pages}{search}{sortKey}{sortOrder}
  onSearch={(q:string)=>{search=q;page=1;load()}} onSort={(k:string)=>{sortKey=k;sortOrder=sortOrder==='asc'?'desc':'asc';load()}}
  onPage={(p:number)=>{page=p;load()}} onCreate={()=>goto('/emission-points/new')}>
  {#snippet children({item}:{item:Item})}
    <button class="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg" onclick={()=>goto(`/emission-points/${item.emission_point_id}`)}><Pencil class="w-4 h-4"/></button>
  {/snippet}
</DataTable>
