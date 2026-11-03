<template>
  <section class="template-page">
    <header class="page-header"><div><h1>模板管理</h1><p>管理写作规则，供后续按新资料生成文档。</p></div><el-button type="primary" :disabled="busy" @click="openGenerate">生成模板</el-button></header>
    <el-dialog v-model="generateOpen" title="生成模板" width="min(720px,96vw)" :close-on-click-modal="false" :close-on-press-escape="!submitting" :show-close="!submitting">
      <el-alert v-if="capabilityError" :title="capabilityError" type="warning" :closable="false"><template #default><el-button link @click="loadCapabilities">重新检查</el-button></template></el-alert>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="模板文件" required>
          <el-upload ref="upload" drag :accept="accept" :auto-upload="false" :show-file-list="false" :disabled="busy" :on-change="chooseFile" class="template-upload">
            <el-icon class="upload-icon"><UploadFilled /></el-icon><div>点击或拖入一份模板</div>
            <template #tip><div class="upload-tip">{{ formatHint }} · 每份不超过10MB，PDF需可选中文字</div></template>
          </el-upload>
        </el-form-item>
        <div v-if="file" class="selected-file"><span>{{ file.name }} <small>{{ (file.size / 1024).toFixed(1) }} KB</small></span><el-button link type="danger" :disabled="busy" @click="clearFile">移除</el-button></div>
        <el-form-item label="模板名称（可选）"><el-input v-model="skillName" maxlength="100" show-word-limit placeholder="例如：年度工作总结；不填则自动识别" :disabled="busy" aria-label="模板名称" @input="resetRequestKey" /></el-form-item>
        <el-alert v-if="submitError" :title="submitError" type="error" :closable="false" />

        <p class="help">自动学习结构、写作要求和图表用途。范文中的人物、数字和旧结论不会作为新资料的事实。</p>
      </el-form><template #footer><el-button :disabled="submitting" @click="generateOpen=false">取消</el-button><el-button type="primary" :loading="submitting" :disabled="!file || busy" @click="submit">生成模板</el-button></template>
    </el-dialog>

    <div v-if="task || taskError" class="template-panel" aria-live="polite">
      <h2>提炼进度</h2>
      <template v-if="task">
        <div class="task-heading"><el-tag :type="statusType">{{ statusLabel }}</el-tag><span v-if="task.progress !== statusLabel">{{ task.progress }}</span><el-button :loading="checking" :disabled="submitting" @click="checkTask">刷新进度</el-button></div>
        <p class="help">任务号：{{ task.taskId }}。离开页面后，后台仍会继续处理。</p>
        <el-alert v-if="task.error" :title="task.error.message" type="error" :closable="false" />
        <el-alert v-for="warning in task.warnings || []" :key="warning" :title="warning" type="warning" :closable="false" />
        <el-button v-if="canRetry" type="primary" :loading="submitting" :disabled="checking" @click="retry">重试提炼</el-button>
        <el-button v-if="task.status === 'completed' && task.skillId" type="primary" link @click="showDetail(task.skillId)">查看提炼结果</el-button><el-button v-if="task.status === 'completed' && task.skillId" type="primary" link @click="openStructure(task.skillId, '模板')">结构图谱</el-button>
      </template>
      <el-alert v-if="taskError" :title="taskError" type="error" :closable="false"><template #default><el-button link @click="checkTask">重新获取进度</el-button></template></el-alert>
    </div>

    <div class="template-panel">
      <div class="list-heading"><h2>可用模板</h2><el-button :loading="loading" @click="load">刷新列表</el-button></div>
      <el-form inline @submit.prevent="search"><el-form-item><el-input v-model="keyword" clearable maxlength="100" aria-label="搜索模板" placeholder="搜索模板名称或用途" @clear="search" /></el-form-item><el-form-item><el-button native-type="submit" :disabled="loading">查询</el-button></el-form-item></el-form>
      <el-alert v-if="listError" :title="listError" type="error" :closable="false"><template #default><el-button link @click="load">重新加载</el-button></template></el-alert>
      <el-table v-loading="loading" :data="rows" row-key="id" empty-text="暂无模板，上传一份模板开始提炼">
        <el-table-column prop="skillName" label="模板名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="来源" width="100"><template #default="{row}">{{ row.ownerType==='company'?'公司授权':'我的模板' }}</template></el-table-column>
        <el-table-column prop="description" label="用途" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" min-width="280"><template #default="{ row }"><el-button link type="primary" :disabled="row.status === 'deleting' || deletingId === row.id" @click="showDetail(row.id)">查看写作规则</el-button><el-button link type="primary" :disabled="row.status === 'deleting'" @click="openStructure(row.id, row.skillName)">结构图谱</el-button><el-button v-if="row.ownerType!=='company'" link type="danger" :loading="deletingId === row.id" :disabled="!!deletingId" @click="removeTemplate(row)">{{ row.status === 'deleting' ? '重试删除' : '删除' }}</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="total" v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next" @current-change="load" />
    </div>
    <TemplateStructureDialog v-model="structureOpen" :skill-id="structureId" :name="structureName" />
    <el-dialog v-model="detailOpen" :title="detail?.meta.skillName || '模板 Skill'" width="min(900px, 96vw)">
      <div v-loading="detailLoading" class="detail-content">
        <el-alert v-if="detailError" :title="detailError" type="error" :closable="false"><template #default><el-button link @click="showDetail(detailId)">重新加载</el-button></template></el-alert>
        <template v-if="detail"><el-alert v-for="warning in detail.meta.warnings||[]" :key="warning" :title="warning" type="warning" :closable="false" /><article class="markdown-body" v-html="renderedDetail" /></template>
      </div>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadFile, type UploadInstance } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { UploadFilled } from '@element-plus/icons-vue'
