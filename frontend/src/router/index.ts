import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "overview",
      component: () => import("@/views/OverviewView.vue"),
      meta: { title: "经营总览", eyebrow: "BUSINESS OVERVIEW" },
    },
    {
      path: "/rfm",
      name: "rfm",
      component: () => import("@/views/RfmView.vue"),
      meta: { title: "动态 RFM 客群", eyebrow: "CUSTOMER INTELLIGENCE" },
    },
    {
      path: "/basket",
      name: "basket",
      component: () => import("@/views/BasketView.vue"),
      meta: { title: "分群购物篮", eyebrow: "MARKET BASKET ANALYSIS" },
    },
    {
      path: "/strategy",
      name: "strategy",
      component: () => import("@/views/StrategyView.vue"),
      meta: { title: "营销策略中心", eyebrow: "ACTIONABLE STRATEGY" },
    },
  ],
});

router.afterEach((route) => {
  document.title = `${String(route.meta.title)} · 客群智篮`;
});

export default router;
