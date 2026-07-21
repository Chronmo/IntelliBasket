<script setup lang="ts">
import type { EChartsOption } from "echarts";
import { computed, onMounted, ref, watch } from "vue";

import { analyticsApi } from "@/api/client";
import type { AssociationRule, RfmSegment, RuleDrift } from "@/api/types";
import EChart from "@/components/EChart.vue";
import LoadingState from "@/components/LoadingState.vue";
import PanelHeader from "@/components/PanelHeader.vue";

const rules = ref<AssociationRule[]>([]);
const drifts = ref<RuleDrift[]>([]);
const segments = ref<RfmSegment[]>([]);
const selectedSegment = ref("ALL");
const minLift = ref(1.2);
const minConfidence = ref(0.25);
const isLoading = ref(true);

const ruleOption = computed<EChartsOption>(() => ({
  color: ["#14b8a6"],
  tooltip: {
    trigger: "item",
    formatter: (params: unknown) => {
      const [support, confidence, lift, name] = (
        params as { data: [number, number, number, string] }
      ).data;
      return `${name}<br/>支持度 ${(support * 100).toFixed(2)}%<br/>置信度 ${(confidence * 100).toFixed(1)}%<br/>提升度 ${lift.toFixed(2)}`;
    },
  },
  grid: { left: 58, right: 30, top: 20, bottom: 46 },
  xAxis: {
    name: "支持度",
    type: "value",
    axisLabel: { formatter: (value: number) => `${(value * 100).toFixed(1)}%` },
    splitLine: { lineStyle: { color: "#edf2f7" } },
  },
  yAxis: {
    name: "置信度",
    type: "value",
    min: 0.2,
    max: 1,
    axisLabel: { formatter: (value: number) => `${Math.round(value * 100)}%` },
    splitLine: { lineStyle: { color: "#edf2f7" } },
  },
  visualMap: {
    min: Math.min(...rules.value.map((rule) => rule.lift), 1),
    max: Math.max(...rules.value.map((rule) => rule.lift), 2),
    dimension: 2,
    orient: "horizontal",
    left: "center",
    bottom: 0,
    calculable: false,
    text: ["高提升", "低提升"],
    inRange: { color: ["#bfdbfe", "#14b8a6", "#f59e0b"] },
    textStyle: { color: "#64748b" },
  },
  series: [
    {
      type: "scatter",
      symbolSize: (data: [number, number, number, string, number]) =>
        Math.max(9, Math.min(34, Math.sqrt(data[4]) * 1.4)),
      data: rules.value.map((rule) => [
        rule.support,
        rule.confidence,
        rule.lift,
        `${rule.antecedentNames} → ${rule.consequentNames}`,
        rule.coverageBasketCount,
      ]),
      itemStyle: { opacity: 0.8, borderColor: "#fff", borderWidth: 1 },
    },
  ],
}));

const driftCounts = computed(() =>
  drifts.value.reduce<Record<string, number>>((accumulator, item) => {
    accumulator[item.driftStatus] = (accumulator[item.driftStatus] ?? 0) + 1;
    return accumulator;
  }, {}),
);

async function loadRules(): Promise<void> {
  const response = await analyticsApi.getRules({
    segmentCode: selectedSegment.value,
    minLift: minLift.value,
    minConfidence: minConfidence.value,
    limit: 100,
  });
  rules.value = response.data;
}

let filterTimer: number | undefined;
watch([selectedSegment, minLift, minConfidence], () => {
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(() => void loadRules(), 250);
});

onMounted(async () => {
  try {
    const [segmentResponse, driftResponse] = await Promise.all([
      analyticsApi.getSegments(),
      analyticsApi.getRuleDrift({ limit: 200 }),
    ]);
    segments.value = segmentResponse.data;
    drifts.value = driftResponse.data;
    await loadRules();
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <LoadingState v-if="isLoading" />
  <div v-else class="view-stack">
    <section class="filter-bar">
      <label>
        分析客群
        <select v-model="selectedSegment">
          <option value="ALL">全部客户</option>
          <option v-for="segment in segments" :key="segment.segmentCode" :value="segment.segmentCode">
            {{ segment.segmentName }}
          </option>
        </select>
      </label>
      <label>
        最低提升度 <strong>{{ minLift.toFixed(1) }}</strong>
        <input v-model.number="minLift" type="range" min="1" max="5" step="0.1" />
      </label>
      <label>
        最低置信度 <strong>{{ Math.round(minConfidence * 100) }}%</strong>
        <input v-model.number="minConfidence" type="range" min="0.1" max="0.9" step="0.05" />
      </label>
      <div class="filter-result"><strong>{{ rules.length }}</strong><span>条有效规则</span></div>
    </section>

    <section class="dashboard-grid dashboard-grid--wide">
      <article class="panel panel--wide">
        <PanelHeader title="规则强度分布" description="点面积代表覆盖购物篮数，颜色代表提升度" badge="FP-GROWTH" />
        <EChart :option="ruleOption" height="390px" />
      </article>
      <article class="panel drift-panel">
        <PanelHeader title="年度规则漂移" description="新兴、消失与强度变化" />
        <div class="drift-grid">
          <div class="drift-stat drift-stat--new"><span>NEW</span><strong>{{ driftCounts.NEW ?? 0 }}</strong><small>新兴组合</small></div>
          <div class="drift-stat drift-stat--drop"><span>DROPPED</span><strong>{{ driftCounts.DROPPED ?? 0 }}</strong><small>消失组合</small></div>
          <div class="drift-stat drift-stat--grow"><span>GROWING</span><strong>{{ driftCounts.GROWING ?? 0 }}</strong><small>持续增强</small></div>
          <div class="drift-stat drift-stat--decline"><span>DECLINING</span><strong>{{ driftCounts.DECLINING ?? 0 }}</strong><small>持续减弱</small></div>
        </div>
        <p class="drift-note">创新指标：对同一客群的跨年度商品组合进行对齐，区分稳定偏好与短期热点。</p>
      </article>
    </section>

    <article class="panel">
      <PanelHeader title="可解释关联规则" description="支持度保证覆盖，置信度衡量命中，提升度排除商品本身热度" />
      <div class="table-wrap">
        <table>
          <thead><tr><th>前项商品</th><th></th><th>后项商品</th><th>支持度</th><th>置信度</th><th>提升度</th><th>覆盖篮子</th></tr></thead>
          <tbody>
            <tr v-for="rule in rules.slice(0, 12)" :key="rule.ruleId">
              <td><strong>{{ rule.antecedentNames }}</strong><small>{{ rule.antecedentCodes }}</small></td>
              <td class="rule-arrow">→</td>
              <td><strong>{{ rule.consequentNames }}</strong><small>{{ rule.consequentCodes }}</small></td>
              <td>{{ (rule.support * 100).toFixed(2) }}%</td>
              <td>{{ (rule.confidence * 100).toFixed(1) }}%</td>
              <td><span class="lift-pill">{{ rule.lift.toFixed(2) }}×</span></td>
              <td>{{ rule.coverageBasketCount.toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </div>
</template>