import TemplateStructureDialog from './TemplateStructureDialog.vue'
import { createTemplateSkill, deleteTemplateSkill, getTemplateCapabilities, getTemplateSkill, getTemplateSkills, getTemplateTask, retryTemplateTask, type TemplateSkill, type TemplateTask } from '@/api/skill'

const file = ref<File>(), upload = ref<UploadInstance>(), skillName = ref(''), submitting = ref(false), submitError = ref('')
const route = useRoute()
const task = ref<TemplateTask>(), taskId = ref(''), checking = ref(false), taskError = ref('')
const rows = ref<TemplateSkill[]>([]), page = ref(1), total = ref(0), keyword = ref(''), loading = ref(false), listError = ref('')
const deletingId = ref('')
const formats = ref(['doc', 'docx', 'pdf', 'txt', 'md', 'markdown']), capabilityError = ref('')
const accept = computed(() => formats.value.map(ext => '.' + ext).join(','))
const formatHint = computed(() => `${formats.value.includes('doc') ? 'DOC、' : ''}DOCX、文字型 PDF、TXT、Markdown`)
const detailOpen = ref(false), detailLoading = ref(false), detailError = ref(''), detailId = ref('')
const detail = ref<{ meta: TemplateSkill; skillMarkdown: string }>()
const generateOpen=ref(false),structureOpen=ref(false),structureId=ref(''),structureName=ref('模板')
const markdown=new MarkdownIt({html:false,linkify:false,breaks:false}).disable('image')
const renderedDetail=computed(()=>markdown.render((detail.value?.skillMarkdown||'').replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/,'')))
function openGenerate(){clearFile();skillName.value='';generateOpen.value=true}
function openStructure(id: string, label: string) { structureId.value = id; structureName.value = label || '模板'; structureOpen.value = true }
const busy = computed(() => submitting.value || task.value?.status === 'queued' || task.value?.status === 'running')
const canRetry = computed(() => task.value?.status === 'failed' || task.value?.status === 'interrupted')
const statusLabel = computed(() => task.value ? ({ queued: '排队中', running: '提炼中', completed: '已完成', failed: '提炼失败', interrupted: '已中断' })[task.value.status] : '')
const statusType = computed(() => task.value?.status === 'completed' ? 'success' : canRetry.value ? 'danger' : 'primary')
let requestKey = '', timer: ReturnType<typeof setTimeout> | undefined, disposed = false, listVersion = 0, detailVersion = 0
// 仅保存任务号，不保存文件/凭据；按登录账号和公司隔离刷新恢复。
let storageKey = ''
try {
  const user = JSON.parse(localStorage.getItem('fijo-chat-userInfo') || '{}')
  const org = JSON.parse(localStorage.getItem('fijo-chat-organization') || 'null')
  if (user.id && (org?.id || user.orgId)) storageKey = `fijo-chat-template-task:${user.id}:${org?.id || user.orgId}`
} catch { /* 由路由处理无效登录状态 */ }
const message = (cause: unknown, fallback: string) => cause instanceof Error ? cause.message : fallback
function resetRequestKey() { requestKey = '' }
function clearFile() { file.value = undefined; upload.value?.clearFiles(); resetRequestKey(); submitError.value = '' }
function chooseFile(item: UploadFile) {
  upload.value?.clearFiles()
  if (busy.value || !item.raw) return
  file.value = undefined; resetRequestKey()
  const extension = item.name.split('.').pop()?.toLowerCase() || ''
  if (!formats.value.includes(extension)) { submitError.value = '此格式暂不支持，请选择 ' + formatHint.value; return }
  if (!item.raw.size || item.raw.size > 10 * 1024 * 1024) { submitError.value = '文件不能为空，且不能超过10MB'; return }
  file.value = item.raw; resetRequestKey(); submitError.value = ''
}
async function loadCapabilities() {
  capabilityError.value = ''
  try {
    const res = await getTemplateCapabilities()
    if (!res.success) throw new Error(res.message || '无法检查文件格式')
    if (disposed) return
    formats.value = [...new Set([...res.data.templateFormats, 'markdown'])]
    if (!res.data.officeAvailable) capabilityError.value = '服务器暂不支持 DOC 转换，请使用 DOCX、文字型 PDF、TXT 或 Markdown。'
  } catch (cause) { if (!disposed) capabilityError.value = message(cause, '无法检查文件格式，请重试') }
}
async function load() {
  const version = ++listVersion; loading.value = true; listError.value = ''
  try {
    const res = await getTemplateSkills({ keyword: keyword.value.trim() || undefined, pageNo: page.value, pageSize: 10 })
    if (!res.success) throw new Error(res.message || '模板列表加载失败')
    if (disposed || version !== listVersion) return
    rows.value = res.data.list; total.value = res.data.total
  } catch (cause) { if (!disposed && version === listVersion) { listError.value = message(cause, '模板列表加载失败'); rows.value = []; total.value = 0 } }
  finally { if (!disposed && version === listVersion) loading.value = false }
}
function search() { page.value = 1; void load() }
async function removeTemplate(row: TemplateSkill) {
  if (deletingId.value) return
  deletingId.value = row.id
  try {
    try {
      await ElMessageBox.confirm(`确定永久删除模板“${row.skillName}”吗？模板记录和提炼任务将物理删除，无法恢复。已生成的历史文档保留。`, '删除模板', { type: 'warning', confirmButtonText: '永久删除', cancelButtonText: '取消', closeOnClickModal: false })
    } catch { return }
    if (disposed) return
    const res = await deleteTemplateSkill(row.id)
    if (!res.success) throw new Error(res.message || '删除失败')
    if (disposed) return
    if (detailId.value === row.id) { ++detailVersion; detailOpen.value = false; detail.value = undefined }
    if (task.value?.skillId === row.id) {
      clearTimeout(timer); task.value = undefined; taskId.value = ''; taskError.value = ''
      try { if (storageKey) localStorage.removeItem(storageKey) } catch { /* 删除成功不依赖浏览器存储 */ }
    }
    ElMessage.success('模板已永久删除')
    await load()
    if (!listError.value && !rows.value.length && page.value > 1) { page.value = Math.max(1, Math.ceil(total.value / 10)); await load() }
  } catch (cause) {
    if (!disposed) { await load(); listError.value = message(cause, '删除失败，请重试') }
  } finally { deletingId.value = '' }
}
function remember(id: string) {
  try { if (storageKey) localStorage.setItem(storageKey, id) } catch { ElMessage.warning('浏览器无法保存任务号，请记下任务号以便查询。') }
}
function acceptTask(value: TemplateTask) {
  task.value = value; taskId.value = value.taskId; taskError.value = ''; remember(value.taskId)
}
function schedule() {
  clearTimeout(timer)
  if (!disposed && ['queued', 'running'].includes(task.value?.status || '')) timer = setTimeout(() => void checkTask(), 2500)
}
async function checkTask() {
  if (!taskId.value || checking.value || disposed) return
  const requestedId = taskId.value
  clearTimeout(timer); checking.value = true; taskError.value = ''
  try {
    const res = await getTemplateTask(requestedId)
    if (!res.success) throw new Error(res.message || '进度读取失败')
    if (disposed || requestedId !== taskId.value) return
    const completed = task.value?.status !== 'completed' && res.data.status === 'completed'
    acceptTask(res.data)
    if (completed) { page.value = 1; keyword.value = ''; void load() }
    schedule()
  } catch (cause) { if (!disposed && requestedId === taskId.value) taskError.value = message(cause, '进度读取失败，请重新获取；不会重复提交任务') }
  finally { if (!disposed) checking.value = false }
}
async function submit() {
  if (!file.value || busy.value) return
  submitting.value = true; submitError.value = ''
  // 上传响应丢失后，使用同一键再次提交，避免重复模型调用。
  requestKey ||= 'template-' + crypto.randomUUID()
  try {
    const res = await createTemplateSkill(file.value, skillName.value.trim(), requestKey)
    if (!res.success) throw new Error(res.message || '上传失败')
    remember(res.data.taskId)
    if (disposed) return
    acceptTask(res.data); file.value = undefined; skillName.value = ''; generateOpen.value = false; resetRequestKey(); schedule()
  } catch (cause) { if (!disposed) submitError.value = message(cause, '上传失败，请重试') }
  finally { if (!disposed) submitting.value = false }
}
async function retry() {
  if (!task.value || !canRetry.value || submitting.value) return
  submitting.value = true; taskError.value = ''
  try {
    const res = await retryTemplateTask(task.value.taskId, task.value.attempt)
    if (!res.success) throw new Error(res.message || '重试失败')
    if (!disposed) { acceptTask(res.data); schedule() }
  } catch (cause) { if (!disposed) taskError.value = message(cause, '重试失败，请刷新进度') }
  finally { if (!disposed) submitting.value = false }
}
async function showDetail(id: string) {
  const version = ++detailVersion; detailId.value = id; detail.value = undefined; detailError.value = ''; detailLoading.value = true; detailOpen.value = true
  try {
    const res = await getTemplateSkill(id)
    if (!res.success) throw new Error(res.message || 'Skill 加载失败')
    if (!disposed && version === detailVersion) detail.value = res.data
  } catch (cause) { if (!disposed && version === detailVersion) detailError.value = message(cause, 'Skill 加载失败') }
  finally { if (!disposed && version === detailVersion) detailLoading.value = false }
}
onMounted(() => {
  void load(); void loadCapabilities()
  try { const id = route.query.taskId || (storageKey && localStorage.getItem(storageKey)); if (typeof id === 'string' && /^[a-f0-9]{24}$/.test(id)) { taskId.value = id; void checkTask() } } catch { /* 列表仍可从服务端恢复已完成模板 */ }
})
onUnmounted(() => { disposed = true; clearTimeout(timer) })
</script>

