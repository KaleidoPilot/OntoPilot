<template>
  <section class="agent-page">
    <header class="page-header"><h1>技能组管理</h1><el-button type="primary" @click="openEditor()">新增私有技能组</el-button></header>
    <div class="agent-panel">
      <el-form inline @submit.prevent="search">
        <el-form-item><el-input v-model="keyword" clearable placeholder="搜索技能组名称或描述" aria-label="搜索技能组" @clear="search" /></el-form-item>
        <el-form-item><el-select v-model="source" aria-label="技能组来源" @change="search"><el-option label="全部技能组" value="all" /><el-option label="公司公有" value="company" /><el-option label="我创建的" value="mine" /><el-option label="接收分享" value="received" /></el-select></el-form-item>
        <el-form-item><el-button native-type="submit" :loading="loading">查询</el-button><el-button :disabled="loading" @click="load">刷新</el-button></el-form-item>
      </el-form>
      <el-alert v-if="error" :title="error" type="error" :closable="false"><template #default><el-button link @click="load">重新加载</el-button></template></el-alert>
      <el-table v-loading="loading" :data="rows" row-key="id" empty-text="暂无可用技能组，可以创建自己的私有技能组">
        <el-table-column prop="agentName" label="技能组名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="100"><template #default="{ row }"><el-tag :type="row.agentType === 1 ? 'success' : 'primary'">{{ row.agentType === 1 ? '公有' : '私有' }}</el-tag></template></el-table-column>
        <el-table-column label="来源" width="120"><template #default="{ row }">{{ row.agentType === 1 ? '后台创建' : row.canManage ? '我创建的' : '接收分享' }}</template></el-table-column>
        <el-table-column prop="agentDescription" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="270"><template #default="{ row }">
          <el-button link type="primary" :disabled="!row.enabled" @click="useAgent(row)">使用</el-button>
          <template v-if="row.canManage"><el-button link type="primary" @click="openEditor(row.id)">编辑</el-button><el-button link type="primary" @click="openShare(row)">分享</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template>
        </template></el-table-column>
      </el-table>
      <el-pagination v-if="total" v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next" background @current-change="load" />
    </div>

    <el-dialog v-model="editorOpen" :title="editingId ? '编辑私有技能组' : '新增私有技能组'" width="min(900px, 96vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
      <el-alert v-if="editorError" :title="editorError" type="error" :closable="false" />
      <el-form v-loading="optionsLoading" :model="form" label-width="120px" @submit.prevent="save">
        <el-form-item label="技能组名称" required><el-input v-model="form.agentName" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="技能组描述"><el-input v-model="form.agentDescription" type="textarea" :rows="2" maxlength="255" /></el-form-item>
        <el-form-item label="系统提示词" required><el-input v-model="form.systemPrompt" type="textarea" :rows="8" maxlength="60000" placeholder="定义角色、任务和约束" /></el-form-item>
        <h3>模型配置</h3>
        <div class="model-grid"><el-form-item v-for="role in modelRoles" :key="role.field" :label="role.label" required><el-select v-model="form[role.field]" filterable placeholder="选择已有模型"><el-option v-for="model in models.filter(item => item.type === role.type)" :key="model.id" :label="model.model" :value="model.id" /></el-select></el-form-item></div>
        <el-form-item label="温度"><el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" /></el-form-item>
        <el-form-item label="核采样"><el-input-number v-model="form.topP" :min="0" :max="1" :step="0.1" /></el-form-item>
        <h3>资源绑定</h3>
        <el-form-item label="个人技能"><el-select v-model="form.skillIds" multiple filterable clearable collapse-tags collapse-tags-tooltip :multiple-limit="20" placeholder="选择自己导入的技能"><el-option v-for="item in skills" :key="item.id" :label="item.skillName" :value="item.id" /></el-select></el-form-item>
        <el-form-item><span class="binding-note">已导入的个人技能可在这里绑定。分享技能组时，技能文本一起供接收人使用。</span></el-form-item>
        <el-form-item label="MCP"><el-select v-model="form.mcpIds" multiple filterable clearable collapse-tags collapse-tags-tooltip :multiple-limit="5" placeholder="选择可使用的 MCP"><el-option v-for="item in mcps" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="知识库"><el-select v-model="form.tenantIds" multiple filterable clearable collapse-tags collapse-tags-tooltip :multiple-limit="20" placeholder="选择可使用的知识库"><el-option v-for="item in tenants" :key="item.id" :label="`${item.tenantName} · ${tenantLabels[item.scopeType]}`" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="返回数量"><el-input-number v-model="form.tenantTopK" :min="1" :max="50" /></el-form-item>
        <el-form-item label="最低置信度"><el-input-number v-model="form.tenantScore" :min="0" :max="1" :step="0.01" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="editorOpen = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="optionsLoading || !optionsReady" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="shareOpen" :title="`分享技能组：${sharingAgent?.agentName || ''}`" width="min(850px, 96vw)" :close-on-click-modal="!sharing" :close-on-press-escape="!sharing" :show-close="!sharing">
      <el-alert title="绑定的个人技能文本随技能组分享，接收人不能编辑原技能。MCP 和知识库仍按接收人自己的权限检查。" type="info" :closable="false" />
      <el-alert v-if="shareError" :title="shareError" type="error" :closable="false" />
      <el-form v-loading="shareLoading" label-width="88px">
        <el-form-item label="接收用户"><el-select v-model="receivers" multiple filterable remote :remote-method="searchReceivers" :loading="receiverLoading" :multiple-limit="100" collapse-tags collapse-tags-tooltip placeholder="搜索同公司的用户"><el-option v-for="user in receiverOptions" :key="user.id" :value="user.id" :label="`${user.realName || user.account}（${user.account || user.id}）`" /></el-select></el-form-item>
        <el-form-item><el-button :disabled="receiverLoading" @click="receivers = Array.from(new Set([...receivers, ...currentSearchIds])).slice(0, 100)">全选当前搜索结果</el-button><el-button @click="receivers = []">清空分享</el-button></el-form-item>
      </el-form>
      <el-table :data="shareRecords" max-height="260" empty-text="暂无分享记录">
        <el-table-column label="接收用户" min-width="150"><template #default="{ row }">{{ row.realName || row.account || `用户 ${row.receiveUserId}` }}</template></el-table-column>
        <el-table-column prop="shareUserId" label="分享人ID" width="110" />
        <el-table-column prop="receiveUserId" label="接收人ID" width="110" />
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已分享' : '已撤销' }}</el-tag></template></el-table-column>
        <el-table-column prop="updateTime" label="更新时间" min-width="190" />
      </el-table>
      <template #footer><el-button :disabled="sharing" @click="shareOpen = false">取消</el-button><el-button type="primary" :loading="sharing" :disabled="shareLoading || !shareReady" @click="saveShare">保存分享名单</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPersonalAgentPage, getPersonalAgent, getPersonalAgentModels, createPersonalAgent, updatePersonalAgent, deletePersonalAgent, getAgentShares, getAgentShareUsers, sharePersonalAgent, type PersonalAgent, type PersonalAgentForm, type AgentShareRecord, type AgentReceiver } from '@/api/agent'
