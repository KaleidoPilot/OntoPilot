<template>
  <div class="project-group-page">
    <el-card class="project-group-card" shadow="never">
      <template #header>
        <div class="page-header">
          <div>
            <h1>数据字典管理</h1>
            <p>描述：维护一级数据字典；完整层级显示在左侧，进入具体数据字典后可继续新增下级。</p>
          </div>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">
            新增数据字典
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="errorMessage"
        class="error-alert"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
      >
        <template #default>
          <el-button link type="primary" @click="fetchProjectGroups">重新加载</el-button>
        </template>
      </el-alert>

      <div class="search-toolbar">
        <el-input
          v-model="searchKeyword"
          class="search-input"
          :prefix-icon="Search"
          clearable
          placeholder="请输入事项管理名称"
          aria-label="按事项管理名称搜索"
        />
        <span v-if="searchKeyword.trim()" class="search-result-count">
          找到 {{ filteredRootProjectGroups.length }} 条
        </span>
      </div>

      <el-table
        v-loading="loading"
        :data="filteredRootProjectGroups"
        row-key="id"
        class="project-group-table"
      >
        <el-table-column prop="groupName" label="数据字典名称" min-width="300">
          <template #default="scope">
            <div class="group-name-cell">
              <el-icon><Folder /></el-icon>
              <el-button link type="primary" @click="openProjectGroup(scope.row)">
                {{ scope.row.groupName }}
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.enabled === 1 ? 'success' : 'info'">
              {{ scope.row.enabled === 1 ? '已启用' : '已停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="沙箱" min-width="140">
          <template #default="{ row }"><el-tag :type="row.sandboxConfigId ? 'info' : 'warning'">{{ sandboxLabel(row.sandboxConfigId) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" min-width="180">
          <template #default="scope">{{ scope.row.createTime || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button link type="primary" :icon="ArrowRight" @click="openProjectGroup(scope.row)">
              进入
            </el-button>
            <el-button link type="primary" :icon="Edit" @click="openEditDialog(scope.row)">
              编辑
            </el-button>
            <el-button link type="danger" :icon="Delete" @click="confirmDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="searchKeyword.trim() ? '未找到匹配的事项管理' : '暂无一级项目组'">
            <el-button v-if="!searchKeyword.trim()" type="primary" :icon="Plus" @click="openCreateDialog">
              创建第一个项目组
            </el-button>
          </el-empty>
        </template>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增项目组' : '编辑项目组'"
      width="min(560px, 94vw)"
      :close-on-click-modal="!submitting"
      :close-on-press-escape="!submitting"
      :show-close="!submitting"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :disabled="submitting"
        label-width="100px"
        status-icon
      >
        <el-form-item label="项目组名称" prop="groupName">
          <el-input
            v-model="form.groupName"
            maxlength="100"
            show-word-limit
            clearable
            placeholder="例如：房屋管理"
          />
        </el-form-item>
        <el-form-item label="启用状态" prop="enabled">
          <el-switch
            v-model="form.enabled"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
        <el-form-item label="沙箱" prop="sandboxConfigId">
          <el-select v-model="form.sandboxConfigId" filterable :filter-method="filterSandboxes" @visible-change="sandboxSearch = ''" :loading="sandboxLoading" placeholder="输入名称或 URL 搜索沙箱" style="width: 100%" :disabled="submitting">
            <el-option v-for="item in filteredSandboxOptions" :key="item.id" :label="item.name || item.url" :value="item.id" />
            <el-option v-if="form.sandboxConfigId && !sandboxOptions.some(item => item.id === form.sandboxConfigId)" label="已绑定沙箱不可用，请重新选择" :value="form.sandboxConfigId" disabled />
          </el-select>
          <el-alert v-if="sandboxError" :title="sandboxError" type="error" :closable="false"><el-button link type="primary" @click="loadSandboxOptions">重新加载</el-button></el-alert>
          <span v-else-if="!sandboxLoading && !sandboxOptions.length">暂无可用沙箱，请先到系统配置新增并启用沙箱。</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button :disabled="submitting" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ dialogMode === 'create' ? '确定新增' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Delete, Edit, Folder, Plus, Search } from '@element-plus/icons-vue'
import { getSandboxOptions, type SandboxOption } from '@/api/system'
import {
  createProjectGroup,
  getProjectGroupList,
  deleteProjectGroup,
  updateProjectGroup,
  type ProjectGroup,
  type ProjectGroupCreateParams
} from '@/api/project'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const errorMessage = ref('')
const searchKeyword = ref('')
const projectGroups = ref<ProjectGroup[]>([])
const formRef = ref<FormInstance>()
const router = useRouter()
const sandboxOptions = ref<SandboxOption[]>([])
const sandboxSearch = ref('')
const filterSandboxes = (query: string) => { sandboxSearch.value = query.trim().toLowerCase() }
const filteredSandboxOptions = computed(() => sandboxOptions.value.filter(item => `${item.name || ''} ${item.url}`.toLowerCase().includes(sandboxSearch.value)))
const sandboxLabel = (id?: number | null) => {
  const item = sandboxOptions.value.find(option => option.id === id)
  return item ? item.name || item.url : id ? '已绑定沙箱（不可用）' : '待选择沙箱'
}
const sandboxLoading = ref(false)
const sandboxError = ref('')
const loadSandboxOptions = async () => {
  sandboxLoading.value = true
  sandboxError.value = ''
  try {
    const response = await getSandboxOptions()
    if (!response.success) throw new Error(response.message || '沙箱加载失败')
    sandboxOptions.value = response.data.list
  } catch (error) {
    sandboxOptions.value = []
    sandboxError.value = error instanceof Error ? error.message : '沙箱加载失败'
  } finally { sandboxLoading.value = false }
}

const createDefaultForm = (): ProjectGroupCreateParams => ({
  groupName: '',
  parentId: null,
  sandboxConfigId: null,
  sortOrder: 0,
  enabled: 1
})

const form = reactive<ProjectGroupCreateParams>(createDefaultForm())

const rules: FormRules<ProjectGroupCreateParams> = {
  sandboxConfigId: [{ required: true, message: '请选择项目组使用的沙箱', trigger: 'change' }],
  groupName: [
    { required: true, message: '请输入项目组名称', trigger: 'blur' },
    { min: 1, max: 100, message: '项目组名称不能超过 100 个字符', trigger: 'blur' }
  ]
}

const rootProjectGroups = computed(() =>
  projectGroups.value.filter((projectGroup) => projectGroup.parentId === null)
)

const filteredRootProjectGroups = computed(() => {
  const keyword = searchKeyword.value.trim().toLocaleLowerCase()
  if (!keyword) return rootProjectGroups.value
  return rootProjectGroups.value.filter((projectGroup) =>
    projectGroup.groupName.toLocaleLowerCase().includes(keyword)
  )
})

const getErrorMessage = (error: unknown, fallback: string) =>
  error instanceof Error && error.message ? error.message : fallback

const fetchProjectGroups = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getProjectGroupList()
    if (response.success) {
      projectGroups.value = response.data.list
    } else {
      errorMessage.value = response.message || '项目组加载失败'
    }
  } catch (error: unknown) {
    errorMessage.value = getErrorMessage(error, '项目组加载失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, createDefaultForm())
  editingId.value = null
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  void loadSandboxOptions()
  resetForm()
  dialogMode.value = 'create'
  dialogVisible.value = true
}

const openProjectGroup = (projectGroup: ProjectGroup) => {
  router.push(`/project/group/${projectGroup.id}`)
}

const openEditDialog = (projectGroup: ProjectGroup) => {
  void loadSandboxOptions()
  dialogMode.value = 'edit'
  editingId.value = projectGroup.id
  Object.assign(form, {
    groupName: projectGroup.groupName,
    parentId: projectGroup.parentId,
    sandboxConfigId: projectGroup.sandboxConfigId,
    sortOrder: projectGroup.sortOrder,
    enabled: projectGroup.enabled
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  if (sandboxLoading.value || sandboxError.value || submitting.value) return
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const groupName = form.groupName.trim()
    let response: Awaited<ReturnType<typeof createProjectGroup>>
    if (dialogMode.value === 'create') {
      response = await createProjectGroup({ ...form, groupName })
    } else {
      if (editingId.value === null) {
        ElMessage.error('未找到需要修改的项目组')
        return
      }
      response = await updateProjectGroup({
        id: editingId.value,
        groupName,
        sortOrder: form.sortOrder,
        sandboxConfigId: form.sandboxConfigId,
        enabled: form.enabled
      })
    }
    if (response.success) {
      ElMessage.success(dialogMode.value === 'create' ? '项目组新增成功' : '项目组修改成功')
      dialogVisible.value = false
      await fetchProjectGroups()
      window.dispatchEvent(new Event('project-groups-changed'))
    } else {
      ElMessage.error(response.message || '项目组保存失败')
    }
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '项目组保存失败'))
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (projectGroup: ProjectGroup) => {
  try {
    await ElMessageBox.confirm(
      `确定删除项目组“${projectGroup.groupName}”吗？这会永久删除数据库中的对应记录，且无法恢复。`,
      '删除项目组',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const response = await deleteProjectGroup({ id: projectGroup.id })
    if (response.success) {
      ElMessage.success('项目组删除成功')
      await fetchProjectGroups()
      window.dispatchEvent(new Event('project-groups-changed'))
    } else {
      ElMessage.error(response.message || '项目组删除失败')
    }
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '项目组删除失败'))
  }
}

onMounted(() => { void fetchProjectGroups(); void loadSandboxOptions() })
</script>

<style scoped lang="scss">
.project-group-page {
  box-sizing: border-box;
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 24px;
  background: var(--bg-dark);
}

.project-group-card {
  min-height: calc(100vh - 108px);
  border: none;

  :deep(.el-card__header) {
    padding: 22px 24px;
  }

  :deep(.el-card__body) {
    padding: 24px;
  }
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;

  h1 {
    margin: 0;
    color: #303133;
    font-size: 22px;
    line-height: 1.4;
  }

  p {
    margin: 6px 0 0;
    color: #909399;
    font-size: 14px;
  }
}

.error-alert {
  margin-bottom: 20px;
}

.search-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: min(360px, 100%);
}

.search-result-count {
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.project-group-table {
  width: 100%;
}

.group-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #303133;
  font-weight: 500;

  .el-icon {
    color: var(--primary-color);
  }
}

@media (max-width: 768px) {
  .project-group-page {
    padding: 12px;
  }

  .project-group-card {
    min-height: calc(100vh - 84px);
  }

  .page-header {
    align-items: flex-start;
    flex-direction: column;

    .el-button {
      width: 100%;
    }
  }

  .search-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  :deep(.el-dialog) {
    width: calc(100% - 24px) !important;
  }
}
</style>
