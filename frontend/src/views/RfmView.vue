<script setup lang="ts">
import type { EChartsOption } from "echarts";
import { computed, onMounted, ref, watch } from "vue";

import { analyticsApi } from "@/api/client";
import type { RfmCustomer, RfmSegment } from "@/api/types";
import EChart from "@/components/EChart.vue";
import LoadingState from "@/components/LoadingState.vue";
import PanelHeader from "@/components/PanelHeader.vue";

const segments = ref<RfmSegment[]>([]);
const customers = ref<RfmCustomer[]>([]);
const selectedSegment = ref("");
const isLoading = ref(true);
const isCustomerLoading = ref(false);
const totalCount = ref(0);
const page = ref(1);

const segmentColors = ["#0f766e", "#14b8a6", "#1d4ed8", "#f59e0b", "#8b5cf6", "#ef6c4d", "#64748b", "#94a3b8"];

const segmentOption = computed<EChartsOption>(() => ({
  color: segmentColors,
  tooltip: {
    trigger: "item",
    formatter: "{b}<br/>客户数 {c}<br/>占比 {d}%",
  },
  legend: {
    type: "scroll",
    orient: "vertical",
    right: 8,
    top: "middle",
    textStyle: { color: "#475569" },
  },
  series: [
    {
      type: "pie",
      radius: ["46%", "72%"],
      center: ["37%", "50%"],
      itemStyle: { borderColor: "#fff", borderWidth: 4, borderRadius: 5 },
      label: { show: false },
      data: segments.value.map((item) => ({ name: item.segmentName, value: item.customerCount })),
    },
  ],
}));

const valueOption = computed<EChartsOption>(() => ({
  color: ["#1d4ed8", "#f59e0b"],
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  legend: { top: 0, right: 0, textStyle: { color: "#64748b" } },
  grid: { left: 48, right: 40, top: 42, bottom: 72 },
  xAxis: {
    type: "category",
    data: segments.value.map((item) => item.segmentName),
    axisLabel: { rotate: 28, color: "#64748b" },
  },
  yAxis: [
    {
      type: "value",
      name: "客户占比",
      axisLabel: { formatter: (value: number) => `${Math.round(value * 100)}%` },
      splitLine: { lineStyle: { color: "#edf2f7" } },
    },
    {
      type: "value",
      name: "金额占比",
      axisLabel: { formatter: (value: number) => `${Math.round(value * 100)}%` },
      splitLine: { show: false },
    },
  ],
  series: [
    {
      name: "客户占比",
      type: "bar",
      barMaxWidth: 18,
      data: segments.value.map((item) => item.customerShare),
      itemStyle: { borderRadius: [4, 4, 0, 0] },
    },
    {
      name: "金额占比",
      type: "line",
      yAxisIndex: 1,
      symbolSize: 7,
      lineStyle: { width: 3 },
      data: segments.value.map((item) => item.monetaryShare),
    },
  ],
}));

async function loadCustomers(): Promise<void> {
  isCustomerLoading.value = true;
  try {
    const response = await analyticsApi.getCustomers({
      segmentCode: selectedSegment.value || undefined,
      page: page.value,
      pageSize: 12,
    });
    customers.value = response.data;
    totalCount.value = response.meta.totalCount ?? 0;
  } finally {
    isCustomerLoading.value = false;
  }
}

watch(selectedSegment, () => {
  page.value = 1;
  void loadCustomers();
});

onMounted(async () => {
  try {
    const response = await analyticsApi.getSegments();
    segments.value = response.data;
    await loadCustomers();
  } finally {
    isLoading.value = false;
  }
});

const moneyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});
</script>

<template>
  <LoadingState v-if="isLoading" />
  <div v-else class="view-stack">
    <section class="segment-ribbon">
      <button
        v-for="(segment, index) in segments"
        :key="segment.segmentCode"
        :class="{ active: selectedSegment === segment.segmentCode }"
        :style="{ '--segment-color': segmentColors[index] }"
        @click="selectedSegment = selectedSegment === segment.segmentCode ? '' : segment.segmentCode"
      >
        <span>{{ segment.segmentName }}</span>
        <strong>{{ segment.customerCount.toLocaleString() }}</strong>
        <small>贡献 {{ (segment.monetaryShare * 100).toFixed(1) }}% 金额</small>
      </button>
    </section>

    <section class="dashboard-grid dashboard-grid--equal">
      <article class="panel">
        <PanelHeader title="客户结构" description="最新动态快照的客群人数构成" />
        <EChart :option="segmentOption" height="330px" />
      </article>
      <article class="panel">
        <PanelHeader title="价值错位分析" description="对比人数占比与销售贡献，发现高杠杆客群" />
        <EChart :option="valueOption" height="330px" />
      </article>
    </section>

    <article class="panel">
      <PanelHeader
        title="客户价值明细"
        :description="selectedSegment ? `当前筛选：${segments.find((item) => item.segmentCode === selectedSegment)?.segmentName}` : '按消费金额降序展示最新快照'"
        :badge="`${totalCount.toLocaleString()} CUSTOMERS`"
      >
        <button v-if="selectedSegment" class="text-button" @click="selectedSegment = ''">清除筛选</button>
      </PanelHeader>
      <div class="table-wrap" :class="{ 'is-loading': isCustomerLoading }">
        <table>
          <thead>
            <tr><th>客户 ID</th><th>客群</th><th>R / F / M</th><th>最近消费</th><th>订单频次</th><th>累计消费</th></tr>
          </thead>
          <tbody>
            <tr v-for="customer in customers" :key="customer.customerId">
              <td><strong>{{ customer.customerId }}</strong></td>
              <td><span class="segment-tag">{{ customer.segmentName }}</span></td>
              <td><span class="rfm-score">{{ customer.rScore }} · {{ customer.fScore }} · {{ customer.mScore }}</span></td>
              <td>{{ customer.recencyDays }} 天前</td>
              <td>{{ customer.frequency }} 单</td>
              <td><strong>{{ moneyFormatter.format(customer.monetary) }}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </div>
</template>
