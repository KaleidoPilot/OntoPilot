<template>
  <div class="management-page">
    <el-card shadow="never" class="management-card">
      <template #header>
        <div class="page-header">
          <h2>{{ enterpriseMode ? '企业后台用户管理' : activeGroup ? activeGroup.groupName + ' · 用户管理' : '用户组管理' }}</h2>
          <el-button v-if="activeGroup" :disabled="saving" @click="backToGroups">返回用户组</el-button>
        </div>
      </template>

        <template v-if="!activeGroup && !enterpriseMode">
          <el-alert v-if="groupError" :title="groupError" type="error" show-icon :closable="false"><template #default><el-button link @click="loadGroups">重新加载</el-button></template></el-alert>
          <div class="toolbar">
            <el-input v-model="groupFilters.keyword" clearable :prefix-icon="Search" placeholder="搜索用户组或智能体" aria-label="搜索用户组" />
            <el-select v-model="groupFilters.enabled" clearable placeholder="全部状态">
              <el-option label="已启用" :value="1" />
              <el-option label="已停用" :value="0" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="openGroupDialog()">新增用户组</el-button>
          </div>
          <el-table v-loading="groupLoading" :data="groups" row-key="id">
            <el-table-column label="用户组" min-width="180"><template #default="{ row }"><el-button link type="primary" :aria-label="'进入用户组 ' + row.groupName" @click="enterGroup(row)">{{ row.groupName }}</el-button></template></el-table-column>
            <el-table-column prop="agentName" label="智能体" min-width="180" show-overflow-tooltip />
            <el-table-column prop="agentKey" label="Agent Key" min-width="190" show-overflow-tooltip />
            <el-table-column prop="userCount" label="用户数" width="100" align="center" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="240" align="center">
              <template #default="{ row }">
                <el-button link type="primary" @click="enterGroup(row)">进入用户组</el-button>
                <el-button link type="primary" :icon="Edit" @click="openGroupDialog(row)">编辑</el-button>
                <el-button link type="danger" :icon="Delete" @click="removeGroup(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="groupError ? '加载失败，请重新加载' : '暂无用户组'" /></template>
          </el-table>
          <div class="pagination"><el-pagination v-model:current-page="groupPage" :page-size="10" :total="groupTotal" layout="total, prev, pager, next" /></div>
        </template>

        <template v-else>
          <el-alert v-if="activeGroup && !activeGroup.enabled" title="用户组已停用，请先返回用户组列表启用后再新增或编辑用户。" type="info" :closable="false" />
          <el-alert v-if="userError" :title="userError" type="error" show-icon :closable="false"><template #default><el-button link @click="loadUsers">重新加载</el-button></template></el-alert>
          <el-alert v-if="enterpriseMode && groupOptionsError" :title="groupOptionsError" type="error" :closable="false"><el-button link @click="loadGroupOptions">重新加载用户组</el-button></el-alert>
          <div class="toolbar">
            <el-input v-model="userFilters.keyword" clearable :prefix-icon="Search" placeholder="搜索用户名或登录账号" aria-label="搜索用户" />
            <el-select v-if="enterpriseMode" v-model="userFilters.groupId" filterable clearable placeholder="全部用户组" aria-label="按用户组筛选" :loading="groupOptionsLoading">
              <el-option v-for="group in groupOptions" :key="group.id" :label="group.groupName + (group.enabled ? '' : '（已停用）')" :value="group.id" />
            </el-select>
            <el-select v-model="userFilters.enabled" clearable placeholder="全部状态">
              <el-option label="已启用" :value="1" />
              <el-option label="已停用" :value="0" />
            </el-select>
            <el-button type="danger" plain :icon="Delete" :disabled="saving || userLoading || !selectedUsers.length" @click="removeSelectedUsers">批量删除</el-button>
            <el-button type="primary" :icon="Plus" :disabled="saving || (enterpriseMode ? groupOptionsLoading || !!groupOptionsError : !activeGroup?.enabled)" @click="openUserDialog()">新增用户</el-button>
          </div>
          <el-table v-loading="userLoading" :data="users" row-key="id" @selection-change="selectedUsers = $event">
            <el-table-column type="selection" width="50" />
            <el-table-column prop="realName" label="用户名" min-width="130" />
            <el-table-column prop="account" label="登录账号" min-width="150" />
            <el-table-column v-if="enterpriseMode" prop="groupName" label="所属用户组" min-width="160" show-overflow-tooltip />
            <el-table-column prop="agentName" label="智能体" min-width="160" />
            <el-table-column prop="phone" label="手机号" min-width="130" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="230" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :icon="Edit" :disabled="saving || (!enterpriseMode && !activeGroup?.enabled)" @click="openUserDialog(row)">编辑</el-button>
                <el-button link type="warning" :disabled="saving" @click="openResetDialog(row)">重置密码</el-button>
                <el-button link type="danger" :icon="Delete" :disabled="saving" @click="removeUsers([row.id])">删除</el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="userError ? '加载失败，请重新加载' : enterpriseMode ? '暂无符合条件的公司用户' : '当前用户组暂无用户'" /></template>
          </el-table>
          <div class="pagination"><el-pagination v-model:current-page="userPage" :page-size="10" :total="userTotal" layout="total, prev, pager, next" /></div>
        </template>
    </el-card>

    <el-dialog v-model="groupDialog" :title="groupForm.id ? '编辑用户组' : '新增用户组'" width="min(520px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
      <el-form class="dialog-form" label-width="110px" :disabled="saving">
        <el-form-item label="用户组名称" required><el-input v-model="groupForm.groupName" maxlength="100" /></el-form-item>
        <el-form-item label="智能体" required>
          <div v-loading="agentOptionsLoading" class="full-width agent-picker">
            <el-alert v-if="agentOptionsError" :title="agentOptionsError" type="error" :closable="false">
              <el-button link @click="loadOptions">重新加载</el-button>
            </el-alert>
            <el-scrollbar v-else-if="groupAgentOptions.length" max-height="240px">
              <el-checkbox-group v-model="groupForm.agentIds" aria-label="绑定智能体，可多选">
                <el-checkbox v-for="agent in groupAgentOptions" :key="agent.id" :value="agent.id">{{ agent.agentName }}</el-checkbox>
              </el-checkbox-group>
            </el-scrollbar>
            <el-empty v-else-if="!agentOptionsLoading" description="暂无可绑定的智能体，请先创建并启用智能体" :image-size="60" />
            <div class="agent-picker-hint">可勾选多个智能体，已选择 {{ groupForm.agentIds.length }} 个</div>
          </div>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="groupForm.remarks" type="textarea" :rows="3" maxlength="500" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="groupForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="groupDialog=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="agentOptionsLoading || !!agentOptionsError" @click="saveGroup">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="userDialog" :title="userForm.id ? '编辑用户' : '新增用户'" width="min(560px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
      <el-form class="dialog-form" label-width="110px" :disabled="saving">
        <el-form-item label="用户组" required>
          <el-select v-if="enterpriseMode" v-model="userForm.groupId" filterable placeholder="请选择用户组" aria-label="所属用户组" :loading="groupOptionsLoading" :disabled="!!groupOptionsError">
            <el-option v-for="group in groupOptions" :key="group.id" :label="group.groupName + (group.enabled ? '' : '（已停用）')" :value="group.id" :disabled="!group.enabled" />
          </el-select>
          <el-input v-else :model-value="activeGroup?.groupName || ''" disabled aria-label="当前用户组" />
        </el-form-item>
        <el-form-item label="用户名" required><el-input v-model="userForm.realName" maxlength="55" /></el-form-item>
        <el-form-item label="登录账号" required><el-input v-model="userForm.account" maxlength="55" /></el-form-item>
        <el-form-item v-if="!userForm.id" label="初始密码" required><el-input v-model="userForm.password" type="password" show-password maxlength="72" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="userForm.phone" maxlength="32" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="userForm.remarks" type="textarea" :rows="3" maxlength="500" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="userForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="userDialog=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="enterpriseMode && (groupOptionsLoading || !!groupOptionsError)" @click="saveUser">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="resetDialog" title="重置密码" width="min(440px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
      <el-form label-width="90px" :disabled="saving"><el-form-item label="新密码" required><el-input v-model="resetPassword" type="password" show-password maxlength="72" /></el-form-item></el-form>
      <template #footer><el-button :disabled="saving" @click="resetDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveResetPassword">确认重置</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { Delete, Edit, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import {
  batchDeleteExternalUsers, createExternalUser, createUserGroup, deleteExternalUser,
  deleteUserGroup, getAgentOptions, getExternalUserPage, getUserGroupOptions,
  getUserGroupPage, resetExternalUserPassword, updateExternalUser, updateUserGroup,
  type ExternalUser, type UserGroup
} from '@/api/user'

