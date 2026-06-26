<script lang="ts">
  import { onMount } from 'svelte';

  let {
    type = 'doughnut' as 'doughnut' | 'pie',
    labels = [] as string[],
    data = [] as number[],
  } = $props();

  const colors = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#f97316','#ec4899'];

  let canvasEl = $state<HTMLCanvasElement>();
  let ChartJs: any = null;
  let chartInstance: any = null;

  const percentageLabelPlugin = {
    id: 'percentageLabel',
    afterDatasetsDraw(chart: any) {
      const { ctx, data: chartData } = chart;
      const dataset = chartData.datasets[0];
      const total = dataset.data.reduce((a: number, b: number) => a + b, 0);
      if (total === 0) return;
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.font = 'bold 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      meta.data.forEach((arc: any, i: number) => {
        const pct = Math.round((dataset.data[i] / total) * 100);
        if (pct < 5) return;
        const { x, y } = arc.tooltipPosition();
        ctx.fillStyle = '#fff';
        ctx.shadowColor = 'rgba(0,0,0,0.3)';
        ctx.shadowBlur = 2;
        ctx.fillText(`${pct}%`, x, y);
        ctx.shadowBlur = 0;
      });
      ctx.restore();
    }
  };

  function legendWithPct(chart: any) {
    const chartData = chart.data;
    const total = chartData.datasets[0].data.reduce((a: number, b: number) => a + b, 0);
    return chartData.labels.map((label: string, i: number) => ({
      text: `${label} (${Math.round(chartData.datasets[0].data[i] / total * 100)}%)`,
      fillStyle: chartData.datasets[0].backgroundColor[i],
      strokeStyle: chartData.datasets[0].backgroundColor[i],
      index: i, hidden: !chart.getDataVisibility(i), pointStyle: 'circle',
    }));
  }

  async function renderChart() {
    if (!canvasEl || !data.length) return;
    if (!ChartJs) {
      const mod = await import('chart.js');
      mod.Chart.register(...mod.registerables);
      ChartJs = mod.Chart;
    }
    if (chartInstance) chartInstance.destroy();

    chartInstance = new ChartJs(canvasEl, {
      type,
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors.slice(0, data.length) }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { usePointStyle: true, padding: 15, generateLabels: legendWithPct },
          },
        },
      },
      plugins: [percentageLabelPlugin],
    });
  }

  $effect(() => {
    // Re-render when data changes
    labels; data;
    renderChart();
  });
</script>

<div class="relative h-64 md:h-72">
  <canvas bind:this={canvasEl}></canvas>
</div>
