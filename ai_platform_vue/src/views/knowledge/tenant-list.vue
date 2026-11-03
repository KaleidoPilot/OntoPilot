<template>
  <div class="knowledge-page">
    <el-card class="knowledge-card" shadow="never">
      <template #header>
        <div class="page-header">
          <div>
            <h2>知识库管理</h2>
          </div>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增知识库</el-button>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          class="tenant-search"
          clearable
          :prefix-icon="Search"
          placeholder="搜索知识库名称或备注"
          aria-label="搜索知识库"
        />
        <el-select
          v-model="enabledFilter"
          class="status-filter"
          clearable
          placeholder="全部状态"
          aria-label="按状态筛选知识库"
        >
          <el-option label="已启用" :value="1" />
          <el-option label="已停用" :value="0" />
        </el-select>
      </div>

      <el-alert v-if="listError" class="list-alert" :title="listError" type="error" show-icon :closable="false" />

      <div class="table-area">
        <el-table v-loading="listLoading" :data="tenantList" row-key="id" size="large">
          <el-table-column label="编号" width="110" align="center">
            <template #default="{ row }">#{{ row.id }}</template>
          </el-table-column>
          <el-table-column label="知识库" min-width="220">
            <template #default="{ row }">
              <el-button link type="primary" class="tenant-link" @click="openTenant(row)">
                {{ row.tenantName }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">{{ row.remarks || '—' }}</template>
          </el-table-column>
          <el-table-column label="类型" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="row.scopeType === 2 ? 'warning' : 'success'" effect="light">
                {{ row.scopeType === 2 ? '公司私有' : '公司公有' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="数据量" width="120" align="center">
            <template #default="{ row }">{{ row.knowledgeCount }} 条</template>
          </el-table-column>
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.enabled === 1 ? 'success' : 'info'" effect="light">
                {{ row.enabled === 1 ? '已启用' : '已停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" align="center" fixed="right">
            <template #default="{ row }">
              <div class="action-buttons">
                <el-button link type="primary" @click="openTenant(row)">查看数据</el-button>
                <el-button link type="primary" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
                <el-button link type="danger" :icon="Delete" :loading="deletingId === row.id" @click="confirmDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="keyword.trim() || enabledFilter !== '' ? '没有符合条件的知识库' : '暂无知识库'" :image-size="92" />
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
          @current-change="loadTenants"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新增知识库' : `编辑知识库 #${editingId}`"
      width="520px"
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px" status-icon>
        <el-form-item label="知识库名称" prop="tenantName">
          <el-input v-model="form.tenantName" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="区分备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="类型" prop="scopeType">
          <el-radio-group v-model="form.scopeType">
            <el-radio :value="1">公司公有</el-radio>
            <el-radio :value="2">公司私有</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.scopeType === 2">
          <el-form-item label="授权用户">
            <el-select v-model="form.accessUserIds" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择可以使用的用户" :loading="optionsLoading">
              <el-option v-for="item in grantUsers" :key="item.id" :label="`${item.realName}（${item.account}）`" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="授权用户组">
            <el-select v-model="form.accessGroupIds" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择可以使用的用户组" :loading="optionsLoading">
              <el-option v-for="item in grantGroups" :key="item.id" :label="item.groupName" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-alert v-if="optionsError" :title="optionsError" type="error" show-icon :closable="false" />
        </template>
        <el-form-item v-if="editingId !== null" label="状态" prop="enabled">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitTenant">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Delete, Edit, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  createTenant,
  deleteTenant,
  getKnowledgeGrantOptions,
  getTenantPage,
  updateTenant,
  type KnowledgeGrantOptions,
  type KnowledgeTenant,
  type TenantCreateParams
} from '@/api/knowledge'


const router = useRouter()
const tenantList = ref<KnowledgeTenant[]>([])
const keyword = ref('')
const enabledFilter = ref<'' | 0 | 1>('')
const pageNo = ref(1)
const pageSize = 5
const total = ref(0)
const listLoading = ref(false)
const listError = ref('')
let requestSequence = 0
let searchTimer: ReturnType<typeof setTimeout> | undefined
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const submitting = ref(false)
const deletingId = ref<number | null>(null)
const emptyForm = (): TenantCreateParams & { enabled: 0 | 1 } => ({
  tenantName: '',
  remarks: '',
  enabled: 1,
  scopeType: 1,
  accessUserIds: [],
  accessGroupIds: []
})
const form = ref(emptyForm())
const grantUsers = ref<KnowledgeGrantOptions['users']>([])
const grantGroups = ref<KnowledgeGrantOptions['groups']>([])
const optionsLoading = ref(false)
const optionsError = ref('')
const rules: FormRules = {
  tenantName: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }],
  remarks: [{ max: 500, message: '备注不能超过 500 个字符', trigger: 'blur' }],
  scopeType: [{ required: true, message: '请选择知识库类型', trigger: 'change' }]
}

const loadGrantOptions = async () => {
  if (grantUsers.value.length || grantGroups.value.length || optionsLoading.value) return
  optionsLoading.value = true
  optionsError.value = ''
  try {
    const response = await getKnowledgeGrantOptions()
    if (!response.success) {
      optionsError.value = response.message || '授权选项加载失败'
      return
    }
    grantUsers.value = response.data.users
    grantGroups.value = response.data.groups
  } catch (error) {
    optionsError.value = error instanceof Error ? error.message : '授权选项加载失败'
  } finally {
    optionsLoading.value = false
  }
}

const loadTenants = async () => {
  const sequence = ++requestSequence
  listLoading.value = true
  listError.value = ''
  try {
    const response = await getTenantPage({
      keyword: keyword.value.trim() || undefined,
      enabled: enabledFilter.value === '' ? undefined : enabledFilter.value,
      pageNo: pageNo.value,
      pageSize
    })
    if (sequence !== requestSequence) return
    if (!response.success) {
      listError.value = response.message || '知识库加载失败'
      return
    }
    tenantList.value = response.data.list
    total.value = response.data.total
  } catch (error) {
    if (sequence === requestSequence) {
      listError.value = error instanceof Error ? error.message : '知识库加载失败'
    }
  } finally {
    if (sequence === requestSequence) listLoading.value = false
  }
}

const openTenant = (tenant: KnowledgeTenant) => {
  router.push(`/knowledge/${tenant.id}`)
}

const openCreateDialog = () => {
  editingId.value = null
  form.value = emptyForm()
  void loadGrantOptions()
  dialogVisible.value = true
}

const openEditDialog = (tenant: KnowledgeTenant) => {
  editingId.value = tenant.id
  form.value = {
    tenantName: tenant.tenantName,
    remarks: tenant.remarks || '',
    enabled: tenant.enabled,
    scopeType: tenant.scopeType === 2 ? 2 : 1,
    accessUserIds: [...(tenant.accessUserIds || [])],
    accessGroupIds: [...(tenant.accessGroupIds || [])]
  }
  void loadGrantOptions()
  dialogVisible.value = true
}

const resetForm = () => {
  editingId.value = null
  form.value = emptyForm()
  formRef.value?.clearValidate()
}

const submitTenant = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (form.value.scopeType === 2 && !form.value.accessUserIds.length && !form.value.accessGroupIds.length) {
    ElMessage.warning('公司私有知识库至少选择一位用户或一个用户组')
    return
  }
  if (form.value.scopeType === 2 && optionsError.value) {
    ElMessage.warning('授权选项加载失败，请关闭后重试')
    return
  }
  submitting.value = true
  try {
    const payload = {
      tenantName: form.value.tenantName.trim(),
      remarks: form.value.remarks.trim(),
      scopeType: form.value.scopeType,
      accessUserIds: form.value.scopeType === 2 ? form.value.accessUserIds : [],
      accessGroupIds: form.value.scopeType === 2 ? form.value.accessGroupIds : []
    }
    const response = editingId.value === null
      ? await createTenant(payload)
      : await updateTenant({ id: editingId.value, ...payload, enabled: form.value.enabled })
    if (!response.success) {
      ElMessage.warning(response.message || '知识库保存失败')
      return
    }
    ElMessage.success(response.message || '知识库保存成功')
    dialogVisible.value = false
    if (editingId.value === null) pageNo.value = 1
    await loadTenants()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '知识库保存失败')
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (tenant: KnowledgeTenant) => {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库“${tenant.tenantName}”（#${tenant.id}）吗？有知识数据时系统会拒绝删除。`,
      '删除知识库',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  deletingId.value = tenant.id
  try {
    const response = await deleteTenant(tenant.id)
    if (!response.success) {
      ElMessage.warning(response.message || '知识库删除失败')
      return
    }
    ElMessage.success(response.message || '知识库删除成功')
    await loadTenants()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '知识库删除失败')
  } finally {
    deletingId.value = null
  }
}

watch(keyword, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pageNo.value = 1
    loadTenants()
  }, 300)
})

