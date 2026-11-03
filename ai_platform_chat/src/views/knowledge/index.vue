<template>
  <section class="knowledge-workspace">
    <header class="workspace-header">
      <div class="heading"><el-icon><Files /></el-icon><h1>知识库</h1></div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建我的知识库</el-button>
    </header>
    <div class="library-panel">
      <el-form inline class="library-filters" @submit.prevent="searchLibraries">
        <el-form-item><el-input v-model="keyword" clearable placeholder="搜索知识库名称或备注" aria-label="搜索知识库名称或备注" @clear="searchLibraries" /></el-form-item>
        <el-form-item>
          <el-select v-model="scopeType" clearable placeholder="全部类型" aria-label="知识库类型" @change="searchLibraries">
            <el-option label="公司公有" :value="1" />
            <el-option label="公司私有" :value="2" />
            <el-option label="个人" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item><el-button native-type="submit" :loading="loading">查询</el-button><el-button :disabled="loading" @click="loadLibraries">刷新</el-button></el-form-item>
      </el-form>
      <el-alert v-if="listError" :title="listError" type="error" show-icon :closable="false"><template #default><el-button link @click="loadLibraries">重新加载</el-button></template></el-alert>
      <el-table v-loading="loading" :data="libraries" row-key="id" empty-text="暂无可查看的知识库">
        <el-table-column label="编号" width="90"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
        <el-table-column label="知识库" min-width="180" show-overflow-tooltip><template #default="{ row }"><el-button link type="primary" @click="openLibrary(row, row.scopeType === 3)">{{ row.tenantName }}</el-button></template></el-table-column>
        <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip><template #default="{ row }">{{ row.remarks || '—' }}</template></el-table-column>
        <el-table-column label="类型" width="120"><template #default="{ row }"><el-tag :type="row.scopeType === 3 ? 'primary' : row.scopeType === 2 ? 'warning' : 'success'">{{ typeLabels[row.scopeType as 1 | 2 | 3] }}</el-tag></template></el-table-column>
        <el-table-column label="数据量" width="100"><template #default="{ row }">{{ row.knowledgeCount }} 条</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled === 1 ? 'success' : 'info'">{{ row.enabled === 1 ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" min-width="330"><template #default="{ row }">
          <div class="library-actions">
            <el-button link type="primary" @click="openLibrary(row, row.scopeType === 3)">查看资料</el-button>
            <el-button link type="primary" :aria-label="`查看${row.tenantName}的知识图谱`" @click="openGraph(row)">查看知识图谱</el-button>
            <template v-if="row.scopeType === 3"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="removeLibrary(row)">删除</el-button></template>
          </div>
        </template></el-table-column>
      </el-table>
      <el-pagination v-if="total" v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" background @current-change="loadLibraries" />
    </div>

    <el-dialog v-model="editorOpen" :title="editingId ? `编辑知识库 #${editingId}` : '新建我的知识库'" width="min(520px, 94vw)" :close-on-click-modal="!saving">
      <el-form label-width="88px" @submit.prevent="saveLibrary">
        <el-form-item label="名称" required><el-input v-model="form.tenantName" maxlength="255" show-word-limit /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remarks" type="textarea" :rows="3" maxlength="500" show-word-limit /></el-form-item>
        <el-form-item v-if="editingId" label="状态"><el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <el-alert v-if="formError" :title="formError" type="error" show-icon :closable="false" />
      <template #footer>
        <el-button :disabled="saving" @click="editorOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveLibrary">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="activeLibrary ? `${activeLibrary.tenantName} #${activeLibrary.id}` : '知识资料'" size="min(760px, 100vw)">
      <div class="folder-breadcrumb"><el-button link @click="enterFolder(0)">知识库根层</el-button><template v-for="item in folderScope?.breadcrumbs || []" :key="item.id"><span>/</span><el-button link @click="enterFolder(item.id)">{{ item.folderName }}</el-button></template></div>
      <div class="folder-actions"><el-button v-if="canEditActive" :disabled="folderLoading||activeLibrary?.enabled!==1" @click="editFolder()">新建文档</el-button></div>
      <el-alert v-if="folderError" :title="folderError" type="error" :closable="false"><template #default><el-button link @click="enterFolder(folderId)">重新加载文档</el-button></template></el-alert>
      <div v-loading="folderLoading" class="folder-list"><div v-for="item in documentEntries" :key="item.id" class="folder-row"><el-button link type="primary" class="folder-entry" :disabled="folderLoading" :aria-label="`进入文档：${item.folderName}`" @click="enterFolder(item.id)"><span class="folder-entry-name">{{ item.folderName }}</span><span class="folder-enter-label">进入文档 →</span></el-button><div v-if="canEditActive"><el-button link @click="editFolder(item)">重命名</el-button><el-button link type="danger" @click="removeFolder(item)">删除空文档</el-button></div></div></div>
      <p class="upload-tip">点击文档名称进入，图谱与问答包含本文档及全部下级文件。</p>
      <div class="detail-toolbar">
        <span>{{ recordTotal }} 个文档</span>
        <el-button v-if="activeLibrary" :disabled="folderLoading" @click="openFolderGraph">查看知识图谱</el-button>
        <el-button v-if="canEditActive" :loading="syncing" @click="repairSync">修复同步</el-button>
      </div>
      <el-alert v-if="detailError" :title="detailError" type="error" show-icon :closable="false" />
      <el-alert v-if="uploadWarnings.length" :title="uploadWarnings.join('；')" type="warning" show-icon @close="uploadWarnings = []" />
      <div v-if="canEditActive" class="detail-create">
        <el-upload v-model:file-list="fileList" drag multiple :auto-upload="false" :limit="10" accept=".docx,.xlsx,.xls" :disabled="activeLibrary?.enabled !== 1">
          <div>拖入 Word/Excel，或点击选择</div>
          <template #tip><div class="upload-tip">最多 10 个文件，单个不超过 10 MB。保留原文件并同步向量。解析文字和表格，图片、图表暂未识别。</div></template>
        </el-upload>
        <el-button type="primary" :loading="uploading" :disabled="activeLibrary?.enabled !== 1" @click="uploadFiles">上传并同步</el-button>
        <el-input v-model="recordForm.title" maxlength="255" placeholder="资料标题" aria-label="资料标题" />
        <el-input v-model="recordForm.content" type="textarea" :rows="4" maxlength="60000" placeholder="或手动写入知识正文" aria-label="知识正文" />
        <el-button :loading="recordSaving" :disabled="activeLibrary?.enabled !== 1" @click="addRecord">保存手动资料</el-button>
      </div>
      <el-empty v-if="!detailLoading && !records.length" description="当前层级暂无文档" />
      <article v-for="record in records" :key="record.id" class="record-row">
        <div><el-button link type="primary" :loading="openingRecordId===record.id" :disabled="!!openingRecordId" @click="openDocument(record.id)">{{ record.title || '未命名文档' }}</el-button><small v-if="!record.fileUrl">手动录入</small></div>
        <div class="row-actions">
          <el-button v-if="canEditActive" link type="primary" @click="openMove(record)">移动</el-button>
          <el-button link type="primary" :loading="downloadingId === record.id" @click="downloadRecord(record)">下载</el-button>
          <el-button v-if="canEditActive" link type="primary" :disabled="activeLibrary?.enabled !== 1" @click="openReplace(record)">编辑</el-button>
          <el-button v-if="canEditActive" link type="danger" :loading="deletingRecordId === record.id" @click="removeRecord(record)">删除</el-button>
        </div>
      </article>
      <el-pagination v-if="recordTotal > pageSize" v-model:current-page="recordPage" :page-size="pageSize" :total="recordTotal" layout="total, prev, pager, next" background @current-change="loadRecords" />
    </el-drawer>
    <el-dialog v-model="replaceOpen" title="编辑文档" width="min(720px, 94vw)" :close-on-click-modal="!replacingNow">
      <div v-loading="editLoading">
        <p class="upload-tip">当前文档：{{ replacing?.title || '未命名文档' }}。保存后会删除原来的段落和向量，再按新内容用原来的方式重新切分并写入。</p>
        <el-input v-model="editContent" type="textarea" :autosize="{ minRows: 12, maxRows: 20 }" />
      </div>
      <template #footer>
        <el-button :disabled="replacingNow" @click="replaceOpen = false">取消</el-button>
        <el-button type="primary" :loading="replacingNow" :disabled="editLoading" @click="submitEditContent">保存</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="moveOpen" title="移动文档" width="min(560px,94vw)" :close-on-click-modal="false" :show-close="!moving" :close-on-press-escape="!moving"><el-select v-model="moveTarget" filterable :disabled="moving" style="width:100%" placeholder="选择目标文档"><el-option label="知识库根层" :value="0" /><el-option v-for="item in folderScope?.allFolders || []" :key="item.id" :label="folderLabel(item.id)" :value="item.id" /></el-select><el-alert v-if="moveError" :title="moveError" type="error" :closable="false" /><template #footer><el-button :disabled="moving" @click="moveOpen=false">取消</el-button><el-button type="primary" :loading="moving" @click="submitMove">确定移动</el-button></template></el-dialog>
    <KnowledgeGraphDialog v-if="graphLibrary" v-model="graphOpen" :tenant-id="graphLibrary.id" :folder-id="graphFolderId" :name="graphScopeName || graphLibrary.tenantName" :can-build="graphLibrary.scopeType === 3" @open-document="openDocument" @manage-documents="manageGraphDocuments" @add-documents="manageGraphDocuments" />


  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadUserFile } from 'element-plus'
