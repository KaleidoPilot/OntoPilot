<template>
  <div class="organization-page">
    <el-card class="organization-card" shadow="never">
      <template #header>
        <div class="page-header">
          <div>
            <h1>公司管理</h1>
            <p>{{ isEnterpriseAdmin ? '维护所属公司的信息。' : '先进入一家公司，再维护该公司的项目组、系统配置、知识库、用户和技能。' }}</p>
          </div>
          <el-button v-if="!isEnterpriseAdmin" type="primary" :icon="Plus" @click="openCreateDialog">新增公司</el-button>
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
        <template #default><el-button link type="primary" @click="loadRows">重新加载</el-button></template>
      </el-alert>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          clearable
          placeholder="搜索公司编码或公司名称"
          aria-label="搜索公司编码或公司名称"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="enabled" clearable placeholder="全部状态" aria-label="按公司状态筛选">
          <el-option label="已启用" :value="1" />
          <el-option label="已停用" :value="0" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" row-key="id">
        <el-table-column prop="orgCode" label="公司编码" min-width="150" />
        <el-table-column prop="name" label="公司名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="remarks" label="备注" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remarks || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'info'">
              {{ row.enabled === 1 ? '已启用' : '已停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="isSuperAdmin ? 350 : 250" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="row.enabled !== 1" :icon="ArrowRight" @click="enterOrganization(row)">
              进入公司
            </el-button>
            <el-button v-if="isSuperAdmin" link type="primary" @click="openAdministratorManager(row)">管理员管理</el-button>
            <el-button link type="primary" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" :icon="Delete" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="loading ? '正在加载' : '暂无公司'">
            <el-button v-if="!loading && !isEnterpriseAdmin" type="primary" :icon="Plus" @click="openCreateDialog">创建第一家公司</el-button>
          </el-empty>
        </template>
      </el-table>

      <div v-if="total > 0" class="pagination-wrap">
        <el-pagination
          v-model:current-page="pageNo"
          v-model:page-size="pageSize"
          background
          layout="total, prev, pager, next, jumper"
          :total="total"
          @current-change="loadRows"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑公司' : '新增公司'" width="560px" destroy-on-close @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" status-icon>
        <el-form-item label="公司编码" prop="orgCode">
          <el-input v-model="form.orgCode" maxlength="64" clearable placeholder="例如：FIJO-SH" />
        </el-form-item>
        <el-form-item label="公司名称" prop="name">
          <el-input v-model="form.name" maxlength="255" clearable placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="4" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="状态" prop="enabled">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <CompanyAdministratorManager v-if="isSuperAdmin" v-model="administratorDrawer" :company="administratorCompany" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Delete, Edit, Plus, Search } from '@element-plus/icons-vue'
import { readStoredPlatformUser, getCurrentPlatformUser } from '@/api/user'
import CompanyAdministratorManager from '@/views/user/company-administrator-manager.vue'
import {
  createOrganization,
  deleteOrganization,
  queryOrganizations,
  updateOrganization,
  type Organization,
  type OrganizationSaveParams
} from '@/api/organization'

const router = useRouter()
const currentUser = ref(readStoredPlatformUser())
const isEnterpriseAdmin = computed(() => currentUser.value.deptLevel === 1)
const isSuperAdmin = computed(() => currentUser.value.userType === 'internal' && currentUser.value.deptLevel === 0)
const administratorCompany = ref<Organization>()
const administratorDrawer = ref(false)
const openAdministratorManager = (row: Organization) => {
  if (!isSuperAdmin.value) return
  administratorCompany.value = {...row}
  administratorDrawer.value = true
}
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const keyword = ref('')
const enabled = ref<'' | 0 | 1>('')
const pageNo = ref(1)
const pageSize = ref(10)
const total = ref(0)
const rows = ref<Organization[]>([])
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()

const emptyForm = (): OrganizationSaveParams & { id?: number } => ({
  orgCode: '',
  name: '',
  remarks: '',
  enabled: 1
})
const form = reactive(emptyForm())
const rules: FormRules = {
  orgCode: [
    { required: true, message: '请输入公司编码', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$/, message: '只能使用字母、数字、横线和下划线', trigger: 'blur' }
  ],
  name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }]
}

