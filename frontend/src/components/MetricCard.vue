<script setup lang="ts">
import type { Component } from "vue";

withDefaults(
  defineProps<{
    label: string;
    value: string;
    note: string;
    icon: Component;
    tone?: "teal" | "orange" | "blue" | "violet";
  }>(),
  { tone: "teal" },
);
</script>

<template>
  <article class="metric-card" :class="`metric-card--${tone}`">
    <div class="metric-card__icon"><component :is="icon" :size="20" /></div>
    <p>{{ label }}</p>
    <strong>{{ value }}</strong>
    <span>{{ note }}</span>
  </article>
</template>