import { getAvailableMcp, type PersonalMcp } from '@/api/mcp'
import { getVisibleTenantPage, type UsableTenant } from '@/api/knowledge'
import { getImportedSkillOptions, type ImportedSkill } from '@/api/skill'

const router = useRouter()
const rows = ref<PersonalAgent[]>([]), total = ref(0), page = ref(1), keyword = ref(''), source = ref<'all' | 'mine' | 'received' | 'company'>('all'), loading = ref(false), error = ref('')
const editorOpen = ref(false), editingId = ref<number>(), saving = ref(false), optionsLoading = ref(false), optionsReady = ref(false), editorError = ref('')
const models = ref<Array<{ id: number; model: string; type: 1 | 2 | 3 | 4 }>>([]), mcps = ref<PersonalMcp[]>([]), tenants = ref<UsableTenant[]>([])
const skills = ref<Array<Pick<ImportedSkill, 'id' | 'skillName'>>>([])
const modelRoles = [{ field: 'intentLlmId', type: 1, label: '意图模型' }, { field: 'taskLlmId', type: 2, label: '任务分解模型' }, { field: 'executLlmId', type: 3, label: '执行模型' }, { field: 'summaryLlmId', type: 4, label: '总结模型' }] as const
const tenantLabels = { 1: '公司公有', 2: '公司私有', 3: '个人' }
const blank = (): PersonalAgentForm => ({ agentName: '', agentDescription: '', systemPrompt: '', userPromptTemplate: '', temperature: 0.7, topP: 0.9, intentLlmId: undefined, taskLlmId: undefined, executLlmId: undefined, summaryLlmId: undefined, mcpIds: [], tenantIds: [], skillIds: [], tenantTopK: 5, tenantScore: 0.4, enabled: 1 })
const form = ref(blank())
const shareOpen = ref(false), sharingAgent = ref<PersonalAgent>(), sharing = ref(false), shareLoading = ref(false), shareReady = ref(false), shareError = ref(''), receiverLoading = ref(false)
const receivers = ref<number[]>([]), receiverOptions = ref<AgentReceiver[]>([]), currentSearchIds = ref<number[]>([]), shareRecords = ref<AgentShareRecord[]>([])
let listVersion = 0, editorVersion = 0, receiverVersion = 0, shareVersion = 0

