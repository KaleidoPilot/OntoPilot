<template>
    <el-drawer v-model="administratorDrawer" :title="(administratorCompany?.name || '') + ' · 管理员管理'" size="min(1000px, 96vw)"
      :close-on-click-modal="!administratorSaving" :close-on-press-escape="!administratorSaving" :show-close="!administratorSaving" @closed="closeAdministratorManager">
      <el-alert v-if="administratorCompany?.enabled === 0" title="公司已停用，暂不能新增或启用管理员。" type="info" :closable="false" />
      <el-alert v-if="administratorError" :title="administratorError" type="error" show-icon :closable="false">
        <el-button link @click="loadAdministrators">重新加载</el-button>
      </el-alert>
      <div class="administrator-toolbar">
        <el-input v-model="administratorKeyword" clearable placeholder="搜索姓名或账号" aria-label="搜索公司管理员" @keyup.enter="searchAdministrators" />
        <el-select v-model="administratorEnabled" clearable placeholder="全部状态" aria-label="管理员状态筛选">
          <el-option label="已启用" :value="1" /><el-option label="已停用" :value="0" />
        </el-select>
        <el-button :disabled="administratorSaving" @click="searchAdministrators">查询</el-button>
        <el-button type="primary" :icon="Plus" :disabled="administratorSaving || administratorCompany?.enabled !== 1" @click="openAdministratorDialog()">新增管理员</el-button>
      </div>
      <el-table v-loading="administratorLoading" :data="administrators" row-key="id">
        <el-table-column prop="realName" label="姓名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="account" label="登录账号" min-width="160" show-overflow-tooltip />
        <el-table-column label="等级" width="130"><template #default><el-tag>1 级管理员</el-tag></template></el-table-column>
        <el-table-column prop="phone" label="手机号" min-width="140" show-overflow-tooltip />
        <el-table-column prop="deptName" label="部门" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="row.enabled === 1 ? 'success' : 'info'">{{ row.enabled === 1 ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="administratorSaving" @click="openAdministratorDialog(row)">编辑</el-button></template></el-table-column>
        <template #empty><el-empty :description="administratorError ? '加载失败，请重新加载' : '暂无符合条件的管理员'" /></template>
      </el-table>
      <div class="pagination-wrap"><el-pagination v-model:current-page="administratorPage" :page-size="10" :total="administratorTotal" layout="total, prev, pager, next" @current-change="loadAdministrators" /></div>
    </el-drawer>

    <el-dialog v-model="administratorDialog" :title="administratorForm.id ? '编辑公司管理员' : '新增公司管理员'" width="min(560px, 94vw)"
      :close-on-click-modal="!administratorSaving" :close-on-press-escape="!administratorSaving" :show-close="!administratorSaving" @closed="resetAdministratorForm">
      <el-form ref="administratorFormRef" :model="administratorForm" :rules="administratorRules" label-width="100px" :disabled="administratorSaving">
        <el-form-item label="所属公司"><el-input :model-value="administratorCompany?.name || ''" disabled /></el-form-item>
        <el-form-item label="管理员等级"><el-input model-value="1 级管理员" disabled /></el-form-item>
        <el-form-item label="姓名" prop="realName"><el-input v-model="administratorForm.realName" maxlength="55" /></el-form-item>
        <el-form-item label="登录账号" prop="account"><el-input v-model="administratorForm.account" maxlength="55" autocomplete="off" /></el-form-item>
        <el-form-item :label="administratorForm.id ? '新密码' : '初始密码'" prop="password" :required="!administratorForm.id">
          <el-input v-model="administratorForm.password" type="password" show-password autocomplete="new-password" :placeholder="administratorForm.id ? '留空保留原密码' : '请输入至少8字节的密码'" />
        </el-form-item>
        <el-form-item label="手机号"><el-input v-model="administratorForm.phone" maxlength="32" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="administratorForm.deptName" maxlength="100" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="administratorForm.remarks" type="textarea" :rows="3" maxlength="500" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="administratorForm.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="administratorSaving" @click="administratorDialog = false">取消</el-button><el-button type="primary" :loading="administratorSaving" @click="saveAdministrator">保存</el-button></template>
    </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { readStoredPlatformUser, queryCompanyAdministrators, createCompanyAdministrator, updateCompanyAdministrator, type CompanyAdministrator } from '@/api/user'
import type { Organization } from '@/api/organization'
const props = defineProps<{ modelValue: boolean; company?: Organization }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: boolean): void }>()
const isSuperAdmin = readStoredPlatformUser().deptLevel === 0
const administratorCompany = computed(() => props.company)
const administratorDialog = ref(false), administratorLoading = ref(false), administratorSaving = ref(false)
const administratorDrawer = computed({get: () => props.modelValue, set: value => {if (!administratorSaving.value) emit('update:modelValue', value)}})
const administratorError = ref(''), administratorKeyword = ref(''), administratorEnabled = ref<''|0|1>('')
const administratorPage = ref(1), administratorTotal = ref(0), administrators = ref<CompanyAdministrator[]>([])
const administratorFormRef = ref<FormInstance>()
const emptyAdministratorForm = () => ({id:0,orgId:0,realName:'',account:'',password:'',phone:'',deptName:'',remarks:'',enabled:1 as 0|1})
const administratorForm = reactive(emptyAdministratorForm())
let administratorVersion = 0
const administratorRules: FormRules = {
  realName: [{required:true,message:'请输入姓名',trigger:'blur'}, {validator:(_rule,value,callback)=>callback(String(value).trim() ? undefined : new Error('姓名不能为空')),trigger:'blur'}],
  account: [{required:true,message:'请输入登录账号',trigger:'blur'}, {validator:(_rule,value,callback)=>callback(String(value).trim() ? undefined : new Error('账号不能为空')),trigger:'blur'}],
  password: [{validator:(_rule,value,callback)=>{
    const raw = String(value || '')
    if (!raw && administratorForm.id) return callback()
    const length = new TextEncoder().encode(raw).length
    callback(raw.trim() && length >= 8 && length <= 72 ? undefined : new Error('密码长度必须为8至72字节'))
  },trigger:'blur'}]
}