<style scoped>
.template-page { padding: 28px; min-width: 0; }
.page-header { margin-bottom: 20px; display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap; } h1 { font-size: 24px; margin: 0; } h2 { font-size: 18px; margin: 0 0 20px; } h3 { font-size: 15px; }
.page-header p, .help, .upload-tip, small { color: var(--text-secondary); line-height: 1.7; } .help { font-size: 13px; }
.template-panel { background: var(--bg-card); padding: 24px; border-radius: 20px; margin-bottom: 20px; }
.template-upload { width: 100%; } .upload-icon { font-size: 36px; color: var(--primary-color); margin-bottom: 12px; } .upload-tip { font-size: 13px; }
.selected-file, .task-heading, .list-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; } .selected-file { justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border-color); overflow-wrap: anywhere; } .selected-file span { min-width: 0; flex: 1; }
.list-heading { justify-content: space-between; } .list-heading h2 { margin: 0; }
.el-alert { margin-bottom: 16px; } .el-pagination { margin-top: 16px; justify-content: flex-end; } .el-form--inline .el-input { width: 280px; }
.detail-content { min-height: 100px; overflow-wrap: anywhere; } pre { background: var(--bg-dark); padding: 16px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; max-height: 50vh; overflow-y: auto; }
@media (max-width: 700px) { .template-page { padding: 12px 4px; } .template-panel { padding: 16px; } .el-form--inline .el-form-item { margin-right: 0; display: block; } .el-form--inline .el-input { width: 100%; } .el-pagination { justify-content: flex-start; } }
.detail-content{max-height:65vh;overflow:auto;padding-right:12px}.markdown-body{font-size:15px;line-height:1.85;overflow-wrap:anywhere}.markdown-body :deep(h1){font-size:26px;margin:0 0 24px}.markdown-body :deep(h2){font-size:21px;margin:32px 0 16px;border-bottom:1px solid var(--border-color);padding-bottom:10px}.markdown-body :deep(h3){font-size:17px;margin:24px 0 12px}.markdown-body :deep(p){margin:10px 0}.markdown-body :deep(ul),.markdown-body :deep(ol){padding-left:24px}.markdown-body :deep(table){display:block;overflow:auto;border-collapse:collapse;margin:16px 0}.markdown-body :deep(th),.markdown-body :deep(td){border:1px solid var(--border-color);padding:10px 14px;text-align:left}.markdown-body :deep(th){background:var(--bg-dark)}.el-tag{margin:2px 6px 2px 0}
</style>
