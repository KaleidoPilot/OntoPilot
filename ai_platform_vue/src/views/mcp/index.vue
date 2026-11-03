<template>
  <div class="mcp-page">
    <el-card shadow="never">
      <header class="page-header">
        <div><h2>{{ activeCategory ? activeCategory.name : 'MCP 分类' }}</h2></div>
        <div class="actions"><el-button v-if="activeCategory" @click="enterCategory()">返回分类</el-button><el-button :loading="loading" @click="load">刷新</el-button><el-button v-if="!activeCategory" type="primary" :icon="Plus" @click="editCategory()">新增分类</el-button><el-button v-else type="primary" :icon="Plus" @click="edit()">新增 MCP</el-button></div>
      </header>
      <el-alert v-if="!hasMcpToken" title="请退出并重新登录，以获取 MCP 管理凭证。" type="warning" show-icon :closable="false" />
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"><template #default><el-button link @click="load">重新加载</el-button></template></el-alert>
      <template v-if="!activeCategory">
        <el-input v-model="categoryKeyword" clearable :prefix-icon="Search" placeholder="搜索分类" aria-label="搜索 MCP 分类" />
        <el-table v-loading="loading" :data="filteredCategories" empty-text="暂无分类，点击新增分类开始配置">
          <el-table-column prop="name" label="分类名称" min-width="180" />
          <el-table-column label="公司 MCP 数量" width="150"><template #default="{ row }">{{ row.total ?? '—' }}</template></el-table-column>
          <el-table-column label="操作" min-width="220"><template #default="{ row }"><el-button link type="primary" @click="enterCategory(row)">进入分类</el-button><el-button v-if="row.id" link type="primary" @click="editCategory(row)">编辑分类</el-button><el-button v-if="row.id" link type="danger" :disabled="saving" @click="removeCategory(row)">删除分类</el-button></template></el-table-column>
        </el-table>
      </template>
      <template v-else>
      <el-tabs v-model="visibility" @tab-change="resetPage"><el-tab-pane label="公用 MCP" name="public" /><el-tab-pane label="私有 MCP" name="private" /></el-tabs>
      <div class="toolbar">
        <el-input v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索名称或服务地址" aria-label="搜索 MCP" @keyup.enter="resetPage" @clear="resetPage" />
        <el-select v-model="enabled" clearable placeholder="全部状态" aria-label="筛选 MCP 状态" @change="resetPage"><el-option label="启用" :value="1" /><el-option label="停用" :value="0" /></el-select>
        <el-button @click="resetPage">搜索</el-button>
      </div>
      <el-table v-loading="loading" :data="rows" row-key="id" :empty-text="error ? '加载失败，请重新加载' : '当前范围暂无 MCP，点击新增 MCP 开始配置'">
        <el-table-column prop="name" label="名称" width="140" fixed="left" show-overflow-tooltip />
        <el-table-column prop="url" label="服务地址" min-width="220" show-overflow-tooltip />
        <el-table-column label="请求方式" width="100"><template #default="{ row }"><el-tag>{{ row.httpRequest?.method || 'MCP 协议' }}</el-tag></template></el-table-column>
        <el-table-column label="使用范围" width="140"><template #default="{ row }"><el-tag>{{ row.visibility === 'public' ? '公司全部用户' : `${row.accessUserIds.length} 位指定用户` }}</el-tag></template></el-table-column>
        <el-table-column label="状态" width="85"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="工具" width="80"><template #default="{ row }">{{ row.selectedTools.length }} / {{ row.tools.length }}</template></el-table-column>
        <el-table-column label="操作" min-width="410"><template #default="{ row }">
          <el-button link type="primary" :disabled="saving" @click="test(row)">测试请求</el-button>
          <el-button link type="primary" :disabled="saving" @click="openTools(row)">{{ row.httpRequest ? '查看工具' : '选择工具' }}</el-button>
          <el-button link type="primary" :disabled="saving" @click="edit(row)">编辑</el-button>
          <el-button link type="primary" :disabled="saving" @click="edit(row, true)">{{ row.visibility === 'public' ? '转为私有' : '转为公用' }}</el-button>
          <el-button link :disabled="saving" @click="toggleEnabled(row)">{{ row.enabled ? '停用' : '启用' }}</el-button>
          <el-button link type="danger" :disabled="saving" @click="remove(row)">删除</el-button>
        </template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="pageNo" :page-size="10" :total="total" layout="total, prev, pager, next" class="pagination" @current-change="load" />
      </template>
    </el-card>
    <el-dialog v-model="categoryEditing" :title="categoryForm.id ? '编辑分类' : '新增分类'" width="min(460px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving">
      <el-form label-width="90px" @submit.prevent="saveCategory"><el-form-item label="分类名称" required><el-input v-model="categoryForm.name" maxlength="100" aria-label="分类名称" :disabled="saving" placeholder="例如：房屋、公司" @keyup.enter="saveCategory" /></el-form-item></el-form>
      <template #footer><el-button :disabled="saving" @click="categoryEditing = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveCategory">保存分类</el-button></template>
    </el-dialog>

    <el-dialog v-model="editing" :title="form.id ? '编辑 MCP' : '新增 MCP'" width="min(800px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" :disabled="saving" @submit.prevent="save">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" maxlength="100" /></el-form-item>
        <el-form-item label="所属分类" prop="categoryId"><el-select v-model="form.categoryId" filterable aria-label="所属分类" placeholder="选择分类"><el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="服务地址" prop="url"><el-input v-model="form.url" placeholder="http://127.0.0.1:8100/api/chat/sync" maxlength="2048" /></el-form-item>
        <el-alert v-if="form.id && !initialRequest" title="保存后改为 HTTP 接口工具；原 MCP 协议的技能绑定需要重新选择。" type="warning" :closable="false" />
        <HttpRequestEditor v-if="editing" :key="editorVersion" ref="requestEditor" :initial="initialRequest" />
        <el-form-item label="使用范围"><el-radio-group v-model="form.visibility"><el-radio value="public" label="public">公用 MCP</el-radio><el-radio value="private" label="private">私有 MCP</el-radio></el-radio-group></el-form-item>
        <el-form-item v-if="form.visibility === 'private'" label="指定用户" prop="accessUserIds">
          <el-select v-model="form.accessUserIds" multiple filterable remote :remote-method="searchUsers" :loading="usersLoading" placeholder="搜索并选择当前公司用户" aria-label="指定 MCP 用户">
            <el-option v-for="user in userOptions" :key="user.id" :label="userLabel(user)" :value="user.id" />
            <el-option v-for="id in missingUserIds" :key="id" :label="`用户 ${id}（需重新确认）`" :value="id" disabled />
          </el-select>
          <small>仅所选用户可见、可用，支持选择多人。</small>
        </el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <el-alert :title="form.visibility === 'public' ? '当前公司所有用户都可以使用此 MCP。' : '只有指定用户可以使用此 MCP。'" type="info" :closable="false" />
      <template #footer><el-button :disabled="saving" @click="editing = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="toolsOpen" :title="`选择工具 · ${toolConfig?.name || ''}`" width="min(800px, 94vw)">
      <el-alert title="仅选择需要的工具。写入类及未声明只读的工具，在用户调用时需要确认。" type="info" :closable="false" />
      <el-empty v-if="!toolConfig?.tools.length" description="暂无工具，请先测试连接" />
      <el-checkbox-group v-model="chosenTools" class="tool-list" :disabled="!!toolConfig?.httpRequest">
        <div v-for="tool in toolConfig?.tools" :key="tool.name" class="tool-row"><el-checkbox :value="tool.name" :label="tool.name" /><el-tag :type="tool.readOnly ? 'success' : 'warning'" size="small">{{ tool.readOnly ? '只读' : '执行前确认' }}</el-tag><p>{{ tool.description || '服务未提供工具说明' }}</p><el-collapse><el-collapse-item title="参数定义" :name="tool.name"><pre>{{ JSON.stringify(tool.inputSchema, null, 2) }}</pre></el-collapse-item></el-collapse></div>
      </el-checkbox-group>
      <template #footer><el-button :disabled="saving" @click="toolsOpen = false">关闭</el-button><el-button v-if="!toolConfig?.httpRequest" type="primary" :loading="saving" @click="saveTools">保存选择</el-button></template>
    </el-dialog>
    <HttpRequestTest v-model="testOpen" :config="testConfig" :send="testCompanyMcp" @tested="load" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { deleteCompanyMcp, getCompanyMcpPage, getCompanyMcpUsers, saveCompanyMcp, saveCompanyMcpTools, testCompanyMcp, getMcpCategories, saveMcpCategory, deleteMcpCategory, type McpCategory, type CompanyMcp, type CompanyMcpSave, type McpUser } from '@/api/mcp'
