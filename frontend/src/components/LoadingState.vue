<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: "正在加载真实分析结果" });
</script>

<template>
  <div class="loading-state">
    <span class="loading-state__spinner"></span>
    <p>{{ label }}</p>
  </div>
</template>
