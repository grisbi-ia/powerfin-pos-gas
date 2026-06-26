<script lang="ts">
  import type { Period } from './types';

  interface EvoItem {
    period_label: string;
    sales: number;
    gallons: number;
    count: number;
  }

  let {
    metric = 'sales' as 'sales' | 'gallons',
    period = 'daily' as Period,
    previous = [] as EvoItem[],
    current = [] as EvoItem[],
    next = [] as EvoItem[],
    previousLabel = '',
    currentLabel = '',
    nextLabel = '',
  } = $props();

  const monthNames = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  let canvasEl = $state<HTMLCanvasElement>();
  let ChartJs: any = null;
  let chartInstance: any = null;

  function formatLabel(raw: string): string {
    if (period === 'daily') return raw.split('T')[1]?.substring(0, 5) || raw;
    if (period === 'annual') {
      const m = parseInt(raw);
      return monthNames[m] || raw;
    }
    // monthly — raw is a date string like "2026-06-15"
    const parts = raw.split('-');
    if (parts.length === 3) return `${parseInt(parts[2])} ${monthNames[parseInt(parts[1])]}`;
    return raw;
  }

  function formatShortLabel(raw: string): string {
    // Shorter version for the label in the period_label
    return raw; // already formatted by backend
  }

  function getValue(item: EvoItem): number {
    return metric === 'sales' ? item.sales : item.gallons;
  }

  let formatValue = $derived(metric === 'sales'
    ? (v: number) => '$' + v.toLocaleString('es-EC')
    : (v: number) => v.toLocaleString('es-EC') + ' gl');

  async function renderChart() {
    if (!canvasEl) return;
    // ── Generate ALL expected labels for the period ────────────
    // This ensures datasets align by bucket value, not array position.
    let allLabels: string[] = [];
    if (period === 'daily') {
      allLabels = Array.from({length: 24}, (_, h) => `${String(h).padStart(2,'0')}:00`);
    } else if (period === 'annual') {
      allLabels = Array.from({length: 12}, (_, m) => monthNames[m + 1]);
    } else {
      // monthly — derive days from current dataset's date labels
      if (current.length > 0) {
        const firstRaw = current[0].period_label;
        const parts = firstRaw.split('-');
        if (parts.length === 3) {
          const y = parseInt(parts[0]);
          const m = parseInt(parts[1]);
          const daysInMonth = new Date(y, m, 0).getDate();
          allLabels = Array.from({length: daysInMonth}, (_, d) =>
            `${d + 1} ${monthNames[m]}`
          );
        }
      }
    }

    // Build lookup: period_label (raw) → value
    function extractKey(item: EvoItem): string {
      if (period === 'daily') return item.period_label.split('T')[1]?.substring(0, 5) || item.period_label;
      return item.period_label;
    }

    function buildLookup(arr: EvoItem[]): Map<string, number> {
      const m = new Map<string, number>();
      for (const item of arr) {
        const key = extractKey(item);
        m.set(key, getValue(item));
      }
      return m;
    }

    const prevMap = buildLookup(previous);
    const curMap = buildLookup(current);
    const nextMap = buildLookup(next);

    // For monthly comparison, we need to match date labels to day+month labels
    function formatLookupLabel(raw: string): string {
      if (period === 'daily') return raw.split('T')[1]?.substring(0, 5) || raw;
      if (period === 'annual') {
        const m = parseInt(raw);
        return monthNames[m] || raw;
      }
      // monthly: "2026-06-15" → "15 Jun"
      const parts = raw.split('-');
      if (parts.length === 3) return `${parseInt(parts[2])} ${monthNames[parseInt(parts[1])]}`;
      return raw;
    }

    // ── Align data to allLabels ──────────────────────────────
    const lookupValue = (label: string, map: Map<string, number>) => {
      // For monthly, try to match by formatted label
      for (const [rawKey, val] of map) {
        if (formatLookupLabel(rawKey) === label) return val;
      }
      return null;
    };

    const prevData = allLabels.map(l => lookupValue(l, prevMap));
    const curData = allLabels.map(l => lookupValue(l, curMap));
    const nextData = allLabels.map(l => lookupValue(l, nextMap));

    if (!ChartJs) {
      const mod = await import('chart.js');
      mod.Chart.register(...mod.registerables);
      ChartJs = mod.Chart;
    }
    if (chartInstance) chartInstance.destroy();

    chartInstance = new ChartJs(canvasEl, {
      type: 'line',
      data: {
        labels: allLabels,
        datasets: [
          {
            label: previousLabel || 'Anterior',
            data: prevData,
            borderColor: '#94a3b8',
            backgroundColor: 'rgba(148,163,184,0.08)',
            borderWidth: 1.5,
            borderDash: [4, 3],
            tension: 0.3,
            pointRadius: 0,
            fill: false,
            spanGaps: false,
          },
          {
            label: currentLabel || 'Actual',
            data: curData,
            borderColor: metric === 'sales' ? '#3b82f6' : '#22c55e',
            backgroundColor: metric === 'sales' ? 'rgba(59,130,246,0.1)' : 'rgba(34,197,94,0.1)',
            borderWidth: 2.5,
            tension: 0.3,
            pointRadius: allLabels.length <= 31 ? 3 : 0,
            fill: true,
            spanGaps: false,
          },
          {
            label: nextLabel || 'Siguiente',
            data: nextData,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.06)',
            borderWidth: 1.5,
            borderDash: [2, 4],
            tension: 0.3,
            pointRadius: 0,
            fill: false,
            spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx: any) => `${ctx.dataset.label}: ${formatValue(ctx.raw || 0)}`,
            },
          },
        },
        scales: {
          y: {
            ticks: { callback: (v: any) => formatValue(v) },
          },
        },
      },
    });
  }

  $effect(() => {
    current; previous; next; metric; period;
    renderChart();
  });
</script>

<div class="relative h-72 md:h-80">
  <canvas bind:this={canvasEl}></canvas>
</div>