import type { HttpRequestConfig } from '@/api/mcp'
import HttpRequestEditor from './HttpRequestEditor.vue'
import HttpRequestTest from './HttpRequestTest.vue'

const rows = ref<CompanyMcp[]>([]), total = ref(0), loading = ref(false), error = ref('')
const categories = ref<McpCategory[]>([]), activeCategory = ref<McpCategory>(), categoryKeyword = ref('')
const uncategorizedCount = ref(0)
const categoryEditing = ref(false), categoryForm = reactive<{id?: number; name: string}>({name: ''})
const filteredCategories = computed(() => [...categories.value, ...(uncategorizedCount.value ? [{id: 0, name: '未分类', total: uncategorizedCount.value}] : [])].filter(item => item.name.toLowerCase().includes(categoryKeyword.value.trim().toLowerCase())))
const visibility = ref<'public' | 'private'>('public'), keyword = ref(''), enabled = ref<0 | 1>(), pageNo = ref(1)
const editing = ref(false), saving = ref(false), formRef = ref<FormInstance>()
const initialRequest = ref<HttpRequestConfig | null>(), requestEditor = ref<InstanceType<typeof HttpRequestEditor>>(), editorVersion = ref(0)
const testOpen = ref(false), testConfig = ref<CompanyMcp>()
const originalVisibility = ref<'public' | 'private'>()
const form = reactive<CompanyMcpSave>({ name: '', url: '', authType: 'none', enabled: 1, visibility: 'public', accessUserIds: [] })
const hasMcpToken = (() => { try { return !!JSON.parse(localStorage.getItem('userInfo') || '{}').mcpToken } catch { return false } })()
const rules: FormRules = {
  name: [{ required: true, whitespace: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, whitespace: true, message: '请输入服务地址', trigger: 'blur' }],
  categoryId: [{ required: true, message: '请选择分类', trigger: 'change' }],
  accessUserIds: [{ validator: (_rule, value, callback) => callback(form.visibility === 'private' && !value?.length ? new Error('请至少选择一位用户') : undefined), trigger: 'change' }]
}
const userOptions = ref<McpUser[]>([]), usersLoading = ref(false)
const missingUserIds = computed(() => form.accessUserIds.filter(id => !userOptions.value.some(user => user.id === id)))
const userLabel = (user: McpUser) => `${user.realName}（${user.account}） · ${user.groupName}`
const toolsOpen = ref(false), toolConfig = ref<CompanyMcp>(), chosenTools = ref<string[]>([])
let listVersion = 0, userVersion = 0
function check(response: { success: boolean; message?: string }) { if (!response.success) throw new Error(response.message || '操作失败') }
const message = (cause: unknown) => cause instanceof Error ? cause.message : '操作失败，请重试'
async function load() {
  const version = ++listVersion
  loading.value = true; error.value = ''
  try {
    const [categoryResponse, uncategorizedResponse] = await Promise.all([
      getMcpCategories(), getCompanyMcpPage({pageNo: 1, pageSize: 1, categoryId: 0}),
    ])
    check(categoryResponse); check(uncategorizedResponse)
    if (version !== listVersion) return
    categories.value = categoryResponse.data
    uncategorizedCount.value = uncategorizedResponse.data.total
    if (activeCategory.value?.id === 0 && !uncategorizedCount.value) activeCategory.value = undefined
    if (!activeCategory.value) { rows.value = []; total.value = 0; return }
    const res = await getCompanyMcpPage({ pageNo: pageNo.value, pageSize: 10, keyword: keyword.value.trim() || undefined, visibility: visibility.value, enabled: enabled.value, categoryId: activeCategory.value.id }); check(res)
    if (version !== listVersion) return
    rows.value = res.data.list; total.value = res.data.total
    if (!rows.value.length && pageNo.value > 1) { pageNo.value = Math.max(1, Math.ceil(total.value / 10)); return }
  } catch (cause) { if (version === listVersion) { rows.value = []; total.value = 0; error.value = message(cause) } }
  finally { if (version === listVersion) loading.value = false }
}
function resetPage() { if (pageNo.value !== 1) pageNo.value = 1; else void load() }
function enterCategory(category?: McpCategory) { activeCategory.value = category; keyword.value = ''; enabled.value = undefined; visibility.value = 'public'; pageNo.value = 1; void load() }
function editCategory(category?: McpCategory) { Object.assign(categoryForm, {id: category?.id, name: category?.name || ''}); categoryEditing.value = true }
async function saveCategory() {
  if (saving.value) return
  if (!categoryForm.name.trim()) { ElMessage.warning('请输入分类名称'); return }
  saving.value = true
  try { check(await saveMcpCategory({...categoryForm, name: categoryForm.name.trim()})); categoryEditing.value = false; ElMessage.success('分类已保存'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
async function removeCategory(category: McpCategory) {
  try { await ElMessageBox.confirm(`删除“${category.name}”分类？分类下仍有 MCP 时无法删除。`, '删除分类', {type: 'warning'}) } catch { return }
  saving.value = true
  try { check(await deleteMcpCategory(category.id)); ElMessage.success('分类已删除'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
async function searchUsers(keyword = '') {
  const version = ++userVersion; usersLoading.value = true
  try {
    const [found, selected] = await Promise.all([getCompanyMcpUsers(keyword), form.accessUserIds.length ? getCompanyMcpUsers(undefined, form.accessUserIds) : Promise.resolve(undefined)])
    check(found); if (selected) check(selected)
    if (version !== userVersion) return
    userOptions.value = [...new Map([...found.data.list, ...(selected?.data.list || [])].map(user => [user.id, user])).values()]
  } catch (cause) { if (version === userVersion) ElMessage.error(message(cause)) }
  finally { if (version === userVersion) usersLoading.value = false }
}
function edit(row?: CompanyMcp, switchScope = false) {
  originalVisibility.value = row?.visibility
  initialRequest.value = row?.httpRequest; editorVersion.value++
  Object.assign(form, { id: row?.id, name: row?.name || '', url: row?.url || '', authType: 'none', enabled: row?.enabled ?? 1,
    categoryId: row?.categoryId || activeCategory.value?.id || undefined,
    visibility: row ? (switchScope ? (row.visibility === 'public' ? 'private' : 'public') : row.visibility) : visibility.value, accessUserIds: [...(row?.accessUserIds || [])], confirmVisibilityChange: false })
  userOptions.value = []; editing.value = true; formRef.value?.clearValidate(); void searchUsers()
}
async function save() {
  if (saving.value || !await formRef.value?.validate().catch(() => false)) return
  saving.value = true
  try {
    if (!requestEditor.value) throw new Error('请求配置尚未加载')
    const httpRequest = requestEditor.value.getRequest()
    const changed = !!form.id && originalVisibility.value !== form.visibility
    if (changed) {
      const text = form.visibility === 'private' ? `切换为私有后，仅所选的 ${form.accessUserIds.length} 位用户可以使用；其他用户将无法继续调用，已有技能绑定也会受限。是否继续？` : '切换为公用后，当前公司的全部用户都可以使用此 MCP。是否继续？'
      try { await ElMessageBox.confirm(text, '使用范围变更确认', { type: 'warning', confirmButtonText: '确认切换', cancelButtonText: '取消' }) } catch { return }
    }
    check(await saveCompanyMcp({ ...form, httpRequest, accessUserIds: form.visibility === 'private' ? [...form.accessUserIds] : [], confirmVisibilityChange: changed }))
    editing.value = false; ElMessage.success('已保存')
    if (visibility.value !== form.visibility) visibility.value = form.visibility
    await load()
  } catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
async function toggleEnabled(row: CompanyMcp) {
  saving.value = true
  try { check(await saveCompanyMcp({ id: row.id, categoryId: row.categoryId, name: row.name, url: row.url, authType: row.authType, httpRequest: row.httpRequest || undefined, visibility: row.visibility, accessUserIds: [...row.accessUserIds], enabled: row.enabled ? 0 : 1 })); ElMessage.success(row.enabled ? '已停用' : '已启用'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
function test(row: CompanyMcp) { testConfig.value = row; testOpen.value = true }
function openTools(row: CompanyMcp) { toolConfig.value = row; chosenTools.value = row.selectedTools.filter(name => row.tools.some(tool => tool.name === name)); toolsOpen.value = true }
async function saveTools() {
  if (!toolConfig.value || saving.value) return
  saving.value = true
  try { check(await saveCompanyMcpTools(toolConfig.value.id, [...chosenTools.value])); toolsOpen.value = false; ElMessage.success('工具选择已保存'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
async function remove(row: CompanyMcp) {
  try { await ElMessageBox.confirm(`删除“${row.name}”及其全部技能绑定？已授权用户将无法继续调用。`, '删除 MCP', { type: 'warning' }) } catch { return }
  saving.value = true
  try { check(await deleteCompanyMcp(row.id)); ElMessage.success('已删除'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
onMounted(load)
</script>

<style scoped lang="scss">
.mcp-page { padding: 20px; }.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; h2 { margin: 0; color: #17233d; } p { color: #687993; font-size: 14px; } }
.actions,.toolbar { display: flex; gap: 12px; }.actions { flex-wrap: wrap; .el-button { margin-left: 0; } }.toolbar { margin: 16px 0; > .el-input { width: 300px; } > .el-select { width: 130px; } }.pagination { justify-content: flex-end; margin-top: 20px; }
.el-form .el-select { width: 100%; } small { color: #687993; font-size: 13px; }.tool-list { display: block; margin-top: 16px; }.tool-row { padding: 12px 0; border-bottom: 1px solid #edf0f5; p { color: #687993; overflow-wrap: anywhere; }.el-tag { margin-left: 12px; } } pre { white-space: pre-wrap; overflow-wrap: anywhere; }
@media(max-width: 760px) { .mcp-page { padding: 12px; }.page-header,.toolbar { align-items: stretch; flex-direction: column; }.toolbar > .el-input,.toolbar > .el-select { width: 100%; }.pagination { overflow: auto; justify-content: flex-start; } }
</style>
