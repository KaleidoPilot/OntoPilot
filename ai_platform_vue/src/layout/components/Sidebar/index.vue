<template>
  <div class="sidebar">
    <div class="sidebar-logo" v-if="!isCollapsed">
      <div class="logo-title">KaleidoPilot</div>
      <div class="logo-subtitle">数智人平台</div>
    </div>
    <div v-if="!isCollapsed && currentOrganization" class="organization-context">
      <span class="organization-label">当前公司</span>
      <strong :title="currentOrganization.name">{{ currentOrganization.name }}</strong>
      <el-button v-if="!isExternal && !isEnterpriseAdmin" link @click="switchOrganization">切换公司</el-button>
    </div>
    <el-scrollbar wrap-class="scrollbar-wrapper">
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.7)"
        active-text-color="#ffffff"
        :collapse-transition="false"
        mode="vertical"
        router
      >
        <el-menu-item v-if="!isExternal" index="/organization">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>{{ isEnterpriseAdmin ? '公司信息' : '公司管理' }}</template>
        </el-menu-item>

        <el-sub-menu v-if="!isExternal && hasOrganizationContext" index="/project">
          <template #title>
            <el-icon><FolderOpened /></el-icon>
            <span>数据字典管理</span>
          </template>
          
          <el-menu-item index="/project/group">
            <el-icon><FolderOpened /></el-icon>
            <template #title>数据字典列表</template>
          </el-menu-item>

          <div class="project-group-tree-wrap">
            <el-skeleton v-if="loading" :rows="3" animated />
            <el-tree
              v-else-if="projectGroupTree.length"
              :data="projectGroupTree"
              node-key="id"
              :props="{ children: 'children', label: 'groupName' }"
              :current-node-key="currentProjectGroupId"
              default-expand-all
              highlight-current
              :expand-on-click-node="false"
              aria-label="项目组导航"
              @node-click="openProjectGroup"
            >
              <template #default="{ data }">
                <div class="project-group-node" :class="{ 'is-disabled': data.enabled !== 1 }">
                  <el-icon><Folder /></el-icon>
                  <span class="project-group-name">{{ data.groupName }}</span>
                  <span v-if="data.enabled !== 1" class="disabled-label">停用</span>
                </div>
              </template>
            </el-tree>
            <div v-else class="empty-project-group">暂无数据字典</div>
          </div>
        </el-sub-menu>

        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/knowledge">
          <el-icon><Files /></el-icon>
          <template #title>知识库管理</template>
        </el-menu-item>

        <!-- <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/agent/list">
          <el-icon><Monitor /></el-icon>
          <template #title>智能体管理</template>
        </el-menu-item> -->

        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/user/external">
          <el-icon><UserFilled /></el-icon>
          <template #title>用户组管理</template>
        </el-menu-item>
        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/user/enterprise">
          <el-icon><UserFilled /></el-icon>
          <template #title>企业后台用户管理</template>
        </el-menu-item>

        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/skill/groups">
          <el-icon><Collection /></el-icon>
          <template #title>技能管理</template>
        </el-menu-item>
        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/skill/templates"><el-icon><Files /></el-icon><template #title>模板管理</template></el-menu-item>

        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/system/config">
          <el-icon><Setting /></el-icon>
          <template #title>系统配置管理</template>
        </el-menu-item>
        <el-menu-item v-if="!isExternal && hasOrganizationContext" index="/mcp">
          <el-icon><Connection /></el-icon>
          <template #title>MCP 管理</template>
        </el-menu-item>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Collection, Connection, Files, Folder, FolderOpened, Monitor, OfficeBuilding, Setting, UserFilled } from '@element-plus/icons-vue'
import { getProjectGroupList, type ProjectGroup } from '@/api/project'

interface ProjectGroupTreeNode extends ProjectGroup {
  children: ProjectGroupTreeNode[]
}

defineProps<{
  isCollapsed: boolean
}>()

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const projectGroups = ref<ProjectGroup[]>([])
interface OrganizationContext {
  id: number
  orgCode: string
  name: string
}

const readStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
}

const isExternal = (() => {
  return readStoredUser().userType === 'external'
})()
const isEnterpriseAdmin = readStoredUser().deptLevel === 1
const readOrganization = (): OrganizationContext | null => {
  try {
    const fixed = isExternal || isEnterpriseAdmin
    const source = fixed
      ? readStoredUser()
      : JSON.parse(localStorage.getItem('currentOrganization') || '{}')
    const id = Number(fixed ? source.orgId : source.id)
    if (!Number.isInteger(id) || id <= 0) return null
    return {
      id,
      orgCode: String(source.orgCode || ''),
      name: String((fixed ? source.orgName : source.name) || source.orgCode || `公司 ${id}`)
    }
  } catch {
    return null
  }
}
const currentOrganization = ref<OrganizationContext | null>(readOrganization())
const hasOrganizationContext = computed(() => currentOrganization.value !== null)

