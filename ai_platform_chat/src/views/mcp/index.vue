<template>
  <section class="mcp-page">
    <header class="page-header"><div><h1>{{ activeCategory ? activeCategory.name : 'MCP 分类' }}</h1></div><div class="actions"><el-button v-if="activeCategory" @click="enterCategory()">返回分类</el-button><el-button :loading="loading" @click="load">刷新</el-button><el-button v-if="activeCategory" type="primary" :icon="Plus" @click="edit()">添加 MCP</el-button></div></header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="!activeCategory">
      <el-input v-model="categoryKeyword" clearable :prefix-icon="Search" placeholder="搜索分类" aria-label="搜索 MCP 分类" class="search" />
      <el-table v-loading="loading" :data="filteredCategories" empty-text="暂无分类，请联系管理员创建分类"><el-table-column prop="name" label="分类名称" /><el-table-column label="可用 MCP 数量" width="150"><template #default="{ row }">{{ rows.filter(item => (item.categoryId || 0) === row.id).length }}</template></el-table-column><el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" @click="enterCategory(row)">进入分类</el-button></template></el-table-column></el-table>
    </template>
    <template v-else>
    <el-tabs v-model="visibility"><el-tab-pane label="公用 MCP" name="public" /><el-tab-pane label="私有 MCP" name="private" /></el-tabs>
    <el-input v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索名称或服务地址" aria-label="搜索 MCP" class="search" />
    <el-table v-loading="loading" :data="pageRows" row-key="id" empty-text="暂无可用 MCP，可添加个人服务或联系管理员授权">
      <el-table-column prop="name" label="名称" width="140" fixed="left" show-overflow-tooltip />
      <el-table-column label="来源" width="110"><template #default="{ row }"><el-tag>{{ scopeLabel(row) }}</el-tag></template></el-table-column>
      <el-table-column prop="url" label="服务地址" min-width="240" show-overflow-tooltip />
      <el-table-column label="请求方式" width="110"><template #default="{ row }"><el-tag>{{ row.httpRequest?.method || 'MCP 协议' }}</el-tag></template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="工具" width="90"><template #default="{ row }">{{ row.selectedTools.length }} / {{ row.tools.length }}</template></el-table-column>
      <el-table-column label="操作" min-width="340"><template #default="{ row }"><el-button v-if="row.canManage !== false" link type="primary" :disabled="saving" @click="test(row)">测试请求</el-button><el-button link type="primary" @click="openTools(row)">{{ row.canManage === false || row.httpRequest ? '查看工具' : '选择工具' }}</el-button><el-button v-if="row.canManage !== false" link type="primary" :disabled="saving" @click="edit(row)">编辑</el-button><el-button v-if="row.canManage !== false" link type="danger" :disabled="saving" @click="remove(row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="filtered.length" layout="total, prev, pager, next" class="pagination" />
    </template>

    <el-dialog v-model="editing" :title="form.id ? '编辑 MCP' : '添加 MCP'" width="min(800px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" :disabled="saving" @submit.prevent="save">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" maxlength="100" /></el-form-item>
        <el-form-item label="所属分类" prop="categoryId"><el-select v-model="form.categoryId" filterable aria-label="所属分类" placeholder="选择分类"><el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="服务地址" prop="url"><el-input v-model="form.url" placeholder="http://127.0.0.1:8100/api/chat/sync" maxlength="2048" /></el-form-item>
        <el-alert v-if="form.id && !initialRequest" title="保存后改为 HTTP 接口工具；请在技能组配置中重新核对使用的工具。" type="warning" :closable="false" />
        <HttpRequestEditor v-if="editing" :key="editorVersion" ref="requestEditor" :initial="initialRequest" />
        <el-form-item label="状态"><el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="editing = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="toolsOpen" :title="`选择工具 · ${toolConfig?.name || ''}`" width="min(800px, 94vw)">
      <el-alert title="仅勾选需要的工具。写入类及未声明只读的工具，在调用时需要你确认。" type="info" :closable="false" />
      <el-empty v-if="!toolConfig?.tools.length" description="暂无工具，请先测试连接" />
      <el-checkbox-group v-model="chosenTools" class="tool-list" :disabled="toolConfig?.canManage === false || !!toolConfig?.httpRequest">
        <div v-for="tool in toolConfig?.tools" :key="tool.name" class="tool-row"><el-checkbox :value="tool.name" :label="tool.name" /><el-tag size="small" :type="tool.readOnly ? 'success' : 'warning'">{{ tool.readOnly ? '只读' : '执行前确认' }}</el-tag><p>{{ tool.description || '服务未提供工具说明' }}</p><el-collapse><el-collapse-item title="参数定义" :name="tool.name"><pre>{{ JSON.stringify(tool.inputSchema, null, 2) }}</pre></el-collapse-item></el-collapse></div>
      </el-checkbox-group>
      <template #footer><el-button @click="toolsOpen = false">关闭</el-button><el-button v-if="toolConfig?.canManage !== false && !toolConfig?.httpRequest" type="primary" :loading="saving" @click="saveTools">保存选择</el-button></template>
    </el-dialog>

    <HttpRequestTest v-model="testOpen" :config="testConfig" :send="testMyMcp" @tested="load" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { deleteMyMcp, getAvailableMcp, getMcpCategories, saveMyMcp, saveMyMcpTools, testMyMcp, type McpCategory, type McpSave, type PersonalMcp } from '@/api/mcp'
import type { HttpRequestConfig } from '@/api/mcp'
import HttpRequestEditor from './HttpRequestEditor.vue'
import HttpRequestTest from './HttpRequestTest.vue'

