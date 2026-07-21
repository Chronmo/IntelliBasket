<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
  badge?: string;
}>();
</script>

<template>
  <header class="panel-header">
    <div>
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </div>
    <span v-if="badge" class="panel-badge">{{ badge }}</span>
    <slot />
  </header>
</template>