const loadRows = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const identity = await getCurrentPlatformUser()
    if (!identity.success) throw new Error(identity.message || '读取登录权限失败')
    const refreshedUser = {...readStoredPlatformUser(), ...identity.data}
    localStorage.setItem('userInfo', JSON.stringify(refreshedUser))
    currentUser.value = refreshedUser
    const response = await queryOrganizations({
      keyword: keyword.value.trim() || undefined,
      enabled: enabled.value === '' ? undefined : enabled.value,
      pageNo: pageNo.value,
      pageSize: pageSize.value
    })
    if (!response.success) throw new Error(response.message || '公司查询失败')
    rows.value = response.data.list
    total.value = response.data.total
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '公司查询失败'
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageNo.value = 1
  loadRows()
}

const handleReset = () => {
  keyword.value = ''
  enabled.value = ''
  pageNo.value = 1
  loadRows()
}

const resetForm = () => {
  Object.assign(form, emptyForm())
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  if (isEnterpriseAdmin.value) return
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (row: Organization) => {
  Object.assign(form, {
    id: row.id,
    orgCode: row.orgCode,
    name: row.name,
    remarks: row.remarks || '',
    enabled: row.enabled
  })
  dialogVisible.value = true
}

const submit = async () => {
  if (!formRef.value || !(await formRef.value.validate().catch(() => false))) return
  submitting.value = true
  try {
    const payload = {
      orgCode: form.orgCode.trim().toUpperCase(),
      name: form.name.trim(),
      remarks: form.remarks?.trim(),
      enabled: form.enabled
    }
    const response = form.id
      ? await updateOrganization({ id: form.id, ...payload })
      : await createOrganization(payload)
    if (!response.success) throw new Error(response.message || '公司保存失败')
    if (form.id) {
      try {
        const current = JSON.parse(localStorage.getItem('currentOrganization') || '{}')
        if (Number(current.id) === form.id) {
          localStorage.setItem('currentOrganization', JSON.stringify({
            id: form.id,
            orgCode: payload.orgCode,
            name: payload.name
          }))
          if (isEnterpriseAdmin.value) {
            const user = readStoredPlatformUser()
            localStorage.setItem('userInfo', JSON.stringify({ ...user, orgCode: payload.orgCode, orgName: payload.name }))
          }
          window.dispatchEvent(new Event('organization-changed'))
        }
      } catch {}
    }
    ElMessage.success(form.id ? '公司修改成功' : '公司新增成功')
    dialogVisible.value = false
    await loadRows()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '公司保存失败')
  } finally {
    submitting.value = false
  }
}

const enterOrganization = async (row: Organization) => {
  if (row.enabled !== 1) return
  localStorage.setItem('currentOrganization', JSON.stringify({ id: row.id, orgCode: row.orgCode, name: row.name }))
  window.dispatchEvent(new Event('organization-changed'))
  await router.push('/system/config')
}

const confirmDelete = async (row: Organization) => {
  try {
    await ElMessageBox.confirm(`确定物理删除公司“${row.name}”吗？有关联数据时系统会阻止删除。`, '删除公司', { type: 'warning' })
    const response = await deleteOrganization(row.id)
    if (!response.success) throw new Error(response.message || '公司删除失败')
    ElMessage.success('公司删除成功')
    await loadRows()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error instanceof Error ? error.message : '公司删除失败')
  }
}

watch(enabled, () => {
  pageNo.value = 1
})

onMounted(loadRows)
</script>

<style scoped lang="scss">
.organization-page { min-height: 100%; padding: 24px; background: var(--bg-dark); }
.organization-card { min-height: calc(100vh - 108px); border: none; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.page-header h1 { margin: 0; color: #303133; font-size: 22px; }
.page-header p { margin: 6px 0 0; color: #909399; font-size: 14px; }
.error-alert { margin-bottom: 20px; }
.toolbar { display: grid; grid-template-columns: minmax(240px, 380px) 150px auto auto; gap: 12px; margin-bottom: 20px; }
.pagination-wrap { display: flex; justify-content: flex-end; padding-top: 20px; }
@media (max-width: 768px) {
  .organization-page { padding: 12px; }
  .page-header { align-items: stretch; flex-direction: column; }
  .toolbar { grid-template-columns: 1fr; }
  .pagination-wrap { overflow-x: auto; justify-content: flex-start; }
  :deep(.el-dialog) { width: calc(100% - 24px) !important; }
}
</style>
