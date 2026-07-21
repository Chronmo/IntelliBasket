<script setup lang="ts">
import { ArrowRight, BadgeCheck, Lightbulb, ScanSearch, Sparkles } from "@lucide/vue";
import { onMounted, ref } from "vue";

import { analyticsApi } from "@/api/client";
import type { AssociationRule, RfmSegment, TopProduct } from "@/api/types";
import PanelHeader from "@/components/PanelHeader.vue";

const segments = ref<RfmSegment[]>([]);
const products = ref<TopProduct[]>([]);
const recommendations = ref<AssociationRule[]>([]);
const segmentCode = ref("ALL");
const productCode = ref("");
const minLift = ref(1.2);
const isSubmitting = ref(false);
const hasSubmitted = ref(false);

async function createRecommendations(): Promise<void> {
  if (!productCode.value) return;
  isSubmitting.value = true;
  try {
    const response = await analyticsApi.getRecommendations({
      segmentCode: segmentCode.value,
      productCode: productCode.value,
      minLift: minLift.value,
      limit: 8,
    });
    recommendations.value = response.data;
    hasSubmitted.value = true;
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(async () => {
  const [segmentResponse, productResponse] = await Promise.all([
    analyticsApi.getSegments(),
    analyticsApi.getTopProducts(100),
  ]);
  segments.value = segmentResponse.data;
  products.value = productResponse.data;
  productCode.value = products.value[0]?.stockCode ?? "";
});
</script>

<template>
  <div class="strategy-layout">
    <aside class="strategy-form panel">
      <PanelHeader title="配置营销场景" description="用业务约束生成可落地组合" badge="LIVE QUERY" />

      <label class="field">
        <span>目标客群</span>
        <select v-model="segmentCode">
          <option value="ALL">全部客户（全局基线）</option>
          <option v-for="segment in segments" :key="segment.segmentCode" :value="segment.segmentCode">
            {{ segment.segmentName }} · {{ segment.customerCount }} 人
          </option>
        </select>
        <small>分群规则可减少“热门但不适合该客群”的误推荐。</small>
      </label>

      <label class="field">
        <span>主推商品</span>
        <select v-model="productCode">
          <option v-for="product in products" :key="`${product.stockCode}-${product.productName}`" :value="product.stockCode">
            {{ product.productName }} · {{ product.stockCode }}
          </option>
        </select>
        <small>选择活动入口商品，系统只返回其作为前项的规则。</small>
      </label>

      <label class="field">
        <span>最低提升度 <strong>{{ minLift.toFixed(1) }}×</strong></span>
        <input v-model.number="minLift" type="range" min="1" max="5" step="0.1" />
        <small>大于 1 表示组合购买概率高于后项商品的自然购买概率。</small>
      </label>

      <button class="primary-button" :disabled="isSubmitting || !productCode" @click="createRecommendations">
        <Sparkles :size="18" />
        {{ isSubmitting ? "正在计算策略" : "生成营销建议" }}
      </button>

      <div class="method-note">
        <ScanSearch :size="18" />
        <p><strong>可靠边界</strong><br />发票号作为购物篮、Customer ID 作为客户、取消单与退货在 DWD 层隔离。</p>
      </div>
    </aside>

    <section class="strategy-results">
      <div v-if="!hasSubmitted" class="strategy-empty panel">
        <span><Lightbulb :size="32" /></span>
        <h2>从规则走向营销动作</h2>
        <p>选择一个客群与入口商品，系统将依据真实订单中的分群规则，返回组合商品、依据与建议动作。</p>
        <div class="strategy-steps">
          <span>01 客群约束</span><ArrowRight :size="16" /><span>02 商品入口</span><ArrowRight :size="16" /><span>03 规则校验</span><ArrowRight :size="16" /><span>04 策略输出</span>
        </div>
      </div>

      <template v-else>
        <header class="result-heading">
          <div><span class="eyebrow">RECOMMENDATION RESULT</span><h2>共找到 {{ recommendations.length }} 个可信组合</h2></div>
          <span class="result-status"><BadgeCheck :size="17" />真实订单 + 模型增强</span>
        </header>

        <div v-if="recommendations.length" class="recommendation-list">
          <article v-for="(rule, index) in recommendations" :key="rule.ruleId" class="recommendation-card">
            <span class="recommendation-card__rank">{{ String(index + 1).padStart(2, "0") }}</span>
            <div class="recommendation-card__main">
              <span class="strategy-label">{{ rule.strategy }}</span>
              <div class="product-flow">
                <strong>{{ rule.antecedentNames }}</strong>
                <ArrowRight :size="20" />
                <strong>{{ rule.consequentNames }}</strong>
              </div>
              <p>{{ rule.reason }}</p>
              <small v-if="rule.dataBasis" class="data-basis">
                分析依据：真实交易与可追溯模型增强场景
              </small>
            </div>
            <div class="rule-evidence">
              <div><span>置信度</span><strong>{{ (rule.confidence * 100).toFixed(1) }}%</strong></div>
              <div><span>提升度</span><strong>{{ rule.lift.toFixed(2) }}×</strong></div>
              <div><span>覆盖篮子</span><strong>{{ rule.coverageBasketCount }}</strong></div>
            </div>
          </article>
        </div>
        <div v-else class="no-result panel">当前阈值下没有可靠规则，请降低提升度或更换入口商品。</div>
      </template>
    </section>
  </div>
</template>
