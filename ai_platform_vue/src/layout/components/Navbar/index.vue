<template>
  <div class="navbar">
    <div class="left-menu">
      <el-icon class="hamburger" @click="toggleSidebar">
        <Expand v-if="!isCollapsed" />
        <Fold v-else />
      </el-icon>
      <div class="breadcrumb">KaleidoPilot</div>
    </div>
    <div class="right-menu">
      <el-dropdown trigger="click" @command="handleLogout">
        <div class="avatar-container">
          <span class="username">{{ displayName }}</span>
          <el-icon class="el-icon--right"><CaretBottom /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

defineProps<{
  isCollapsed: boolean
}>()

const router = useRouter()

const displayName = computed(() => {
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
    return userInfo.realName || userInfo.account || '用户'
  } catch {
    return '用户'
  }
})

const emit = defineEmits(['toggle-sidebar'])

const toggleSidebar = () => {
  emit('toggle-sidebar')
}

const handleLogout = (command: string) => {
  if (command === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    localStorage.removeItem('currentOrganization')
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
.navbar {
  height: 60px;
  overflow: hidden;
  position: relative;
  background-color: transparent;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;

  .left-menu {
    display: flex;
    align-items: center;
    
    .hamburger {
      font-size: 20px;
      cursor: pointer;
      margin-right: 15px;
      color: #606266;
      &:hover {
        color: var(--primary-color);
      }
    }
    
    .breadcrumb {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }

  .right-menu {
    display: flex;
    align-items: center;

    .avatar-container {
      cursor: pointer;
      display: flex;
      align-items: center;
      color: #606266;
      .username {
        margin-right: 5px;
        font-size: 14px;
      }
    }
  }
}
</style>