const route = useRoute()
const enterpriseMode = computed(() => route.path === '/user/enterprise')
const groupOptions = ref<Array<{id:number;groupName:string;enabled:0|1}>>([])
const groupOptionsLoading = ref(false), groupOptionsError = ref('')
const activeGroup = ref<UserGroup>()
const groups = ref<UserGroup[]>([])
const users = ref<ExternalUser[]>([])
const agentOptions = ref<Array<{id:number;agentName:string;agentKey:string}>>([])
const agentOptionsLoading = ref(false), agentOptionsError = ref('')
const groupLoading = ref(false), userLoading = ref(false), saving = ref(false)
const groupError = ref(''), userError = ref('')
const groupPage = ref(1), userPage = ref(1), groupTotal = ref(0), userTotal = ref(0)
const selectedUsers = ref<ExternalUser[]>([])
const groupFilters = reactive<{keyword:string;enabled:''|0|1}>({keyword:'',enabled:''})
const userFilters = reactive<{keyword:string;enabled:''|0|1;groupId:''|number}>({keyword:'',enabled:'',groupId:''})
const groupDialog = ref(false), userDialog = ref(false), resetDialog = ref(false)
const resetUserId = ref(0), resetPassword = ref('')
const groupForm = reactive<{id:number;groupName:string;agentIds:number[];remarks:string;enabled:0|1}>({id:0,groupName:'',agentIds:[],remarks:'',enabled:1})
const groupAgentOptions = computed(() => [
  ...agentOptions.value,
  ...groupForm.agentIds.filter(id => !agentOptions.value.some(agent => agent.id === id)).map(id => ({id,agentName:`智能体 ${id}（已停用或不可用，请取消勾选）`}))
])
const userForm = reactive<{id:number;groupId:number|null;realName:string;account:string;password:string;phone:string;remarks:string;enabled:0|1}>({id:0,groupId:null,realName:'',account:'',password:'',phone:'',remarks:'',enabled:1})
let groupTimer: ReturnType<typeof setTimeout> | undefined, userTimer: ReturnType<typeof setTimeout> | undefined
let groupVersion = 0, userVersion = 0

