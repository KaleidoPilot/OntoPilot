<template>
  <div :class="['app-wrapper', { 'sidebar-collapsed': isCollapsed }]">
    <Sidebar :is-collapsed="isCollapsed" class="sidebar-container" />
    <div class="main-container">
      <div class="fixed-header">
        <Navbar :is-collapsed="isCollapsed" @toggle-sidebar="isCollapsed = !isCollapsed" />
      </div>
      <AppMain />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './components/Sidebar/index.vue'
import Navbar from './components/Navbar/index.vue'
import AppMain from './components/AppMain/index.vue'

const isCollapsed = ref(false)
</script>

<style scoped lang="scss">
.app-wrapper {
  display: flex;
  height: 100vh;
  width: 100%;
  background-color: var(--bg-dark);
}

.sidebar-container {
  width: 210px;
  background-color: var(--sidebar-bg);
  height: 100%;
  transition: width 0.3s cubic-bezier(0.2, 0, 0, 1);
  border-right: 1px solid var(--border-color);
  z-index: 1001;
}

.sidebar-collapsed .sidebar-container {
  width: 64px;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
  transition: margin-left 0.3s;
}

.fixed-header {
  width: 100%;
  height: 60px;
  background-color: transparent;
}
</style>