watch(enabledFilter, () => {
  pageNo.value = 1
  loadTenants()
})

onMounted(loadTenants)
</script>

<style scoped lang="scss">
.knowledge-page { height: calc(100vh - 60px); padding: 24px; box-sizing: border-box; background: var(--bg-dark, #f5f7fa); }
.knowledge-card { height: 100%; border: 0; border-radius: 14px; }
.knowledge-card :deep(.el-card__body) { display: flex; height: calc(100% - 86px); flex-direction: column; box-sizing: border-box; }
.page-header, .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header h2 { margin: 0; color: #1f2937; font-size: 22px; }
.page-header p { margin: 6px 0 0; color: #6b7280; font-size: 13px; }
.toolbar { margin-bottom: 18px; }
.tenant-search { width: 360px; }
.tenant-search :deep(.el-input__wrapper) { border-radius: 20px; background: #f5f7fa; }
.status-filter { width: 140px; }
.el-select { width: 100%; }
.list-alert { margin-bottom: 16px; }
.table-area { min-height: 0; flex: 0 1 auto; overflow: auto; }
.tenant-link { max-width: 100%; padding: 0;  font-size: 15px; font-weight: 600; text-overflow: ellipsis; }
.action-buttons { display: flex; align-items: center; justify-content: center; gap: 12px; white-space: nowrap; }
.action-buttons :deep(.el-button + .el-button) { margin-left: 0; }
.pagination-area { display: flex; align-items: center; justify-content: flex-end; flex-shrink: 0; padding-top: 16px; }
@media (max-width: 760px) {
  .knowledge-page { height: auto; min-height: calc(100vh - 60px); padding: 14px; }
  .knowledge-card :deep(.el-card__body) { height: auto; min-height: 520px; }
  .toolbar { align-items: stretch; flex-direction: column; }
  .tenant-search, .status-filter { width: 100%; }
  .pagination-area { justify-content: center; overflow-x: auto; }
}
</style>
