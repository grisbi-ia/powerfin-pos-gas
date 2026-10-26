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
  let disposed = false;
  let renderToken = 0;
  let hasData = $derived(data.length > 0);

  async function renderChart() {
    const token = ++renderToken;
    if (!canvasEl || !data.length) return;
    if (!ChartJs) {
      const mod = await import('chart.js');
      mod.Chart.register(...mod.registerables);
      ChartJs = mod.Chart;
    }
    if (disposed || token !== renderToken || !canvasEl) return;
    if (chartInstance) chartInstance.destroy();
    ChartJs.getChart(canvasEl)?.destroy();

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

  // Tear down the chart when the component is destroyed (view switch / keyed
  // block). This effect has no reactive reads, so it only runs its cleanup
  // on unmount. Using an effect (instead of onDestroy) keeps the component
  // free of a root `svelte` import, which Vite may resolve to the SSR build.
  $effect(() => {
    return () => {
      disposed = true;
      if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
      }
    };
  });
</script>

{#if hasData}
  <div class="relative h-64 md:h-72">
    <canvas bind:this={canvasEl}></canvas>
  </div>
{:else}
  <p class="text-sm text-gray-400 text-center py-8">Sin datos para este período</p>
{/if}