const notifyFailure = (message?: string) => ElMessage.error(message || '操作失败')
const errorMessage = (cause: unknown) => cause instanceof Error ? cause.message : '操作失败，请重试'
const loadGroupOptions = async () => {
  groupOptionsLoading.value = true; groupOptionsError.value = ''
  try {
    const res = await getUserGroupOptions(true)
    if (!res.success) throw new Error(res.message || '用户组加载失败')
    groupOptions.value = res.data.list
  } catch (cause) { groupOptions.value = []; groupOptionsError.value = errorMessage(cause) }
  finally { groupOptionsLoading.value = false }
}
const loadOptions = async () => {
  if (agentOptionsLoading.value) return
  agentOptionsLoading.value = true; agentOptionsError.value = ''
  try {
    const agentsRes = await getAgentOptions()
    if (!agentsRes.success) throw new Error(agentsRes.message || '智能体选项加载失败')
    agentOptions.value = agentsRes.data.list
  } catch (cause) { agentOptionsError.value = errorMessage(cause) }
  finally { agentOptionsLoading.value = false }
}
const loadGroups = async () => {
  const attempt = ++groupVersion
  groupLoading.value=true; groupError.value=''
  try {
    const res=await getUserGroupPage({keyword:groupFilters.keyword||undefined,enabled:groupFilters.enabled===''?undefined:groupFilters.enabled,pageNo:groupPage.value,pageSize:10})
    if (attempt !== groupVersion) return
    if (!res.success) throw new Error(res.message || '用户组加载失败')
    groups.value=res.data.list; groupTotal.value=res.data.total
    const current = groups.value.find(group => group.id === activeGroup.value?.id)
    if (current) activeGroup.value = {...current}
    if (!groups.value.length && groupPage.value > 1) groupPage.value = Math.max(1, Math.ceil(groupTotal.value / 10))
  } catch (cause) { if (attempt === groupVersion) { groupError.value=errorMessage(cause); groups.value=[]; groupTotal.value=0 } }
  finally { if (attempt === groupVersion) groupLoading.value=false }
}
const loadUsers = async () => {
  const attempt = ++userVersion, groupId = enterpriseMode.value ? userFilters.groupId || undefined : activeGroup.value?.id
  users.value=[]; selectedUsers.value=[]; userError.value=''
  if (!enterpriseMode.value && !groupId) { userLoading.value=false; userTotal.value=0; return }
  userLoading.value=true
  try {
    const res=await getExternalUserPage({keyword:userFilters.keyword||undefined,groupId,enabled:userFilters.enabled===''?undefined:userFilters.enabled,pageNo:userPage.value,pageSize:10})
    if (attempt !== userVersion) return
    if (!res.success) throw new Error(res.message || '用户加载失败')
    users.value=res.data.list; userTotal.value=res.data.total
    if (!users.value.length && userPage.value > 1) userPage.value = Math.max(1, Math.ceil(userTotal.value / 10))
  } catch (cause) { if (attempt === userVersion) { userError.value=errorMessage(cause); userTotal.value=0 } }
  finally { if (attempt === userVersion) userLoading.value=false }
}
const enterGroup = (group: UserGroup) => {
  activeGroup.value={...group}; userVersion++; users.value=[]; selectedUsers.value=[]; userTotal.value=0
  userFilters.keyword=''; userFilters.enabled=''; clearTimeout(userTimer)
  const changedPage = userPage.value !== 1; userPage.value=1
  if (!changedPage) void loadUsers()
}
const backToGroups = () => {
  if (saving.value) return
  activeGroup.value=undefined; userVersion++; clearTimeout(userTimer)
  users.value=[]; selectedUsers.value=[]; userTotal.value=0; userLoading.value=false; userError.value=''
  userDialog.value=false; resetDialog.value=false
  void loadGroups()
}
const openGroupDialog=(row?:UserGroup)=>{Object.assign(groupForm,row?{id:row.id,groupName:row.groupName,agentIds:[...new Set(String(row.agentId).split(',').map(Number).filter(id=>Number.isInteger(id)&&id>0))],remarks:row.remarks||'',enabled:row.enabled}:{id:0,groupName:'',agentIds:[],remarks:'',enabled:1});groupDialog.value=true;void loadOptions()}
const saveGroup=async()=>{
  if (saving.value) return
  if(agentOptionsLoading.value || agentOptionsError.value)return
  if(!groupForm.groupName.trim()||!groupForm.agentIds.length)return ElMessage.warning('请填写用户组名称并至少勾选一个智能体')
  if(groupForm.agentIds.length>100)return ElMessage.warning('最多选择100个智能体')
  const agentId=groupForm.agentIds.join(',')
  const commonData={groupName:groupForm.groupName,agentId,remarks:groupForm.remarks,enabled:groupForm.enabled}
  saving.value=true
  try{
    const groupCreateData={...commonData}
    const groupUpdateData={...commonData,id:groupForm.id}
    const res=groupForm.id?await updateUserGroup(groupUpdateData):await createUserGroup(groupCreateData)
    if(res.success){ElMessage.success(res.message||'保存成功');groupDialog.value=false;await Promise.all([loadGroups(),loadOptions()])}else notifyFailure(res.message)
  }catch(cause){notifyFailure(errorMessage(cause))}finally{saving.value=false}
}
const removeGroup=async(row:UserGroup)=>{
  if(saving.value)return
  try{await ElMessageBox.confirm(`确定物理删除用户组“${row.groupName}”吗？`,'删除确认',{type:'warning'})}catch{return}
  saving.value=true
  try{const res=await deleteUserGroup({id:row.id});if(res.success){ElMessage.success('删除成功');await Promise.all([loadGroups(),loadOptions()])}else notifyFailure(res.message)}catch(cause){notifyFailure(errorMessage(cause))}finally{saving.value=false}
}
const openUserDialog=(row?:ExternalUser)=>{
  if(!enterpriseMode.value && (!activeGroup.value || (row && row.groupId !== activeGroup.value.id)))return
  const groupId = enterpriseMode.value ? row?.groupId || userFilters.groupId || null : activeGroup.value!.id
  Object.assign(userForm,row?{id:row.id,groupId,realName:row.realName,account:row.account,password:'',phone:row.phone||'',remarks:row.remarks||'',enabled:row.enabled}:{id:0,groupId,realName:'',account:'',password:'',phone:'',remarks:'',enabled:1});userDialog.value=true
}
const saveUser=async()=>{
  if(saving.value)return
  const groupId=enterpriseMode.value ? userForm.groupId : activeGroup.value?.id
  if(!groupId || userForm.groupId!==groupId)return ElMessage.warning('请选择用户组')
  if(!userForm.realName.trim()||!userForm.account.trim()||(!userForm.id&&userForm.password.length<8))return ElMessage.warning('请完整填写必填项，密码至少8位')
  const commonData={groupId,realName:userForm.realName,account:userForm.account,phone:userForm.phone,remarks:userForm.remarks,enabled:userForm.enabled}
  saving.value=true
  try{
    const createData={...commonData,password:userForm.password}
    const updateData={...commonData,id:userForm.id}
    const res=userForm.id?await updateExternalUser(updateData):await createExternalUser(createData)
    if(res.success){ElMessage.success(res.message||'保存成功');userDialog.value=false;await Promise.all([loadUsers(),enterpriseMode.value ? loadGroupOptions() : loadGroups()])}else notifyFailure(res.message)
  }catch(cause){notifyFailure(errorMessage(cause))}finally{saving.value=false}
}
const removeUsers=async(ids:number[])=>{
  if(saving.value || (!enterpriseMode.value && !activeGroup.value) || !ids.length || ids.some(id=>!users.value.some(user=>user.id===id && (enterpriseMode.value || user.groupId===activeGroup.value?.id))))return
  try{await ElMessageBox.confirm(`确定物理删除选中的 ${ids.length} 名用户及其关联私有技能吗？`,'删除确认',{type:'warning'})}catch{return}
  saving.value=true
  try{const res=ids.length===1?await deleteExternalUser({id:ids[0]}):await batchDeleteExternalUsers({ids});if(res.success){ElMessage.success(res.message||'删除成功');await Promise.all([loadUsers(),enterpriseMode.value ? loadGroupOptions() : loadGroups()])}else notifyFailure(res.message)}catch(cause){notifyFailure(errorMessage(cause))}finally{saving.value=false}
}
const removeSelectedUsers=()=>removeUsers(selectedUsers.value.map(item=>item.id))
const openResetDialog=(row:ExternalUser)=>{if(!enterpriseMode.value && row.groupId!==activeGroup.value?.id)return;resetUserId.value=row.id;resetPassword.value='';resetDialog.value=true}
const saveResetPassword=async()=>{
  if(saving.value || !users.value.some(user=>user.id===resetUserId.value && (enterpriseMode.value || user.groupId===activeGroup.value?.id)))return
  if(resetPassword.value.length<8)return ElMessage.warning('密码至少8位')
  saving.value=true
  try{const res=await resetExternalUserPassword({id:resetUserId.value,newPassword:resetPassword.value});if(res.success){ElMessage.success('密码重置成功');resetDialog.value=false}else notifyFailure(res.message)}catch(cause){notifyFailure(errorMessage(cause))}finally{saving.value=false}
}