const rows = ref<PersonalMcp[]>([]), loading = ref(false), error = ref(''), keyword = ref(''), page = ref(1)
const categories = ref<McpCategory[]>([]), activeCategory = ref<McpCategory>(), categoryKeyword = ref(''), visibility = ref<'public' | 'private'>('public')
const filteredCategories = computed(() => [...categories.value, ...(rows.value.some(item => !item.categoryId) ? [{id: 0, name: '未分类'}] : [])].filter(item => item.name.toLowerCase().includes(categoryKeyword.value.trim().toLowerCase())))
const editing = ref(false), saving = ref(false), formRef = ref<FormInstance>()
const initialRequest = ref<HttpRequestConfig | null>(), requestEditor = ref<InstanceType<typeof HttpRequestEditor>>(), editorVersion = ref(0)
const testOpen = ref(false), testConfig = ref<PersonalMcp>()
const form = reactive<McpSave>({ name: '', url: '', authType: 'none', enabled: 1 })
const rules: FormRules = { name: [{ required: true, whitespace: true, message: '请输入名称', trigger: 'blur' }], url: [{ required: true, whitespace: true, message: '请输入服务地址', trigger: 'blur' }], categoryId: [{required: true, message: '请选择分类', trigger: 'change'}] }
const filtered = computed(() => rows.value.filter(row => (row.categoryId || 0) === activeCategory.value?.id && (visibility.value === 'public' ? row.configScope === 'company' && row.visibility === 'public' : row.configScope !== 'company' || row.visibility !== 'public') && `${row.name} ${row.url}`.toLowerCase().includes(keyword.value.toLowerCase())))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * 10, page.value * 10))
const toolsOpen = ref(false), toolConfig = ref<PersonalMcp>(), chosenTools = ref<string[]>([])
const message = (cause: unknown) => cause instanceof Error ? cause.message : '操作失败，请重试'
const scopeLabel = (row: PersonalMcp) => row.configScope === 'company' ? (row.visibility === 'public' ? '公司公用' : '公司授权') : '个人配置'
function check(response: { success: boolean; message?: string }) { if (!response.success) throw new Error(response.message || '操作失败') }
async function load() {
  loading.value = true; error.value = ''
  try {
    const [res, categoryResponse] = await Promise.all([getAvailableMcp(), getMcpCategories()]); check(res); check(categoryResponse)
    rows.value = res.data; categories.value = categoryResponse.data
    if (activeCategory.value?.id === 0 && !rows.value.some(item => !item.categoryId)) activeCategory.value = undefined
    page.value = Math.min(page.value, Math.max(1, Math.ceil(filtered.value.length / 10)))
  }
  catch (cause) { error.value = message(cause) }
  finally { loading.value = false }
}
function enterCategory(category?: McpCategory) { activeCategory.value = category; keyword.value = ''; visibility.value = 'public'; page.value = 1 }
function edit(row?: PersonalMcp) { initialRequest.value = row?.httpRequest; editorVersion.value++; Object.assign(form, { id: row?.id, categoryId: row?.categoryId || activeCategory.value?.id || undefined, name: row?.name || '', url: row?.url || '', authType: 'none', enabled: row?.enabled ?? 1 }); editing.value = true; formRef.value?.clearValidate() }
async function save() {
  if (saving.value || !await formRef.value?.validate().catch(() => false)) return
  saving.value = true
  try { if (!requestEditor.value) throw new Error('请求配置尚未加载'); check(await saveMyMcp({ ...form, httpRequest: requestEditor.value.getRequest() })); editing.value = false; visibility.value = 'private'; ElMessage.success('已保存，可测试请求或绑定技能'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
function test(row: PersonalMcp) { testConfig.value = row; testOpen.value = true }
function openTools(row: PersonalMcp) { toolConfig.value = row; chosenTools.value = row.selectedTools.filter(name => row.tools.some(tool => tool.name === name)); toolsOpen.value = true }
async function saveTools() {
  if (!toolConfig.value || saving.value) return
  saving.value = true
  try { check(await saveMyMcpTools(toolConfig.value.id, chosenTools.value)); toolsOpen.value = false; ElMessage.success('工具选择已保存'); await load() }
  catch (cause) { ElMessage.error(message(cause)) } finally { saving.value = false }
}
async function remove(row: PersonalMcp) {
  try { await ElMessageBox.confirm(`删除“${row.name}”及其私有技能绑定？外部 MCP 服务不会被删除。`, '删除确认', { type: 'warning' }) }
  catch { return }
  try { check(await deleteMyMcp(row.id)); ElMessage.success('已删除'); await load() } catch (cause) { ElMessage.error(message(cause)) }
}
watch(keyword, () => { page.value = 1 })
watch(visibility, () => { page.value = 1 })
onMounted(load)
</script>

<style scoped lang="scss">
.mcp-page { padding: 28px; background: #fff; min-height: 100%; box-sizing: border-box; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; h1 { margin: 0; font-size: 24px; color: var(--text-color, #17233d); } p { color: #687993; font-size: 14px; margin: 8px 0 0; } }
.actions { display: flex; gap: 8px; }.search { width: min(100%, 360px); margin: 20px 0; }.pagination { justify-content: flex-end; margin-top: 20px; }
.tool-list { display: block; margin-top: 16px; }.tool-row { border-bottom: 1px solid #edf0f5; padding: 12px 0; p { font-size: 13px; color: #687993; overflow-wrap: anywhere; } .el-tag { margin-left: 12px; } }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }.el-form .el-select { width: 100%; }
@media (max-width: 700px) { .mcp-page { padding: 16px; }.page-header { align-items: flex-start; flex-direction: column; }.pagination { overflow: auto; justify-content: flex-start; } }
</style>