async function load() {
  const version = ++listVersion
  loading.value = true; error.value = ''
  try {
    const response = await getPersonalAgentPage({ keyword: keyword.value.trim() || undefined, source: source.value, pageNo: page.value, pageSize: 10 })
    if (version !== listVersion) return
    if (!response.success) throw new Error(response.message || '技能组加载失败')
    rows.value = response.data.list; total.value = response.data.total
  } catch (cause) { if (version === listVersion) { rows.value = []; total.value = 0; error.value = cause instanceof Error ? cause.message : '技能组加载失败' } }
  finally { if (version === listVersion) loading.value = false }
}
function search() { page.value = 1; void load() }
function useAgent(agent: PersonalAgent) { void router.push({ path: '/chat', query: { agentId: agent.id } }) }

async function loadTenants() {
  const all: UsableTenant[] = []
  for (let pageNo = 1; pageNo <= 100; pageNo++) {
    const response = await getVisibleTenantPage({ pageNo, pageSize: 100 })
    if (!response.success) throw new Error(response.message || '知识库加载失败')
    all.push(...response.data.list)
    if (all.length >= response.data.total || !response.data.list.length) return all.filter(item => item.enabled === 1)
  }
  throw new Error('知识库数量过多，请联系管理员整理后再选择')
}
async function openEditor(id?: number) {
  const version = ++editorVersion
  editorOpen.value = true; editingId.value = id; form.value = blank(); editorError.value = ''; optionsLoading.value = true; optionsReady.value = false
  try {
    const [modelResponse, mcpResponse, availableTenants, availableSkills, detail] = await Promise.all([getPersonalAgentModels(), getAvailableMcp(), loadTenants(), loadSkills(), id ? getPersonalAgent(id) : Promise.resolve(undefined)])
    if (version !== editorVersion) return
    if (!modelResponse.success || !mcpResponse.success || (detail && !detail.success)) throw new Error(detail?.message || modelResponse.message || mcpResponse.message || '选项加载失败')
    models.value = modelResponse.data.models
    mcps.value = mcpResponse.data.filter(item => item.enabled && item.selectedTools.length)
    tenants.value = availableTenants
    skills.value = availableSkills
    if (detail) {
      const value = detail.data
      form.value = { agentName: value.agentName, agentDescription: value.agentDescription || '', systemPrompt: value.systemPrompt, userPromptTemplate: value.userPromptTemplate || '', temperature: value.temperature, topP: value.topP, intentLlmId: value.intentLlmId, taskLlmId: value.taskLlmId, executLlmId: value.executLlmId, summaryLlmId: value.summaryLlmId, mcpIds: value.mcpIds, tenantIds: value.tenantIds, skillIds: value.skillIds || [], tenantTopK: value.tenantTopK, tenantScore: value.tenantScore, enabled: value.enabled }
    }
    optionsReady.value = true
  } catch (cause) { if (version === editorVersion) editorError.value = cause instanceof Error ? cause.message : '加载失败，请关闭后重试' }
  finally { if (version === editorVersion) optionsLoading.value = false }
}
async function loadSkills() {
  const all: Array<Pick<ImportedSkill, 'id' | 'skillName'>> = []
  for (let pageNo = 1; pageNo <= 100; pageNo++) {
    const response = await getImportedSkillOptions(pageNo)
    if (!response.success) throw new Error(response.message || '个人技能加载失败')
    all.push(...response.data.list)
    if (all.length >= response.data.total || !response.data.list.length) return all
  }
  throw new Error('个人技能数量过多，请整理后再选择')
}
async function save() {
  if (!optionsReady.value || optionsLoading.value || saving.value) return
  if (!form.value.agentName.trim() || !form.value.systemPrompt.trim()) { editorError.value = '请填写技能组名称和系统提示词'; return }
  for (const role of modelRoles) {
    if (!models.value.some(item => item.id === form.value[role.field] && item.type === role.type)) { editorError.value = `请选择可用的${role.label}`; return }
  }
  if (form.value.mcpIds.some(id => !mcps.value.some(item => item.id === id)) || form.value.tenantIds.some(id => !tenants.value.some(item => item.id === id))) { editorError.value = '部分绑定资源已失效，请移除或重新选择'; return }
  if (form.value.skillIds.some(id => !skills.value.some(item => item.id === id))) { editorError.value = '部分个人技能已停用或删除，请移除或重新选择'; return }
  saving.value = true; editorError.value = ''
  try {
    const response = editingId.value ? await updatePersonalAgent(editingId.value, form.value) : await createPersonalAgent(form.value)
    if (!response.success) throw new Error(response.message || '保存失败')
    editorOpen.value = false; ElMessage.success(response.message || '技能组已保存'); page.value = 1; source.value = 'mine'; keyword.value = ''; await load()
  } catch (cause) { editorError.value = cause instanceof Error ? cause.message : '保存失败' }
  finally { saving.value = false }
}
async function remove(agent: PersonalAgent) {
  try { await ElMessageBox.confirm(`确定删除“${agent.agentName}”吗？已分享的用户将无法再使用。`, '删除技能组', { type: 'warning' }) } catch { return }
  try {
    const response = await deletePersonalAgent(agent.id)
    if (!response.success) throw new Error(response.message || '删除失败')
    if (rows.value.length === 1 && page.value > 1) page.value--
    ElMessage.success(response.message || '已删除'); await load()
  } catch (cause) { ElMessage.error(cause instanceof Error ? cause.message : '删除失败') }
}
async function searchReceivers(keyword = '') {
  const version = ++receiverVersion
  receiverLoading.value = true
  try {
    const response = await getAgentShareUsers(keyword)
    if (version !== receiverVersion) return
    if (!response.success) throw new Error(response.message || '用户加载失败')
    currentSearchIds.value = response.data.list.map(item => item.id)
    const retained = receiverOptions.value.filter(item => receivers.value.includes(item.id))
    receiverOptions.value = Array.from(new Map([...retained, ...response.data.list].map(item => [item.id, item])).values())
  } catch (cause) { if (version === receiverVersion) { currentSearchIds.value = []; shareError.value = cause instanceof Error ? cause.message : '用户加载失败' } }
  finally { if (version === receiverVersion) receiverLoading.value = false }
}
async function openShare(agent: PersonalAgent) {
  const version = ++shareVersion
  receiverVersion++
  sharingAgent.value = agent; shareOpen.value = true; shareReady.value = false; shareLoading.value = true; shareError.value = ''; receivers.value = []; receiverOptions.value = []; shareRecords.value = []
  try {
    const [detail, records] = await Promise.all([getPersonalAgent(agent.id), getAgentShares(agent.id)])
    if (version !== shareVersion) return
    if (!detail.success || !records.success) throw new Error(detail.message || records.message || '分享记录加载失败')
    receivers.value = detail.data.shareUserIds
    shareRecords.value = records.data.list
    receiverOptions.value = records.data.list.map(row => ({ id: row.receiveUserId, realName: row.realName || '', account: row.account || '' }))
    await searchReceivers(); if (version === shareVersion) shareReady.value = true
  } catch (cause) { if (version === shareVersion) shareError.value = cause instanceof Error ? cause.message : '加载失败，请关闭后重试' }
  finally { if (version === shareVersion) shareLoading.value = false }
}
async function saveShare() {
  if (!sharingAgent.value || !shareReady.value || sharing.value) return
  sharing.value = true; shareError.value = ''
  try {
    const response = await sharePersonalAgent(sharingAgent.value.id, receivers.value)
    if (!response.success) throw new Error(response.message || '分享失败')
    ElMessage.success(response.message || '分享已保存'); await openShare(sharingAgent.value)
  } catch (cause) { shareError.value = cause instanceof Error ? cause.message : '分享失败' }
  finally { sharing.value = false }
}
onMounted(load)
</script>

<style scoped>
.agent-page { padding: 28px; min-width: 0; }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 20px; }
h1 { font-size: 24px; margin: 0; } h3 { margin: 20px 0; }
.binding-note { color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.agent-panel { background: var(--bg-card); padding: 24px; border-radius: 20px; }
.agent-panel :deep(.el-input) { width: 280px; }
.agent-panel :deep(.el-select) { width: 180px; }
.el-pagination { justify-content: flex-end; margin-top: 16px; }
.model-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 12px; }
:deep(.el-dialog .el-select) { width: 100%; }
:deep(.el-alert) { margin-bottom: 16px; }
@media (max-width: 700px) { .agent-page { padding: 16px; } .agent-panel { padding: 16px; } .page-header { flex-wrap: wrap; } .model-grid { grid-template-columns: 1fr; } .agent-panel :deep(.el-form-item) { display: block; margin-right: 0; } .agent-panel :deep(.el-input), .agent-panel :deep(.el-select) { width: 100%; } }
</style>
