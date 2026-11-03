<template>
  <router-view />
  <!-- <AIChat /> -->
</template>

<script setup lang="ts">
import AIChat from '@/components/AIChat/index.vue'
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}
#app {
  height: 100vh;
}
</style>
