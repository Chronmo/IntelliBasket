<script setup lang="ts">
import type { EChartsOption } from "echarts";
import { CircleDollarSign, PackageOpen, ReceiptText, UsersRound } from "@lucide/vue";
import { computed, onMounted, ref } from "vue";

import { analyticsApi } from "@/api/client";
import type { BusinessOverview, MonthlySale, TopProduct } from "@/api/types";
import EChart from "@/components/EChart.vue";
import LoadingState from "@/components/LoadingState.vue";
import MetricCard from "@/components/MetricCard.vue";
import PanelHeader from "@/components/PanelHeader.vue";

const overview = ref<BusinessOverview>();
const monthlySales = ref<MonthlySale[]>([]);
const topProducts = ref<TopProduct[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");

const currencyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});
const integerFormatter = new Intl.NumberFormat("zh-CN");

const salesTrendOption = computed<EChartsOption>(() => ({
  animationDuration: 700,
  color: ["#14b8a6", "#f59e0b"],
  tooltip: { trigger: "axis" },
  legend: { right: 6, top: 0, textStyle: { color: "#64748b" } },
  grid: { left: 58, right: 50, top: 45, bottom: 36 },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: monthlySales.value.map((item) => item.invoiceMonth),
    axisLabel: { color: "#64748b", interval: 2 },
    axisLine: { lineStyle: { color: "#dbe4ee" } },
  },
  yAxis: [
    {
      type: "value",
      axisLabel: { color: "#64748b", formatter: (value: number) => `£${value / 1000}k` },
      splitLine: { lineStyle: { color: "#edf2f7" } },
    },
    {
      type: "value",
      axisLabel: { color: "#64748b" },
      splitLine: { show: false },
    },
  ],
  series: [
    {
      name: "销售额",
      type: "line",
      smooth: 0.3,
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { width: 3 },
      areaStyle: { color: "rgba(20,184,166,.1)" },
      data: monthlySales.value.map((item) => item.salesAmount),
    },
    {
      name: "订单数",
      type: "bar",
      yAxisIndex: 1,
      barMaxWidth: 16,
      itemStyle: { borderRadius: [4, 4, 0, 0], opacity: 0.75 },
      data: monthlySales.value.map((item) => item.orderCount),
    },
  ],
}));

const productOption = computed<EChartsOption>(() => {
  const items = topProducts.value.slice(0, 7).reverse();
  return {
    color: ["#1d4ed8"],
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 10, right: 38, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `£${Math.round(value / 1000)}k` },
      splitLine: { lineStyle: { color: "#edf2f7" } },
    },
    yAxis: {
      type: "category",
      data: items.map((item) => item.productName.slice(0, 22)),
      axisLabel: { color: "#475569", width: 145, overflow: "truncate" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        barWidth: 13,
        data: items.map((item) => item.salesAmount),
        itemStyle: { borderRadius: [0, 6, 6, 0] },
      },
    ],
  };
});

onMounted(async () => {
  try {
    const [overviewResponse, monthlyResponse, productsResponse] = await Promise.all([
      analyticsApi.getOverview(),
      analyticsApi.getMonthlySales(),
      analyticsApi.getTopProducts(10),
    ]);
    overview.value = overviewResponse.data;
    monthlySales.value = monthlyResponse.data;
    topProducts.value = productsResponse.data;
  } catch {
    errorMessage.value = "暂时无法连接分析服务，请确认 FastAPI 与 MySQL 已启动。";
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <LoadingState v-if="isLoading" />
  <div v-else-if="errorMessage" class="error-state">{{ errorMessage }}</div>
  <div v-else-if="overview" class="view-stack">
    <section class="metric-grid">
      <MetricCard
        label="累计销售额"
        :value="currencyFormatter.format(overview.salesAmount)"
        note="有效订单口径 · 英镑"
        :icon="CircleDollarSign"
        tone="teal"
      />
      <MetricCard
        label="有效购物篮"
        :value="integerFormatter.format(overview.orderCount)"
        note="发票号定义可靠篮子边界"
        :icon="ReceiptText"
        tone="orange"
      />
      <MetricCard
        label="可识别客户"
        :value="integerFormatter.format(overview.customerCount)"
        note="用于动态 RFM 分层"
        :icon="UsersRound"
        tone="blue"
      />
      <MetricCard
        label="有效商品"
        :value="integerFormatter.format(overview.productCount)"
        note="清洗后参与价值分析"
        :icon="PackageOpen"
        tone="violet"
      />
    </section>

    <section class="dashboard-grid dashboard-grid--wide">
      <article class="panel panel--wide">
        <PanelHeader
          title="25 个月经营趋势"
          description="销售额与订单量双轴对照，识别季节性增长窗口"
          badge="REAL TRANSACTIONS"
        />
        <EChart :option="salesTrendOption" height="350px" />
      </article>
      <article class="panel">
        <PanelHeader title="高价值商品" description="按有效销售额排序" />
        <EChart :option="productOption" height="350px" />
      </article>
    </section>

    <section class="insight-strip">
      <span class="insight-strip__index">01</span>
      <div>
        <strong>购物篮平均产出 {{ currencyFormatter.format(overview.averageBasketAmount) }}</strong>
        <p>从商品组合与高价值客群两条路径提升客单价，避免只按全局热度推荐。</p>
      </div>
      <span class="insight-strip__period">
        {{ overview.minInvoiceTs.slice(0, 10) }} — {{ overview.maxInvoiceTs.slice(0, 10) }}
      </span>
    </section>
  </div>
</template>
