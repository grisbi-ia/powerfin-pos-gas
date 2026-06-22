<script lang="ts" generics="T extends Record<string, any>">
  import { ChevronUp, ChevronDown, ChevronsUpDown, Search, Plus } from 'lucide-svelte';
  import Pagination from './Pagination.svelte';
  import EmptyState from './EmptyState.svelte';
  import ErrorBanner from './ErrorBanner.svelte';

  interface Column {
    key: string;
    label: string;
    sortable?: boolean;
  }

  let { items = [] as T[], columns = [] as Column[], loading = false, error = '',
        total = 0, page = 1, pages = 1, title = '',
        createLabel = 'Nuevo',
        onSearch = ((_q: string) => {}) as (q: string) => void,
        onSort = ((_key: string) => {}) as (k: string) => void,
        onPage = ((_p: number) => {}) as (p: number) => void,
        onCreate = (() => {}) as () => void,
        sortKey = '', sortOrder = 'asc' as 'asc' | 'desc',
        search = $bindable(''),
        children } = $props<{
          items: T[]; columns: Column[]; loading: boolean; error: string;
          total: number; page: number; pages: number; title: string;
          createLabel?: string; onSearch: (q: string) => void; onSort: (k: string) => void;
          onPage: (p: number) => void; onCreate: () => void;
          sortKey: string; sortOrder: 'asc' | 'desc'; search: string;
          children: any;
        }>();

  let searchTimeout: ReturnType<typeof setTimeout> | null = null;

  function handleSearch() {
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => onSearch(search), 300);
  }
</script>

<div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
  <div class="px-4 py-3 border-b border-gray-200 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
    <div class="relative flex-1 max-w-sm">
      <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <input type="text" bind:value={search} oninput={handleSearch}
             placeholder="Buscar..."
             class="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-md
                    focus:outline-none focus:ring-2 focus:ring-primary-500" />
    </div>
    <button onclick={onCreate}
            class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm
                   font-medium rounded-lg hover:bg-primary-600 transition-colors">
      <Plus class="w-4 h-4" /> {createLabel}
    </button>
  </div>

  {#if error}
    <div class="p-4"><ErrorBanner message={error} /></div>
  {:else if loading}
    <div class="flex justify-center py-12">
      <div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  {:else if items.length === 0}
    <EmptyState message="No se encontraron resultados con los filtros actuales." />
  {:else}
    <div class="hidden md:block overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            {#each columns as col}
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider
                         {col.sortable ? 'cursor-pointer select-none hover:bg-gray-100 transition-colors' : ''}"
                  onclick={() => col.sortable && onSort(col.key)}>
                <span class="inline-flex items-center gap-1">
                  {col.label}
                  {#if col.sortable}
                    {#if sortKey === col.key}
                      {#if sortOrder === 'asc'}<ChevronUp class="w-3.5 h-3.5" />{:else}<ChevronDown class="w-3.5 h-3.5" />{/if}
                    {:else}
                      <ChevronsUpDown class="w-3.5 h-3.5 text-gray-400" />
                    {/if}
                  {/if}
                </span>
              </th>
            {/each}
            <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Acciones</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 bg-white">
          {#each items as item, i}
            <tr class="hover:bg-gray-50 transition-colors">
              {#each columns as col}
                <td class="px-4 py-3 text-sm text-gray-700">
                  {String(item[col.key] ?? '')}
                </td>
              {/each}
              <td class="px-4 py-3 text-right">
                {#if children}
                  {@render children({ item })}
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="md:hidden divide-y divide-gray-100">
      {#each items as item, i}
        <div class="px-4 py-3 hover:bg-gray-50">
          <div class="flex items-start justify-between">
            <div class="space-y-1.5 flex-1 min-w-0">
              {#each columns.slice(0, 3) as col}
                <div class="flex items-center gap-1.5 text-xs">
                  <span class="font-medium text-gray-500">{col.label}:</span>
                  <span class="text-gray-700 truncate">{String(item[col.key] ?? '')}</span>
                </div>
              {/each}
            </div>
            <div class="flex gap-1 ml-2">
              {#if children}
                {@render children({ item })}
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>

    <Pagination {page} {pages} {total} {onPage} />
  {/if}
</div>
