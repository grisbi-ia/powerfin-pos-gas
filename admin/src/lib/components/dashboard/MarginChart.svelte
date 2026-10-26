<script lang="ts">
  import type { Period } from './types';

  interface MarginItem {
    period_label: string;
    net_sales: number;
    cost: number;
    utility: number | null;
    utility_complete?: boolean;
    count: number;
  }

  let {
    period = 'daily' as Period,
    anchor = '',
    data = [] as MarginItem[],
  } = $props();

  const monthNames = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  let canvasEl = $state<HTMLCanvasElement>();
  let ChartJs: any = null;
  let chartInstance: any = null;

  function buildLabels(): string[] {
    if (period === 'daily') {
      return Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}:00`);
    }
    if (period === 'annual') {
      return Array.from({ length: 12 }, (_, m) => monthNames[m + 1]);
    }
    // monthly: derive the month from the anchor ("YYYY-MM") or the first row
    let year: number | null = null;
    let month: number | null = null;
    if (anchor && anchor.split('-').length >= 2) {
      [year, month] = anchor.split('-').map(Number);
    } else if (data.length > 0) {
      const parts = data[0].period_label.split('-');
      if (parts.length === 3) { year = Number(parts[0]); month = Number(parts[1]); }
    }
    if (!year || !month) return [];
    const days = new Date(year, month, 0).getDate();
    return Array.from({ length: days }, (_, d) => `${d + 1} ${monthNames[month]}`);
  }

  function keyFromRaw(raw: string): string {
    if (period === 'daily') return raw.split('T')[1]?.substring(0, 5) || raw;
    if (period === 'annual') return monthNames[parseInt(raw)] || raw;
    const parts = raw.split('-');
    if (parts.length === 3) return `${parseInt(parts[2])} ${monthNames[parseInt(parts[1])]}`;
    return raw;
  }

  function formatMoney(v: number): string {
    return (v < 0 ? '-$' : '$') + Math.abs(v).toLocaleString('es-EC', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  async function renderChart() {
    if (!canvasEl) return;

    const allLabels = buildLabels();
    const byLabel = new Map<string, MarginItem>();
    for (const item of data) byLabel.set(keyFromRaw(item.period_label), item);

    const valueFor = (label: string, field: 'net_sales' | 'cost' | 'utility') => {
      const item = byLabel.get(label);
      if (!item) return null;
      if (field === 'utility') return item.utility ?? null;
      return item[field];
    };

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
            label: 'Ventas netas (sin IVA)',
            data: allLabels.map(l => valueFor(l, 'net_sales')),
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59,130,246,0.08)',
            borderWidth: 2,
            tension: 0.3,
            pointRadius: allLabels.length <= 31 ? 3 : 0,
            fill: false,
            spanGaps: false,
          },
          {
            label: 'Costo de ventas (sin IVA)',
            data: allLabels.map(l => valueFor(l, 'cost')),
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.08)',
            borderWidth: 2,
            borderDash: [6, 3],
            tension: 0.3,
            pointRadius: allLabels.length <= 31 ? 3 : 0,
            fill: false,
            spanGaps: false,
          },
          {
            label: 'Utilidad (sin IVA)',
            data: allLabels.map(l => valueFor(l, 'utility')),
            borderColor: '#0d9488',
            backgroundColor: 'rgba(13,148,136,0.12)',
            borderWidth: 2.8,
            tension: 0.3,
            pointRadius: allLabels.length <= 31 ? 3 : 0,
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
              label: (ctx: any) => ctx.raw == null
                ? `${ctx.dataset.label}: sin dato`
                : `${ctx.dataset.label}: ${formatMoney(ctx.raw as number)}`,
            },
          },
        },
        scales: {
          y: { ticks: { callback: (v: any) => formatMoney(Number(v)) } },
        },
      },
    });
  }

  $effect(() => {
    period; anchor; data;
    renderChart();
  });
</script>

<div class="relative h-80 md:h-96">
  <canvas bind:this={canvasEl}></canvas>
</div>
