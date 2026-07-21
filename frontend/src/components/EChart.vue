<script setup lang="ts">
import { BarChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { init, use } from "echarts/core";
import type { EChartsOption } from "echarts";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

const props = withDefaults(
  defineProps<{
    option: EChartsOption;
    height?: string;
  }>(),
  { height: "320px" },
);

const chartElement = ref<HTMLDivElement>();
let chartInstance: ReturnType<typeof init> | undefined;
let resizeObserver: ResizeObserver | undefined;

function renderChart(): void {
  if (!chartElement.value) return;
  chartInstance ??= init(chartElement.value, undefined, { renderer: "canvas" });
  chartInstance.setOption(props.option, true);
}

onMounted(() => {
  renderChart();
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => chartInstance?.resize());
    resizeObserver.observe(chartElement.value);
  }
});

watch(() => props.option, renderChart, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chartInstance?.dispose();
});
</script>

<template>
  <div ref="chartElement" class="echart" :style="{ height }" aria-label="数据图表"></div>
</template>