const loadAdministrators = async () => {
  if (!administratorCompany.value || !administratorDrawer.value) return
  const version = ++administratorVersion, orgId = administratorCompany.value.id
  administratorLoading.value = true; administratorError.value = ''
  try {
    const res = await queryCompanyAdministrators({orgId,keyword:administratorKeyword.value.trim(),enabled:administratorEnabled.value === '' ? undefined : administratorEnabled.value,pageNo:administratorPage.value,pageSize:10})
    if (version !== administratorVersion || !administratorDrawer.value) return
    if (!res.success) throw new Error(res.message || '管理员加载失败')
    administrators.value = res.data.list; administratorTotal.value = res.data.total
    if (!res.data.list.length && administratorPage.value > 1) {
      administratorPage.value = Math.max(1,Math.ceil(res.data.total / 10))
    }
  } catch(error) {
    if(version === administratorVersion) {administratorError.value = error instanceof Error ? error.message : '管理员加载失败';administrators.value=[];administratorTotal.value=0}
  } finally {if(version === administratorVersion)administratorLoading.value=false}
}
const searchAdministrators = () => {
  if (administratorPage.value !== 1) administratorPage.value = 1
  else void loadAdministrators()
}
const resetAdministratorForm = () => {Object.assign(administratorForm,emptyAdministratorForm());administratorFormRef.value?.clearValidate()}
const closeAdministratorManager = () => {if(props.modelValue)return;administratorVersion++;administratorDialog.value=false;resetAdministratorForm()}
const openAdministratorDialog = (row?:CompanyAdministrator) => {
  if (!isSuperAdmin || !administratorCompany.value || administratorSaving.value) return
  if (row && row.orgId !== administratorCompany.value.id) return
  Object.assign(administratorForm, row ? {id:row.id,orgId:row.orgId,realName:row.realName,account:row.account,password:'',phone:row.phone||'',deptName:row.deptName||'',remarks:row.remarks||'',enabled:row.enabled} : {...emptyAdministratorForm(),orgId:administratorCompany.value.id})
  administratorDialog.value=true
}
const saveAdministrator = async () => {
  if (administratorSaving.value || !administratorCompany.value || administratorForm.orgId !== administratorCompany.value.id) return
  if (!administratorFormRef.value || !(await administratorFormRef.value.validate().catch(()=>false))) return
  administratorSaving.value=true
  try {
    const common={orgId:administratorForm.orgId,realName:administratorForm.realName.trim(),account:administratorForm.account.trim(),phone:administratorForm.phone.trim(),deptName:administratorForm.deptName.trim(),remarks:administratorForm.remarks.trim(),enabled:administratorForm.enabled}
    const res = administratorForm.id
      ? await updateCompanyAdministrator({...common,id:administratorForm.id,...(administratorForm.password ? {password:administratorForm.password} : {})})
      : await createCompanyAdministrator({...common,password:administratorForm.password})
    if (!res.success) throw new Error(res.message || '管理员保存失败')
    ElMessage.success(res.message || '保存成功');administratorDialog.value=false;administratorForm.password=''
    await loadAdministrators()
  } catch(error) {ElMessage.error(error instanceof Error ? error.message : '管理员保存失败')}
  finally {administratorSaving.value=false}
}
watch(() => [props.modelValue, props.company?.id], () => {
  administratorVersion++; administrators.value=[]; administratorTotal.value=0; administratorLoading.value=false
  administratorDialog.value=false; administratorKeyword.value=''; administratorEnabled.value=''; administratorPage.value=1
  resetAdministratorForm()
  if (props.modelValue && props.company) void loadAdministrators()
}, {immediate:true})
</script>

<style scoped lang="scss">
.administrator-toolbar{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}.administrator-toolbar .el-input{width:240px}.administrator-toolbar .el-select{width:160px}.pagination-wrap{display:flex;justify-content:flex-end;padding-top:20px}
@media(max-width:760px){.administrator-toolbar{flex-direction:column}.administrator-toolbar .el-input,.administrator-toolbar .el-select{width:100%}.pagination-wrap{overflow-x:auto}}
</style>

