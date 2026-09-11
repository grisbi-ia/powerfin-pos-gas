<script lang="ts">
  import { api } from '$lib/api/api';
  import { toast } from '$lib/utils/toast';
  import StatusBadge from '$components/StatusBadge.svelte';
  import {
    FileCheck, AlertTriangle, CheckCircle2, Clock, Activity,
    Download, RefreshCw, Search,
  } from 'lucide-svelte';

  type Tab = 'summary' | 'documents';

  let tab = $state<Tab>('summary');
  let loading = $state(true);
  let docsLoading = $state(false);
  let error = $state('');

  // ── Filters ─────────────────────────────────────────────────────
  function toLocalDate(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  const today = new Date();
  const monthAgo = new Date();
  monthAgo.setDate(monthAgo.getDate() - 29);

  let dateFrom = $state(toLocalDate(monthAgo));
  let dateTo = $state(toLocalDate(today));
  let statusFilter = $state('');
  let problemType = $state('');
  let key49Filter = $state('');
  let search = $state('');
  let onlyProblems = $state(true);
  let page = $state(1);
  const pageSize = 25;

  // ── Data ────────────────────────────────────────────────────────
  let metrics: any = $state(null);
  let health: any = $state(null);
  let docs: any[] = $state([]);
  let total = $state(0);
  let pages = $state(1);
  let summary: any = $state(null);
  let exporting = $state(false);

  const STATUS_OPTIONS = ['PENDING', 'FAILED', 'REJECTED', 'CREATED', 'SIGNED', 'SENT', 'RECEIVED', 'AUTHORIZED', 'NOTIFIED'];
  const PROBLEM_OPTIONS = [
    { value: 'NEVER_SENT', label: 'Nunca enviada' },
    { value: 'PENDING_SENT', label: 'Enviada, estado pendiente' },
    { value: 'KEY49_FAILED', label: 'Falló en Key49 (reintentos agotados)' },
    { value: 'INVALID_DATA', label: 'Rechazado por Key49 (validación)' },
    { value: 'REJECTED', label: 'Rechazada por el SRI' },
    { value: 'IN_PROGRESS', label: 'En proceso' },
  ];

  function qs(extra: Record<string, string> = {}): string {
    const q = new URLSearchParams();
    if (dateFrom) q.set('date_from', dateFrom);
    if (dateTo) q.set('date_to', dateTo);
    for (const [k, v] of Object.entries(extra)) if (v) q.set(k, v);
    return q.toString();
  }

  async function loadSummary() {
    loading = true;
    error = '';
    try {
      metrics = await api.get(`/sri/metrics?${qs()}`);
      health = await api.get('/sri/health');
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function loadDocs() {
    docsLoading = true;
    error = '';
    try {
      const res = await api.get<any>(`/sri/documents?${qs({
        status: statusFilter, problem_type: problemType, search, key49: key49Filter,
        only_problems: String(onlyProblems), page: String(page), page_size: String(pageSize),
      })}`);
      docs = res.items;
      total = res.total;
      pages = res.pages;
      summary = res.summary;
    } catch (e: any) {
      error = e.message;
      docs = [];
    } finally {
      docsLoading = false;
    }
  }

  // Reload when the active tab or filters change
  $effect(() => {
    void tab; void dateFrom; void dateTo;
    if (tab === 'summary') void loadSummary();
  });
  $effect(() => {
    void tab; void dateFrom; void dateTo; void statusFilter; void problemType; void key49Filter; void search; void onlyProblems; void page;
    if (tab === 'documents') void loadDocs();
  });

  // Reset pagination when filters change
  $effect(() => { void dateFrom; void dateTo; void statusFilter; void problemType; void key49Filter; void search; void onlyProblems; page = 1; });

  async function exportDocs(format: 'pdf' | 'xlsx') {
    exporting = true;
    try {
      const token = (await import('$lib/api/api')).getToken();
      const res = await fetch(`/api/admin/sri/documents/export?${qs({
        format, status: statusFilter, problem_type: problemType, search, key49: key49Filter,
        only_problems: String(onlyProblems),
      })}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error('Error al exportar');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `documentos_sri.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exportado como ${format.toUpperCase()}`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      exporting = false;
    }
  }

  function fmtDate(s: string | null): string {
    if (!s) return '—';
    try {
      return new Intl.DateTimeFormat('es-EC', {
        day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
        timeZone: 'America/Guayaquil',
      }).format(new Date(s));
    } catch { return s; }
  }
  function fmtMoney(n: number): string {
    return '$ ' + Number(n || 0).toLocaleString('es-EC', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  const dayMax = $derived(
    Math.max(1, ...((metrics?.by_day || []).map((d: any) => d.total)))
  );
  const problemLabels: Record<string, string> = {
    NEVER_SENT: 'Nunca enviada',
    PENDING_SENT: 'Enviada, pendiente',
    KEY49_FAILED: 'Falló en Key49',
    INVALID_DATA: 'Rechazado por Key49',
    REJECTED: 'Rechazada SRI',
  };
</script>

<div class="p-4 md:p-6 space-y-5">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
    <div>
      <h1 class="text-xl md:text-2xl font-bold text-gray-900 flex items-center gap-2">
        <FileCheck class="w-6 h-6 text-primary-500" /> Facturación electrónica SRI
      </h1>
      <p class="text-sm text-gray-500 mt-0.5">Monitoreo de documentos enviados a Key49 / SRI</p>
    </div>
    <div class="flex items-center gap-2">
      <input type="date" bind:value={dateFrom} class="px-3 py-2 text-sm border border-gray-300 rounded-md" />
      <span class="text-gray-400">a</span>
      <input type="date" bind:value={dateTo} class="px-3 py-2 text-sm border border-gray-300 rounded-md" />
      <button onclick={() => tab === 'summary' ? loadSummary() : loadDocs()}
              class="p-2 rounded-lg border border-gray-300 hover:bg-gray-50" title="Refrescar">
        <RefreshCw class="w-4 h-4 text-gray-600" />
      </button>
    </div>
  </div>

  <!-- Tabs -->
  <div class="flex gap-1 border-b border-gray-200">
    {#each [['summary', 'Resumen'], ['documents', 'Documentos']] as [id, label]}
      <button onclick={() => (tab = id as Tab)}
              class="px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors
                     {tab === id ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}">
        {label}
      </button>
    {/each}
  </div>

  {#if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      <p class="font-medium">No se pudo cargar el módulo SRI</p>
      <p class="mt-1">{error}</p>
      {#if error.includes('desactivado')}
        <p class="mt-2 text-red-600">
          Actívalo en <b>Configuración</b> con la clave <code class="bg-red-100 px-1 rounded">sri_monitor_enabled = true</code>.
        </p>
      {/if}
    </div>
  {:else if tab === 'summary'}
    {#if loading}
      <div class="flex justify-center py-16">
        <div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    {:else if metrics}
      <!-- KPI cards -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div class="bg-white rounded-lg border border-gray-200 p-4">
          <div class="flex items-center gap-2 text-gray-500 text-sm"><Activity class="w-4 h-4" /> Total emitidos</div>
          <p class="text-2xl font-bold text-gray-900 mt-1">{metrics.total.toLocaleString('es-EC')}</p>
        </div>
        <div class="bg-white rounded-lg border border-gray-200 p-4">
          <div class="flex items-center gap-2 text-green-600 text-sm"><CheckCircle2 class="w-4 h-4" /> Autorizados</div>
          <p class="text-2xl font-bold text-gray-900 mt-1">{metrics.authorized.toLocaleString('es-EC')}</p>
          <p class="text-xs text-green-600">{metrics.success_rate}% éxito</p>
        </div>
        <div class="bg-white rounded-lg border border-gray-200 p-4">
          <div class="flex items-center gap-2 text-blue-600 text-sm"><Clock class="w-4 h-4" /> En proceso</div>
          <p class="text-2xl font-bold text-gray-900 mt-1">{metrics.in_progress.toLocaleString('es-EC')}</p>
        </div>
        <div class="bg-white rounded-lg border border-gray-200 p-4">
          <div class="flex items-center gap-2 text-orange-600 text-sm"><AlertTriangle class="w-4 h-4" /> Con problemas</div>
          <p class="text-2xl font-bold text-gray-900 mt-1">{metrics.problems_total.toLocaleString('es-EC')}</p>
        </div>
        <div class="bg-white rounded-lg border border-gray-200 p-4">
          <div class="flex items-center gap-2 text-gray-500 text-sm">Tiempo a autorización</div>
          <p class="text-2xl font-bold text-gray-900 mt-1">
            {metrics.avg_authorization_seconds ? (metrics.avg_authorization_seconds / 60).toFixed(0) + ' min' : '—'}
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- By day -->
        <div class="lg:col-span-2 bg-white rounded-lg border border-gray-200 p-4">
          <h2 class="font-semibold text-gray-800 mb-3">Emisiones por día</h2>
          {#if (metrics.by_day || []).length === 0}
            <p class="text-sm text-gray-400 py-8 text-center">Sin datos en el rango</p>
          {:else}
            <div class="space-y-2">
              {#each metrics.by_day as d}
                <div class="flex items-center gap-3 text-xs">
                  <span class="w-20 text-gray-500 shrink-0">{d.day}</span>
                  <div class="flex-1 bg-gray-100 rounded h-4 overflow-hidden flex">
                    <div class="bg-green-500 h-4" style="width: {(d.authorized / dayMax) * 100}%"></div>
                    <div class="bg-blue-400 h-4" style="width: {(d.in_progress / dayMax) * 100}%"></div>
                    <div class="bg-red-500 h-4" style="width: {(d.problems / dayMax) * 100}%"></div>
                  </div>
                  <span class="w-24 text-right text-gray-600 shrink-0">{d.total} tot · {d.problems} prob</span>
                </div>
              {/each}
            </div>
            <div class="flex gap-4 mt-3 text-xs text-gray-500">
              <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-green-500"></span> Autorizadas</span>
              <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-blue-400"></span> En proceso</span>
              <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500"></span> Con problema</span>
            </div>
          {/if}
        </div>

        <!-- Problems breakdown + health -->
        <div class="space-y-4">
          <div class="bg-white rounded-lg border border-gray-200 p-4">
            <h2 class="font-semibold text-gray-800 mb-3">Problemas por tipo</h2>
            <div class="space-y-2">
              {#each Object.entries(metrics.problems) as [k, v]}
                <div class="flex items-center justify-between text-sm">
                  <span class="text-gray-600">{problemLabels[k] || k}</span>
                  <span class="font-semibold {Number(v) > 0 ? 'text-red-600' : 'text-gray-400'}">{v}</span>
                </div>
              {/each}
            </div>
          </div>

          <div class="bg-white rounded-lg border border-gray-200 p-4">
            <h2 class="font-semibold text-gray-800 mb-3">Salud Key49</h2>
            <div class="space-y-2 text-sm">
              <div class="flex items-center justify-between">
                <span class="text-gray-600">API configurada</span>
                <StatusBadge status={health?.key49_configured ? 'ACTIVE' : 'INACTIVE'}
                             label={health?.key49_configured ? 'Sí' : 'No'} />
              </div>
              <div class="flex items-center justify-between">
                <span class="text-gray-600">Key49 habilitado</span>
                <StatusBadge status={health?.key49_enabled ? 'ACTIVE' : 'INACTIVE'}
                             label={health?.key49_enabled ? 'Sí' : 'No'} />
              </div>
              <div class="pt-2 border-t border-gray-100 text-xs text-gray-500 space-y-1">
                <div class="flex justify-between"><span>Plan expirado (24h)</span><span>{health?.last_24h?.plan_expired ?? 0}</span></div>
                <div class="flex justify-between"><span>No disponible (24h)</span><span>{health?.last_24h?.unavailable ?? 0}</span></div>
                <div class="flex justify-between"><span>HTTP 402 (24h)</span><span>{health?.last_24h?.http_402 ?? 0}</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p class="text-xs text-gray-400">
        El "tiempo a autorización" promedio puede verse inflado por facturas antiguas reprocesadas.
      </p>
    {/if}
  {:else}
    <!-- Documents tab -->
    <div class="bg-white rounded-lg border border-gray-200">
      <div class="p-4 border-b border-gray-200 flex flex-col lg:flex-row gap-3 lg:items-center justify-between">
        <div class="flex flex-wrap items-center gap-2">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" bind:value={search} placeholder="Buscar orden, cliente, cédula, placa…"
                   class="w-64 pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-md" />
          </div>
          <select bind:value={statusFilter} class="px-3 py-2 text-sm border border-gray-300 rounded-md">
            <option value="">Todos los estados</option>
            {#each STATUS_OPTIONS as s}<option value={s}>{s}</option>{/each}
          </select>
          <select bind:value={problemType} class="px-3 py-2 text-sm border border-gray-300 rounded-md">
            <option value="">Todos los tipos</option>
            {#each PROBLEM_OPTIONS as p}<option value={p.value}>{p.label}</option>{/each}
          </select>
          <select bind:value={key49Filter} class="px-3 py-2 text-sm border border-gray-300 rounded-md">
            <option value="">En Key49: todos</option>
            <option value="yes">Solo en Key49</option>
            <option value="no">Solo no llegaron a Key49</option>
          </select>
          <label class="flex items-center gap-1.5 text-sm text-gray-600">
            <input type="checkbox" bind:checked={onlyProblems} /> Solo con problemas
          </label>
        </div>
        <div class="flex items-center gap-2">
          <button onclick={() => exportDocs('pdf')} disabled={exporting}
                  class="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
            <Download class="w-4 h-4" /> PDF
          </button>
          <button onclick={() => exportDocs('xlsx')} disabled={exporting}
                  class="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
            <Download class="w-4 h-4" /> Excel
          </button>
        </div>
      </div>

      {#if summary}
        <div class="px-4 py-2 border-b border-gray-200 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-600 bg-gray-50">
          <span><b class="text-gray-800">{summary.total}</b> en el filtro</span>
          <span class="text-green-700">En Key49: <b>{summary.in_key49}</b></span>
          <span class="text-red-700">No llegaron a Key49: <b>{summary.not_in_key49}</b></span>
          <span class="text-gray-500">(rechazados por Key49: {summary.rejected_by_key49} · nunca enviados: {summary.never_sent})</span>
        </div>
      {/if}

      {#if docsLoading}
        <div class="flex justify-center py-12">
          <div class="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      {:else if docs.length === 0}
        <div class="py-12 text-center text-sm text-gray-400">No se encontraron documentos con estos filtros.</div>
      {:else}
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Fecha</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Orden</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Cliente</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Secuencial</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Estado</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Problema</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">En Key49</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Mensaje</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              {#each docs as d}
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{fmtDate(d.created_at)}</td>
                  <td class="px-4 py-3 text-sm text-gray-800 font-medium">{d.order_id}</td>
                  <td class="px-4 py-3 text-sm text-gray-600">
                    {d.customer_name || '—'}<br /><span class="text-xs text-gray-400">{d.id_number || ''}</span>
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">{d.sequential_number || '—'}</td>
                  <td class="px-4 py-3 text-sm text-gray-700 text-right whitespace-nowrap">{fmtMoney(d.total)}</td>
                  <td class="px-4 py-3"><StatusBadge status={d.sri_status || 'PENDING'} /></td>
                  <td class="px-4 py-3 text-sm">
                    <span class="inline-block px-2 py-0.5 rounded text-xs font-medium {d.problem_type === 'REJECTED' || d.problem_type === 'INVALID_DATA' || d.problem_type === 'KEY49_FAILED' ? 'bg-red-50 text-red-700' : 'bg-yellow-50 text-yellow-700'}">
                      {problemLabels[d.problem_type] || d.problem_type}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm">
                    {#if d.has_key49_id}
                      <span class="text-green-600 font-medium">Sí</span>
                    {:else}
                      <span class="text-gray-400">No</span>
                    {/if}
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-500 max-w-xs truncate" title={d.sri_messages || ''}>
                    {d.sri_messages || '—'}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <div class="px-4 py-3 border-t border-gray-200 flex items-center justify-between text-sm">
          <span class="text-gray-500">{total.toLocaleString('es-EC')} documento(s)</span>
          <div class="flex items-center gap-2">
            <button onclick={() => page > 1 && page--} disabled={page <= 1}
                    class="px-3 py-1.5 border border-gray-300 rounded-md disabled:opacity-40">Anterior</button>
            <span class="text-gray-600">{page} / {Math.max(1, pages)}</span>
            <button onclick={() => page < pages && page++} disabled={page >= pages}
                    class="px-3 py-1.5 border border-gray-300 rounded-md disabled:opacity-40">Siguiente</button>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
