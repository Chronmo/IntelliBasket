<script setup lang="ts">
import {
  ChartNoAxesCombined,
  DatabaseZap,
  LayoutDashboard,
  Network,
  Sparkles,
} from "@lucide/vue";
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";

import { analyticsApi } from "@/api/client";

const route = useRoute();
const pageTitle = computed(() => String(route.meta.title ?? "经营总览"));
const pageEyebrow = computed(() => String(route.meta.eyebrow ?? "INTELLIBASKET"));
const serviceReady = ref(false);

const navigationItems = [
  { path: "/", label: "经营总览", icon: LayoutDashboard },
  { path: "/rfm", label: "动态 RFM", icon: ChartNoAxesCombined },
  { path: "/basket", label: "分群购物篮", icon: Network },
  { path: "/strategy", label: "策略中心", icon: Sparkles },
];

onMounted(async () => {
  try {
    const response = await analyticsApi.getReadiness();
    serviceReady.value = response.data.status === "READY";
  } catch {
    serviceReady.value = false;
  }
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand__mark"><DatabaseZap :size="25" /></span>
        <div>
          <strong>客群智篮</strong>
          <small>INTELLIBASKET</small>
        </div>
      </div>

      <nav class="sidebar__nav" aria-label="主导航">
        <RouterLink v-for="item in navigationItems" :key="item.path" :to="item.path">
          <component :is="item.icon" :size="19" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar__foot">
        <span class="status-dot" :class="{ 'status-dot--offline': !serviceReady }"></span>
        <div>
          <strong>{{ serviceReady ? "分析服务在线" : "分析服务离线" }}</strong>
          <small>Hive · RFM · FP-Growth</small>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div>
          <span class="eyebrow">{{ pageEyebrow }}</span>
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="data-badge">
          <span>DATA WINDOW</span>
          <strong>2009.12 — 2011.12</strong>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
