<script lang="ts">
  import type { Period } from './types';

  interface GallonsItem {
    period_label: string;
    product_id: number;
    product_name: string;
    product_code: string;
    gallons: number;
    count: number;
  }

  let {
    period = 'daily' as Period,
    data = [] as GallonsItem[],
  } = $props();

  // Stable color mapping by product_id (survives renames)
  const productColorById: Record<number, string> = {
    1: '#22c55e',  // DIESEL  → verde
    2: '#f59e0b',  // SUPER   → amarillo
    3: '#3b82f6',  // ECO_PAIS → azul
  };

  const fallbackColors = ['#ef4444','#14b8a6','#f97316','#ec4899','#e11d48','#0891b2','#d946ef','#84cc16'];
  const monthNames = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  function hexToRgba(hex: string, alpha: number): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  let canvasEl = $state<HTMLCanvasElement>();
  let ChartJs: any = null;
  let chartInstance: any = null;

  function formatLabel(raw: string): string {
    if (period === 'daily') return raw.split('T')[1]?.substring(0, 5) || raw;
    if (period === 'annual') {
      const m = parseInt(raw);
      return monthNames[m] || raw;
    }
    const parts = raw.split('-');
    if (parts.length === 3) return `${parseInt(parts[2])} ${monthNames[parseInt(parts[1])]}`;
    return raw;
  }

  async function renderChart() {
    if (!canvasEl || !data.length) return;
    if (!ChartJs) {
      const mod = await import('chart.js');
      mod.Chart.register(...mod.registerables);
      ChartJs = mod.Chart;
    }
    if (chartInstance) chartInstance.destroy();

    // Pivot: extract unique labels and products
    const labelSet = new Map<string, string>();  // raw -> formatted
    const productSet = new Map<number, string>(); // id -> name
    for (const d of data) {
      if (!labelSet.has(d.period_label)) {
        labelSet.set(d.period_label, formatLabel(d.period_label));
      }
      if (!productSet.has(d.product_id)) {
        productSet.set(d.product_id, d.product_name);
      }
    }

    // Sort labels chronologically
    const sortedLabels = [...labelSet.keys()].sort();
    const labels = sortedLabels.map(l => labelSet.get(l)!);

    // Build datasets: one per product
    const productIds = [...productSet.keys()];
    let fallbackIdx = 0;
    const datasets = productIds.map((pid) => {
      const known = productColorById[pid];
      const color = known || fallbackColors[fallbackIdx++ % fallbackColors.length];
      const values = sortedLabels.map(label => {
        const found = data.find(d => d.period_label === label && d.product_id === pid);
        return found ? found.gallons : null;
      });
      return {
        label: productSet.get(pid) || String(pid),
        data: values,
        borderColor: color,
        backgroundColor: hexToRgba(color, 0.08),
        borderWidth: 2,
        tension: 0.3,
        pointRadius: 2,
        fill: false,
      };
    });

    chartInstance = new ChartJs(canvasEl, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx: any) => `${ctx.dataset.label}: ${ctx.raw?.toLocaleString('es-EC') || 0} gl`,
            },
          },
        },
        scales: {
          y: {
            ticks: { callback: (v: any) => v + ' gl' },
          },
        },
      },
    });
  }

  $effect(() => {
    data;
    renderChart();
  });
</script>

<div class="relative h-72 md:h-80">
  <canvas bind:this={canvasEl}></canvas>
</div>