watch(groupPage,()=>{void loadGroups()},{flush:'sync'})
watch(userPage,()=>{void loadUsers()},{flush:'sync'})
watch(()=>[groupFilters.keyword,groupFilters.enabled],()=>{clearTimeout(groupTimer);groupTimer=setTimeout(()=>{if(groupPage.value!==1)groupPage.value=1;else void loadGroups()},300)})
watch(()=>[userFilters.keyword,userFilters.enabled,userFilters.groupId],()=>{clearTimeout(userTimer);if(!enterpriseMode.value && !activeGroup.value)return;userTimer=setTimeout(()=>{if(userPage.value!==1)userPage.value=1;else void loadUsers()},300)},{flush:'sync'})
const initializeView = () => {
  clearTimeout(groupTimer); clearTimeout(userTimer); groupVersion++; userVersion++
  activeGroup.value=undefined; users.value=[]; selectedUsers.value=[]; userDialog.value=false; resetDialog.value=false; groupDialog.value=false
  userFilters.keyword=''; userFilters.enabled=''; userFilters.groupId=''; userPage.value=1
  if (enterpriseMode.value) void Promise.all([loadGroupOptions(),loadUsers()])
  else void Promise.all([loadOptions(),loadGroups()])
}
watch(enterpriseMode,initializeView)
onMounted(initializeView)
onUnmounted(()=>{clearTimeout(groupTimer);clearTimeout(userTimer);groupVersion++;userVersion++})
</script>