import { Files, Plus } from '@element-plus/icons-vue'
import KnowledgeGraphDialog from './KnowledgeGraphDialog.vue'
import {
  getKnowledgeFolders,saveKnowledgeFolder,deleteKnowledgeFolder,moveKnowledgeDocuments,openKnowledgeDocument,
  type KnowledgeFolder,type KnowledgeFolderScope,
  createKnowledgeRecord,
  createPersonalTenant,
  deleteKnowledgeRecord,
  deletePersonalTenant,
  downloadKnowledgeRecord,
  getKnowledgeDocument,
  getTenantRecords,
  saveKnowledgeDocument,
  getVisibleTenantPage,
  syncTenantRecords,
  updatePersonalTenant,
  uploadKnowledgeFiles,
  type KnowledgeRecord,
  type UsableTenant
} from '@/api/knowledge'

const pageSize = 10
const listError = ref('')
const libraries = ref<UsableTenant[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const scopeType = ref<1 | 2 | 3>()
const loading = ref(false)
const typeLabels: Record<1 | 2 | 3, string> = { 1: '公司公有', 2: '公司私有', 3: '个人' }
let listRequest = 0
const editorOpen = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formError = ref('')
const form = ref({ tenantName: '', remarks: '', enabled: 1 as 0 | 1 })
const detailOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const activeLibrary = ref<UsableTenant | null>(null)
const canEditActive = ref(false)
const graphOpen = ref(false)
const graphLibrary = ref<UsableTenant | null>(null)
const graphFolderId=ref(0),graphScopeName=ref('')
const folderId=ref(0),folderScope=ref<KnowledgeFolderScope>(),folderLoading=ref(false),folderError=ref('')
let folderVersion=0,recordsVersion=0,foldersDisposed=false
const moveOpen=ref(false),moveTarget=ref(0),moving=ref(false),moveError=ref(''),moveRecord=ref<KnowledgeRecord>()
const openingRecordId=ref<number>()
const documentEntries=computed(()=>(folderScope.value?.children||[]).filter(item=>!item.documentKey))
async function openDocument(recordId:number){
  if(!graphLibrary.value&&!activeLibrary.value||openingRecordId.value)return
  const library=graphOpen.value?graphLibrary.value:activeLibrary.value
  if(!library)return
  const version=folderVersion;openingRecordId.value=recordId
  try{const res=await openKnowledgeDocument(library.id,recordId);if(!res.success)throw new Error(res.message||'文档打开失败');if(version!==folderVersion||foldersDisposed)return;if(activeLibrary.value?.id!==library.id){activeLibrary.value=library;canEditActive.value=library.scopeType===3}detailOpen.value=true;await enterFolder(res.data.id)}
  catch(cause){if(!foldersDisposed)ElMessage.error(cause instanceof Error?cause.message:'文档打开失败')}
  finally{openingRecordId.value=undefined}
}
async function manageGraphDocuments(){
  const library=graphLibrary.value,target=graphFolderId.value
  if(!library)return
  graphOpen.value=false
  if(activeLibrary.value?.id===library.id&&folderId.value===target){detailOpen.value=true;return}
  activeLibrary.value=library;canEditActive.value=library.scopeType===3;detailOpen.value=true;await enterFolder(target)
}
function folderLabel(id:number){const nodes=new Map((folderScope.value?.allFolders||[]).map(item=>[item.id,item]));const parts:string[]=[];const seen=new Set<number>();while(id&&nodes.has(id)&&!seen.has(id)){seen.add(id);const item=nodes.get(id)!;parts.unshift(item.folderName);id=item.parentId}return parts.join(' / ').slice(-220)}
function openFolderGraph(){if(!activeLibrary.value)return;graphLibrary.value=activeLibrary.value;graphFolderId.value=folderId.value;graphScopeName.value=[activeLibrary.value.tenantName,...(folderScope.value?.breadcrumbs||[]).map(item=>item.folderName)].join(' / ');graphOpen.value=true}
async function enterFolder(id:number){
  if(!activeLibrary.value)return
  const tenantId=activeLibrary.value.id,version=++folderVersion;++recordsVersion;folderLoading.value=true;folderError.value='';graphOpen.value=false;moveOpen.value=false
  try{const res=await getKnowledgeFolders(tenantId,id);if(!res.success)throw new Error(res.message||'文档加载失败');if(version!==folderVersion||foldersDisposed||activeLibrary.value?.id!==tenantId)return;folderId.value=id;folderScope.value=res.data;recordPage.value=1;records.value=[];await loadRecords()}
  catch(cause){if(version===folderVersion&&!foldersDisposed)folderError.value=cause instanceof Error?cause.message:'文档加载失败'}
  finally{if(version===folderVersion)folderLoading.value=false}
}
async function editFolder(item?:KnowledgeFolder){
  if(!activeLibrary.value||!canEditActive.value)return
  const tenantId=activeLibrary.value.id,version=folderVersion,parentId=item?.parentId??folderId.value
  try{const {value}=await ElMessageBox.prompt('文档权限继承当前知识库。',item?'重命名文档':'新建文档',{inputValue:item?.folderName||'',inputValidator:value=>!!value?.trim()&&value.trim().length<=100&&!/[\\/\x00]/.test(value)||'请输入1至100字文档名称，不能包含斜杠',confirmButtonText:'保存',cancelButtonText:'取消'});if(version!==folderVersion||foldersDisposed)return;const res=await saveKnowledgeFolder(tenantId,{folderName:value.trim(),parentId},item?.id);if(!res.success)throw new Error(res.message||'保存失败');await enterFolder(folderId.value)}catch(cause){if(cause!=='cancel'&&cause!=='close')ElMessage.error(cause instanceof Error?cause.message:'文档保存失败')}
}
async function removeFolder(item:KnowledgeFolder){
  if(!activeLibrary.value||!canEditActive.value)return
  const tenantId=activeLibrary.value.id,version=folderVersion
  try{await ElMessageBox.confirm(`确定永久删除空文档“${item.folderName}”吗？有下级或资料时不能删除。`,'删除空文档',{type:'warning',confirmButtonText:'删除',cancelButtonText:'取消'});if(version!==folderVersion||foldersDisposed)return;const res=await deleteKnowledgeFolder(tenantId,item.id);if(!res.success)throw new Error(res.message||'删除失败');await enterFolder(folderId.value)}catch(cause){if(cause!=='cancel'&&cause!=='close')ElMessage.error(cause instanceof Error?cause.message:'删除失败')}
}
function openMove(row:KnowledgeRecord){moveRecord.value=row;moveTarget.value=folderId.value;moveError.value='';moveOpen.value=true}
async function submitMove(){if(!activeLibrary.value||!moveRecord.value||moving.value)return;const tenantId=activeLibrary.value.id,version=folderVersion;moving.value=true;moveError.value='';try{const res=await moveKnowledgeDocuments(tenantId,[moveRecord.value.id],moveTarget.value);if(!res.success)throw new Error(res.message||'移动失败');if(version!==folderVersion||foldersDisposed)return;moveOpen.value=false;await loadRecords()}catch(cause){if(version===folderVersion)moveError.value=cause instanceof Error?cause.message:'移动失败'}finally{moving.value=false}}
onBeforeUnmount(()=>{foldersDisposed=true;++folderVersion;++recordsVersion})
function openGraph(item: UsableTenant) {
  graphFolderId.value=0;graphScopeName.value=''
  graphLibrary.value = item
  graphOpen.value = true
}
const records = ref<KnowledgeRecord[]>([])
const recordTotal = ref(0)
const recordPage = ref(1)
const recordForm = ref({ title: '', content: '' })
const recordSaving = ref(false)
const fileList = ref<UploadUserFile[]>([])
const uploading = ref(false)
const uploadWarnings = ref<string[]>([])
const syncing = ref(false)
const deletingRecordId = ref<number | null>(null)
const downloadingId = ref<number | null>(null)
const replaceOpen = ref(false)
const replacingNow = ref(false)
const editLoading = ref(false)
const replacing = ref<KnowledgeRecord | null>(null)
const editContent = ref('')

async function openReplace(record: KnowledgeRecord) {
  if (!activeLibrary.value) return
  replacing.value = record
  editContent.value = ''
  replaceOpen.value = true
  editLoading.value = true
  try {
    const response = await getKnowledgeDocument(activeLibrary.value.id, record.id)
    if (!response.success) throw new Error(response.message || '文档内容加载失败')
    editContent.value = response.data.content || ''
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '文档内容加载失败'
    replaceOpen.value = false
  } finally {
    editLoading.value = false
  }
}

async function submitEditContent() {
  if (!activeLibrary.value || !replacing.value) return
  const content = editContent.value.trim()
  if (!content) { ElMessage.warning('文档内容不能为空'); return }
  replacingNow.value = true
  detailError.value = ''
  try {
    const response = await saveKnowledgeDocument(activeLibrary.value.id, replacing.value.id, content)
    if (!response.success) throw new Error(response.message || '保存失败')
    replaceOpen.value = false
    ElMessage.success(response.message || '已用新内容覆盖，原数据和向量已删除')
    await loadRecords()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    replacingNow.value = false
  }
}

async function loadLibraries() {
  const currentRequest = ++listRequest
  loading.value = true
  listError.value = ''
  try {
    const response = await getVisibleTenantPage({ keyword: keyword.value.trim() || undefined, scopeType: scopeType.value || undefined, pageNo: page.value, pageSize })
    if (currentRequest !== listRequest) return
    if (!response.success) throw new Error(response.message || '知识库加载失败')
    libraries.value = response.data.list
    total.value = response.data.total
  } catch (error) {
    if (currentRequest !== listRequest) return
    libraries.value = []
    total.value = 0
    listError.value = error instanceof Error ? error.message : '知识库加载失败'
  } finally {
    if (currentRequest === listRequest) loading.value = false
  }
}
function searchLibraries() { page.value = 1; void loadLibraries() }

function openCreate() {
  editingId.value = null
  form.value = { tenantName: '', remarks: '', enabled: 1 }
  formError.value = ''
  editorOpen.value = true
}

function openEdit(item: UsableTenant) {
  editingId.value = item.id
  form.value = { tenantName: item.tenantName, remarks: item.remarks || '', enabled: item.enabled }
  formError.value = ''
  editorOpen.value = true
}

async function saveLibrary() {
  const tenantName = form.value.tenantName.trim()
  if (!tenantName) { formError.value = '请输入知识库名称'; return }
  saving.value = true
  formError.value = ''
  try {
    const payload = { tenantName, remarks: form.value.remarks.trim() }
    const response = editingId.value
      ? await updatePersonalTenant({ id: editingId.value, ...payload, enabled: form.value.enabled })
      : await createPersonalTenant(payload)
    if (!response.success) throw new Error(response.message || '保存失败')
    editorOpen.value = false
    if (!editingId.value) { page.value = 1; keyword.value = ''; scopeType.value = undefined }
    ElMessage.success(response.message || '知识库已保存')
    await loadLibraries()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function removeLibrary(item: UsableTenant) {
  try {
    await ElMessageBox.confirm(`确定删除知识库“${item.tenantName}”（#${item.id}）吗？库里还有资料时请先删除资料。`, '删除知识库', { type: 'warning' })
  } catch { return }
  try {
    const response = await deletePersonalTenant(item.id)
    if (!response.success) throw new Error(response.message || '删除失败')
    if (libraries.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success(response.message || '知识库已删除')
    await loadLibraries()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

async function loadRecords() {
  if (!activeLibrary.value) return
  const version=++recordsVersion,tenantId=activeLibrary.value.id
  detailLoading.value = true
  detailError.value = ''
  try {
    const response = await getTenantRecords(tenantId, { pageNo: recordPage.value, pageSize, folderId:folderId.value })
    if(version!==recordsVersion||foldersDisposed||activeLibrary.value?.id!==tenantId)return
    if (!response.success) throw new Error(response.message || '资料加载失败')
    records.value = response.data.list
    recordTotal.value = response.data.total
  } catch (error) {
    if(version===recordsVersion)detailError.value = error instanceof Error ? error.message : '资料加载失败'
  } finally {
    if(version===recordsVersion)detailLoading.value = false
  }
}

async function openLibrary(item: UsableTenant, editable: boolean) {
  ++folderVersion;++recordsVersion;folderScope.value=undefined;folderId.value=0
  uploadWarnings.value = []
  activeLibrary.value = item
  canEditActive.value = editable
  graphOpen.value = false
  detailOpen.value = true
  recordPage.value = 1
  records.value = []
  recordForm.value = { title: '', content: '' }
  fileList.value = []
  await enterFolder(0)
}

async function uploadFiles() {
  if (!activeLibrary.value) return
  const files = fileList.value.flatMap(item => item.raw ? [item.raw] : [])
  if (!files.length) { detailError.value = '请选择要上传的 Word 或 Excel 文件'; return }
  uploading.value = true
  detailError.value = ''
  try {
    const response = await uploadKnowledgeFiles(activeLibrary.value.id, files,folderId.value)
    if (!response.success) throw new Error(response.message || '资料上传失败')
    uploadWarnings.value = response.data.warnings || []
    fileList.value = []
    recordPage.value = 1
    ElMessage.success(response.message || '文件已上传并同步')
    await loadRecords()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '资料上传失败'
  } finally {
    uploading.value = false
  }
}

async function addRecord() {
  if (!activeLibrary.value) return
  const title = recordForm.value.title.trim()
  const content = recordForm.value.content.trim()
  if (!title || !content) { detailError.value = '请填写资料标题和正文'; return }
  recordSaving.value = true
  detailError.value = ''
  try {
    const response = await createKnowledgeRecord(activeLibrary.value.id, { title, content,folderId:folderId.value })
    if (!response.success) throw new Error(response.message || '资料保存失败')
    recordForm.value = { title: '', content: '' }
    recordPage.value = 1
    ElMessage.success('资料已写入并同步')
    await loadRecords()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '资料保存失败'
  } finally {
    recordSaving.value = false
  }
}

async function removeRecord(record: KnowledgeRecord) {
  if (!activeLibrary.value) return
  try {
    await ElMessageBox.confirm(`确定删除“${record.title || '未命名文档'}”吗？`, '删除文档', { type: 'warning' })
  } catch { return }
  deletingRecordId.value = record.id
  try {
    const response = await deleteKnowledgeRecord(record.id, activeLibrary.value.id)
    if (!response.success) throw new Error(response.message || '资料删除失败')
    if (records.value.length === 1 && recordPage.value > 1) recordPage.value -= 1
    ElMessage.success(response.message || '资料已删除')
    await loadRecords()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '资料删除失败')
  } finally {
    deletingRecordId.value = null
  }
}

async function repairSync() {
  if (!activeLibrary.value) return
  syncing.value = true
  detailError.value = ''
  try {
    const response = await syncTenantRecords(activeLibrary.value.id)
    if (!response.success) throw new Error(response.message || '同步修复失败')
    ElMessage.success(response.message || '同步修复完成')
    await loadRecords()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '同步修复失败'
  } finally {
    syncing.value = false
  }
}

async function downloadRecord(record: KnowledgeRecord) {
  downloadingId.value = record.id
  try { await downloadKnowledgeRecord(record.id, record.fileUrl || record.title) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '下载失败') }
  finally { downloadingId.value = null }
}

onMounted(loadLibraries)
</script>

<style scoped>
.folder-breadcrumb{display:flex;align-items:center;gap:8px;overflow-x:auto;white-space:nowrap;padding:8px 0}.folder-actions{display:flex;gap:8px;margin:12px 0}.folder-list{max-height:230px;overflow:auto}.folder-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--border-color,#e5e7eb)}
.folder-entry{flex:1;min-width:0;min-height:40px;padding:8px 12px;justify-content:flex-start;text-align:left}.folder-entry :deep(>span){display:flex;align-items:center;gap:12px;width:100%;min-width:0}.folder-entry-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.folder-enter-label{flex-shrink:0;font-size:13px}.folder-entry:hover,.folder-entry:focus-visible{background:var(--el-color-primary-light-9);border-radius:6px}.folder-row>div{flex-shrink:0}
.knowledge-workspace { min-width: 0; padding: 28px; }
.workspace-header, .record-row, .row-actions, .detail-create, .detail-toolbar { display: flex; gap: 12px; }
.workspace-header, .detail-toolbar { align-items: center; justify-content: space-between; margin-bottom: 18px; }
.heading { display: flex; align-items: center; gap: 8px; }
.heading h1 { margin: 0; font-size: 22px; }
.library-panel { padding: 24px; border-radius: 20px; background: var(--bg-card); min-width: 0; }
.library-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; }
.library-filters :deep(.el-input) { width: 280px; }
.library-filters :deep(.el-select) { width: 180px; }
.record-row { align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border-color); }
.record-row div { min-width: 0; }
.record-row small, .upload-tip { display: block; margin: 4px 0 0; color: var(--text-secondary); }
.detail-create { flex-direction: column; margin-bottom: 16px; }
.el-pagination { justify-content: flex-end; margin-top: 12px; }
pre { white-space: pre-wrap; word-break: break-word; }
@media (max-width: 800px) { .knowledge-workspace { padding: 16px; } .workspace-header { flex-wrap: wrap; } .library-panel { padding: 16px; } .library-filters :deep(.el-input), .library-filters :deep(.el-select) { width: 100%; } .library-filters :deep(.el-form-item) { display: block; margin-right: 0; } .record-row, .detail-toolbar { display: grid; grid-template-columns: 1fr; } }
</style>
