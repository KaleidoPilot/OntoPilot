<template>
  <div class="public-skill-page">
    <el-card class="public-skill-card" shadow="never">
      <template #header>
        <div class="page-header">
          <h2>公共技能管理</h2>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增公共技能</el-button>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          class="skill-search"
          clearable
          :prefix-icon="Search"
          placeholder="搜索技能名称、描述或规则内容"
          aria-label="搜索公共技能"
        />
        <div class="toolbar-actions">
          <el-select
            v-model="skillLevelTypeFilter"
            class="status-filter"
            clearable
            placeholder="全部类型"
            aria-label="按技能类型筛选公共技能"
          >
            <el-option label="主技能" :value="1" />
            <el-option label="子技能" :value="2" />
          </el-select>
          <el-select
            v-model="enabledFilter"
            class="status-filter"
            clearable
            placeholder="全部状态"
            aria-label="按状态筛选公共技能"
          >
            <el-option label="已启用" :value="1" />
            <el-option label="已禁用" :value="0" />
          </el-select>
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :disabled="selectedSkills.length === 0"
            :loading="batchDeleting"
            @click="confirmBatchDelete"
          >
            批量删除<span v-if="selectedSkills.length">（{{ selectedSkills.length }}）</span>
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="listError"
        class="list-alert"
        :title="listError"
        type="error"
        show-icon
        :closable="false"
      />

      <div class="table-area">
        <el-table
          ref="tableRef"
          v-loading="listLoading"
          :data="skillList"
          row-key="id"
          size="large"
          class="skill-table"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="52" reserve-selection />
          <el-table-column prop="skillName" label="技能名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="技能类型" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.skillLevelType === 1 ? 'primary' : 'success'" effect="light">
                {{ row.skillLevelType === 1 ? '主技能' : '子技能' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="技能描述" min-width="230" show-overflow-tooltip>
            <template #default="{ row }">{{ row.skillDescription || '—' }}</template>
          </el-table-column>
          <el-table-column prop="ruleContent" label="规则内容" min-width="300" show-overflow-tooltip />
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.enabled === 1 ? 'success' : 'info'" effect="light">
                {{ row.enabled === 1 ? '已启用' : '已禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" align="center">
            <template #default="{ row }">
              <el-button type="primary" link :icon="Edit" @click="openEditDialog(row)">
                编辑
              </el-button>
              <el-button
                type="danger"
                link
                :icon="Delete"
                :loading="deletingSkillId === row.id"
                @click="confirmDelete(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty
              :description="keyword.trim() || enabledFilter !== '' || skillLevelTypeFilter !== '' ? '没有符合条件的公共技能' : '暂无公共技能'"
              :image-size="92"
            />
          </template>
        </el-table>
      </div>

      <div class="pagination-area">
        <el-pagination
          v-model:current-page="pageNo"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next, jumper"
          background
          @current-change="loadPublicSkills"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="createDialogVisible"
      :title="isEditing ? '编辑公共技能' : '新增公共技能'"
      width="min(620px, 94vw)"
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
        status-icon
      >
        <el-form-item label="技能名称" prop="skillName">
          <el-input v-model="createForm.skillName" maxlength="100" show-word-limit placeholder="请输入技能名称" />
        </el-form-item>
        <el-form-item label="技能类型" prop="skillLevelType">
          <el-radio-group v-model="createForm.skillLevelType" @change="handleSkillLevelTypeChange">
            <el-radio-button :value="1">主技能</el-radio-button>
            <el-radio-button :value="2">子技能</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="createForm.skillLevelType === 1" label="关联子技能" prop="subSkillIds">
          <el-tree-select
            v-model="createForm.subSkillIds"
            :data="publicSubSkillOptions"
            :props="{ label: 'skillName', value: 'id' }"
            class="sub-skill-select"
            node-key="id"
            multiple
            show-checkbox
            check-strictly
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="搜索并勾选公共子技能"
            no-data-text="暂无已启用的公共子技能"
          />
        </el-form-item>
        <el-form-item label="技能描述" prop="skillDescription">
          <el-input
            v-model="createForm.skillDescription"
            type="textarea"
            :rows="3"
            maxlength="255"
            show-word-limit
            placeholder="请输入技能描述"
          />
        </el-form-item>
        <el-form-item label="规则内容" prop="ruleContent">
          <el-input
            v-model="createForm.ruleContent"
            type="textarea"
            :rows="8"
            placeholder="请输入技能规则内容"
          />
        </el-form-item>
        <el-form-item label="是否启用" prop="enabled">
          <el-switch v-model="createForm.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <SkillMcpBinding ref="skillMcpRef" :open="createDialogVisible" :skill-id="editingSkillId || undefined" :skill-type="1" @ready="skillMcpReady = $event" />
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!skillMcpReady" @click="submitSkill">
          {{ isEditing ? '保存修改' : '确定新增' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import SkillMcpBinding from '@/views/mcp/SkillMcpBinding.vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Edit, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type TableInstance } from 'element-plus'

import {
  batchDeletePublicSkills,
  createPublicSkill,
  deletePublicSkill,
  getPublicSubSkillOptions,
  getPublicSkillPage,
  updatePublicSkill,
  type PublicSkill,
  type PublicSkillCreate,
  type SubSkillOption
} from '@/api/skill'


const PAGE_SIZE = 5

const tableRef = ref<TableInstance>()
const skillList = ref<PublicSkill[]>([])
const publicSubSkillOptions = ref<SubSkillOption[]>([])
const selectedSkills = ref<PublicSkill[]>([])
const listLoading = ref(false)
const listError = ref('')
const keyword = ref('')
const enabledFilter = ref<'' | 0 | 1>('')
const skillLevelTypeFilter = ref<'' | 1 | 2>('')
const pageNo = ref(1)
const pageSize = PAGE_SIZE
const total = ref(0)
const deletingSkillId = ref<number | null>(null)
const batchDeleting = ref(false)
let requestSequence = 0
let keywordTimer: ReturnType<typeof setTimeout> | undefined

const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const submitting = ref(false)
const skillMcpRef = ref<InstanceType<typeof SkillMcpBinding>>(), skillMcpReady = ref(false)
const editingSkillId = ref<number | null>(null)
const isEditing = computed(() => editingSkillId.value !== null)

const defaultCreateForm = (): PublicSkillCreate => ({
  skillName: '',
  skillDescription: '',
  skillLevelType: 1,
  subSkillIds: [],
  ruleContent: '',
  enabled: 1
})

const createForm = reactive<PublicSkillCreate>(defaultCreateForm())
const createRules: FormRules<PublicSkillCreate> = {
  skillName: [
    { required: true, message: '请输入技能名称', trigger: 'blur' },
    { min: 1, max: 100, message: '技能名称不能超过100个字符', trigger: 'blur' }
  ],
  skillDescription: [
    { max: 255, message: '技能描述不能超过255个字符', trigger: 'blur' }
  ],
  skillLevelType: [
    { required: true, message: '请选择技能类型', trigger: 'change' }
  ],
  ruleContent: [
    { required: true, message: '请输入规则内容', trigger: 'blur' }
  ]
}

const getErrorMessage = (error: unknown, fallback: string) => {
  return error instanceof Error && error.message ? error.message : fallback
}

const loadPublicSkills = async () => {
  const sequence = ++requestSequence
  const requestedPageNo = pageNo.value
  listLoading.value = true
  listError.value = ''
  try {
    const response = await getPublicSkillPage({
      keyword: keyword.value.trim() || undefined,
      enabled: enabledFilter.value === '' ? undefined : enabledFilter.value,
      skillLevelType: skillLevelTypeFilter.value === '' ? undefined : skillLevelTypeFilter.value,
      pageNo: requestedPageNo,
      pageSize
    })
    if (sequence !== requestSequence) return
    if (!response.success) {
      listError.value = response.message || '公共技能加载失败'
      return
    }

    const lastPage = Math.max(1, Math.ceil(response.data.total / pageSize))
    if (requestedPageNo > lastPage) {
      pageNo.value = lastPage
      await loadPublicSkills()
      return
    }

    skillList.value = response.data.list
    total.value = response.data.total
    selectedSkills.value = []
    tableRef.value?.clearSelection()
  } catch (error) {
    if (sequence === requestSequence) {
      listError.value = getErrorMessage(error, '公共技能加载失败，请检查后端服务')
    }
  } finally {
    if (sequence === requestSequence) listLoading.value = false
  }
}

const handleSelectionChange = (rows: PublicSkill[]) => {
  selectedSkills.value = rows
}

const loadPublicSubSkillOptions = async () => {
  const response = await getPublicSubSkillOptions()
  if (response.success) publicSubSkillOptions.value = response.data.list
}

const handleSkillLevelTypeChange = (value: string | number | boolean | undefined) => {
  if (Number(value) === 2) createForm.subSkillIds = []
}

const openCreateDialog = () => {
  editingSkillId.value = null
  Object.assign(createForm, defaultCreateForm())
  createDialogVisible.value = true
  loadPublicSubSkillOptions()
  createFormRef.value?.clearValidate()
}

const openEditDialog = (skill: PublicSkill) => {
  editingSkillId.value = skill.id
  Object.assign(createForm, {
    skillName: skill.skillName,
    skillDescription: skill.skillDescription || '',
    skillLevelType: skill.skillLevelType,
    subSkillIds: [...skill.subSkillIds],
    ruleContent: skill.ruleContent,
    enabled: skill.enabled
  })
  createDialogVisible.value = true
  loadPublicSubSkillOptions()
  createFormRef.value?.clearValidate()
}

const resetCreateForm = () => {
  editingSkillId.value = null
  Object.assign(createForm, defaultCreateForm())
  createFormRef.value?.clearValidate()
}

const submitSkill = async () => {
  if (!skillMcpReady.value) return ElMessage.warning('请等待 MCP 配置加载成功')
  if (!createFormRef.value) return
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const formData: PublicSkillCreate = {
      mcpBindings: skillMcpRef.value!.getBindings(),
      skillName: createForm.skillName.trim(),
      skillDescription: createForm.skillDescription.trim(),
      skillLevelType: createForm.skillLevelType,
      subSkillIds: [...createForm.subSkillIds],
      ruleContent: createForm.ruleContent.trim(),
      enabled: createForm.enabled
    }
    const response = isEditing.value
      ? await updatePublicSkill({ id: editingSkillId.value!, ...formData })
      : await createPublicSkill(formData)
    if (!response.success) {
      ElMessage.warning(response.message || `公共技能${isEditing.value ? '修改' : '新增'}失败`)
      return
    }
    ElMessage.success(response.message || `公共技能${isEditing.value ? '修改' : '新增'}成功`)
    const wasEditing = isEditing.value
    createDialogVisible.value = false
    if (!wasEditing) pageNo.value = 1
    await loadPublicSkills()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, `公共技能${isEditing.value ? '修改' : '新增'}失败`))
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (skill: PublicSkill) => {
  try {
    await ElMessageBox.confirm(`确定删除公共技能“${skill.skillName}”吗？`, '删除公共技能', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  deletingSkillId.value = skill.id
  try {
    const response = await deletePublicSkill({ id: skill.id })
    if (!response.success) {
      ElMessage.warning(response.message || '公共技能删除失败')
      return
    }
    ElMessage.success(response.message || '公共技能删除成功')
    await loadPublicSkills()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '公共技能删除失败'))
  } finally {
    deletingSkillId.value = null
  }
}

const confirmBatchDelete = async () => {
  if (!selectedSkills.value.length) return
  const selectedCount = selectedSkills.value.length
  try {
    await ElMessageBox.confirm(`确定删除已选择的 ${selectedCount} 条公共技能吗？`, '批量删除公共技能', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  batchDeleting.value = true
  try {
    const response = await batchDeletePublicSkills({
      ids: selectedSkills.value.map((skill) => skill.id)
    })
    if (!response.success) {
      ElMessage.warning(response.message || '公共技能批量删除失败')
      return
    }
    ElMessage.success(response.message || `已删除 ${selectedCount} 条公共技能`)
    await loadPublicSkills()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '公共技能批量删除失败'))
  } finally {
    batchDeleting.value = false
  }
}

watch(keyword, () => {
  requestSequence += 1
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    pageNo.value = 1
    loadPublicSkills()
  }, 300)
})

watch(enabledFilter, () => {
  requestSequence += 1
  pageNo.value = 1
  loadPublicSkills()
})

watch(skillLevelTypeFilter, () => {
  requestSequence += 1
  pageNo.value = 1
  loadPublicSkills()
})

onMounted(loadPublicSkills)
</script>

<style scoped lang="scss">
.public-skill-page {
  height: calc(100vh - 60px);
  padding: 24px;
  box-sizing: border-box;
  background: var(--bg-dark, #f5f7fa);
}

.public-skill-card {
  height: 100%;
  border: 0;
  border-radius: 14px;

  :deep(.el-card__body) {
    height: calc(100% - 72px);
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
  }
}

.page-header,
.toolbar,
.toolbar-actions {
  display: flex;
  align-items: center;
}

.page-header {
  justify-content: space-between;

  h2 {
    margin: 0;
    color: #1f2937;
    font-size: 22px;
  }
}

.toolbar {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.toolbar-actions {
  gap: 12px;
}

.skill-search {
  width: 320px;

  :deep(.el-input__wrapper) {
    border-radius: 20px;
    background: #f5f7fa;
  }
}

.status-filter {
  width: 130px;
}

.sub-skill-select {
  width: 100%;
}

.list-alert {
  margin-bottom: 16px;
}

.table-area {
  flex: 1;
  min-height: 0;
}

.skill-table {
  width: 100%;
}

.pagination-area {
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
  padding-top: 16px;
}

@media (max-width: 900px) {
  .public-skill-page {
    height: auto;
    min-height: calc(100vh - 60px);
    padding: 16px;
  }

  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-actions {
    justify-content: space-between;
  }

  .skill-search,
  .status-filter {
    width: 100%;
  }
}

@media (max-width: 560px) {
  .page-header,
  .toolbar-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .page-header {
    gap: 14px;
  }
}
</style>