<style scoped lang="scss">
@media(min-width:761px) and (max-width:1100px){.toolbar{flex-wrap:wrap}.toolbar>.el-input{flex:1;min-width:220px}.toolbar>.el-select,.toolbar>.el-button{flex-shrink:0}}
.agent-picker :deep(.el-checkbox-group){display:flex;flex-direction:column;align-items:flex-start}.agent-picker :deep(.el-checkbox){height:auto;min-height:32px;margin-right:0;max-width:100%}.agent-picker :deep(.el-checkbox__label){white-space:normal;overflow-wrap:anywhere}.agent-picker-hint{margin-top:8px;color:var(--el-text-color-secondary);font-size:12px}
.management-page{height:100%;padding:20px;background:#f2f4f7}.management-card{min-height:calc(100vh - 100px);border:0}.page-header{display:flex;align-items:center;justify-content:space-between}.page-header h2{margin:0;color:#17233d}.toolbar{display:flex;align-items:center;gap:12px;margin-bottom:18px}.toolbar>.el-input{width:260px}.toolbar>.el-select{width:170px}.pagination{display:flex;justify-content:flex-end;padding-top:18px}.full-width{width:100%}.dialog-form :deep(.el-form-item__label){white-space:nowrap}@media(max-width:760px){.management-page{padding:12px}.toolbar{align-items:stretch;flex-direction:column}.toolbar>.el-input,.toolbar>.el-select,.toolbar>.el-button{width:100%}.pagination{justify-content:center;overflow:auto}}
</style>
