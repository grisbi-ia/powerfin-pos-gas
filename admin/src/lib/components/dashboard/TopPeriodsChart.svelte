<script lang="ts">
  import type { Period } from './types';

  let {
    period = 'monthly' as Period,
    data = [] as { period_label: string; sales: number; gallons: number; count: number }[],
    limit = 5,
  } = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  let ChartJs: any = null;
  let chartInstance: any = null;
  let hasData = $derived(data.length > 0);

  async function renderChart() {
    if (!canvasEl || !data.length) return;
    if (!ChartJs) {
      const mod = await import('chart.js');
      mod.Chart.register(...mod.registerables);
      ChartJs = mod.Chart;
    }
    if (chartInstance) chartInstance.destroy();

    // Reverse for horizontal bar (top first at top)
    const reversed = [...data].reverse();

    chartInstance = new ChartJs(canvasEl, {
      type: 'bar',
      data: {
        labels: reversed.map(d => d.period_label),
        datasets: [
          {
            label: 'Ventas $',
            data: reversed.map(d => d.sales),
            backgroundColor: '#3b82f6',
            borderRadius: 3,
            borderSkipped: false,
          },
        ],
      },
      options: {
        indexAxis: 'y' as any,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: (ctx: any) => `${data[data.length - 1 - ctx.dataIndex]?.gallons} gl · ${data[data.length - 1 - ctx.dataIndex]?.count} despachos`,
            },
          },
        },
        scales: {
          x: {
            ticks: { callback: (v: any) => '$' + v },
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

{#if hasData}
  <div class="relative h-64 md:h-72">
    <canvas bind:this={canvasEl}></canvas>
  </div>
{:else}
  <p class="text-sm text-gray-400 text-center py-8">Sin datos para este período</p>
{/if}