const activeMenu = computed(() => {
  if (route.path.startsWith('/project/group')) return '/project/group'
  if (route.path.startsWith('/organization')) return '/organization'
  if (route.path.startsWith('/knowledge')) return '/knowledge'
  if (route.path.startsWith('/user/external')) return '/user/external'
  return route.path
})

const currentProjectGroupId = computed(() => {
  const groupId = Number(route.params.groupId)
  return Number.isInteger(groupId) && groupId > 0 ? groupId : undefined
})

const projectGroupTree = computed<ProjectGroupTreeNode[]>(() =>
  // 暂时不展示二级技能组，侧栏只保留一级项目组，避免再出现分层。
  projectGroups.value
    .filter((group) => group.level === 0 && group.parentId === null)
    .map<ProjectGroupTreeNode>((group) => ({ ...group, children: [] }))
)

const fetchProjectGroups = async () => {
  if (!hasOrganizationContext.value) {
    projectGroups.value = []
    return
  }
  loading.value = true
  try {
    const response = await getProjectGroupList()
    if (response.success) {
      projectGroups.value = response.data.list
    }
  } catch {
    projectGroups.value = []
  } finally {
    loading.value = false
  }
}

const openProjectGroup = (projectGroup: ProjectGroup) => {
  router.push(`/project/group/${projectGroup.id}`)
}

const switchOrganization = () => {
  if (isEnterpriseAdmin) return
  localStorage.removeItem('currentOrganization')
  currentOrganization.value = null
  projectGroups.value = []
  router.push('/organization')
}

const handleOrganizationChanged = () => {
  currentOrganization.value = readOrganization()
  if (!isExternal && currentOrganization.value) fetchProjectGroups()
}

onMounted(() => {
  if (!isExternal && hasOrganizationContext.value) {
    fetchProjectGroups()
  }
  window.addEventListener('project-groups-changed', fetchProjectGroups)
  window.addEventListener('organization-changed', handleOrganizationChanged)
})

onBeforeUnmount(() => {
  window.removeEventListener('project-groups-changed', fetchProjectGroups)
  window.removeEventListener('organization-changed', handleOrganizationChanged)
})
</script>

<style scoped lang="scss">
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;

  .sidebar-logo {
    padding: 24px 20px;
    color: #fff;
    .logo-title {
      font-size: 20px;
      font-weight: bold;
      letter-spacing: 1px;
    }
    .logo-subtitle {
      font-size: 14px;
      opacity: 0.6;
      margin-top: 4px;
    }
  }

  .organization-context {
    margin: 0 12px 12px;
    padding: 10px 12px;
    color: #fff;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;

    .organization-label {
      display: block;
      margin-bottom: 4px;
      color: rgba(255, 255, 255, 0.52);
      font-size: 11px;
    }

    strong {
      display: block;
      overflow: hidden;
      font-size: 13px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .el-button {
      height: auto;
      margin-top: 5px;
      padding: 0;
      color: #aebfff;
      font-size: 12px;
    }
  }

  .el-menu {
    border: none;
    flex: 1;
    width: 100% !important;
  }

  .project-group-tree-wrap {
    padding: 6px 0 6px 12px;

    :deep(.el-skeleton__item) {
      background: rgba(255, 255, 255, 0.1);
    }

    :deep(.el-tree) {
      color: rgba(255, 255, 255, 0.72);
      background: transparent;

      .el-tree-node__content {
        min-height: 38px;
        padding-right: 8px;
        border-radius: 6px;
      }

      .el-tree-node__content:hover,
      .el-tree-node.is-current > .el-tree-node__content {
        color: #fff;
        background: rgba(79, 110, 247, 0.42);
      }

      .el-tree-node__expand-icon {
        color: rgba(255, 255, 255, 0.54);
      }
    }
  }

  .project-group-node {
    display: flex;
    align-items: center;
    min-width: 0;
    width: 100%;
    gap: 7px;

    &.is-disabled {
      opacity: 0.6;
    }
  }

  .project-group-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .disabled-label {
    margin-left: auto;
    color: rgba(255, 255, 255, 0.56);
    font-size: 11px;
  }

  .empty-project-group {
    padding: 8px 10px;
    color: rgba(255, 255, 255, 0.38);
    font-size: 12px;
  }
}
</style>
