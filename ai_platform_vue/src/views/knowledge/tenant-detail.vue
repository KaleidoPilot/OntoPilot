<template>
  <div class="knowledge-page">
    <el-card class="knowledge-card" shadow="never">
      <template #header>
        <div class="page-header">
          <div class="title-area">
            <h2>{{ folderScope?.breadcrumbs.at(-1)?.folderName || tenant?.tenantName || '知识库文档' }}</h2>
          </div>
          <div class="header-actions">
            <el-button :disabled="folderLoading||tenant?.enabled!==1" @click="editFolder()">新建文档</el-button>
            <el-button :icon="ArrowLeft" :disabled="folderLoading" @click="returnToParent">{{ folderId ? '返回上一级' : '返回知识库列表' }}</el-button>
            <el-button @click="graphOpen = true">查看知识图谱</el-button>
            <el-button :icon="Refresh" :loading="syncing" @click="syncRecords">同步</el-button>
            <el-button type="primary" :icon="Upload" @click="openCreateDialog">{{ folderId ? '添加下级文件' : '上传文档' }}</el-button>
          </div>
        </div>
      </template>

      <div class="folder-breadcrumb"><el-button link :disabled="folderLoading" @click="enterFolder(0)">{{ tenant?.tenantName || '知识库根层' }}</el-button><template v-for="item in folderScope?.breadcrumbs || []" :key="item.id"><span>/</span><el-button link :disabled="folderLoading" @click="enterFolder(item.id)">{{ item.folderName }}</el-button></template></div>
      <el-alert v-if="folderError" :title="folderError" type="error" :closable="false"><template #default><el-button link @click="enterFolder(folderId)">重新加载文档</el-button></template></el-alert>
      <div v-loading="folderLoading" class="folder-list"><div v-for="item in documentEntries" :key="item.id" class="folder-row"><el-button link type="primary" class="folder-entry" :disabled="folderLoading" :aria-label="`进入文档：${item.folderName}`" @click="enterFolder(item.id)"><span class="folder-entry-name">{{ item.folderName }}</span><span class="folder-enter-label">进入文档 →</span></el-button><div><el-button link @click="editFolder(item)">重命名</el-button><el-button link type="danger" @click="removeFolder(item)">删除空文档</el-button></div></div></div>
      <p class="folder-hint">点击文档名称进入，查看图谱按钮用于查看本文档与全部下级文件的关系。</p>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          class="record-search"
          clearable
          :prefix-icon="Search"
          placeholder="搜索文档名或正文"
          aria-label="搜索知识库数据"
        />
        <el-select
          v-model="syncStatus"
          class="status-filter"
          clearable
          placeholder="全部同步状态"
          aria-label="按同步状态筛选知识数据"
        >
          <el-option label="已同步" value="synced" />
          <el-option label="待处理" value="pending" />
        </el-select>
      </div>

      <el-alert v-if="listError" class="list-alert" :title="listError" type="error" show-icon :closable="false" />
      <el-alert v-if="uploadWarnings.length" class="list-alert" :title="uploadWarnings.join('；')" type="warning" show-icon @close="uploadWarnings = []" />

      <div class="table-area">
        <el-table v-loading="listLoading" :data="recordList" row-key="id" size="large">
          <el-table-column label="文档" min-width="320" show-overflow-tooltip>
            <template #default="{ row }">
              <el-button link type="primary" class="record-title" :loading="openingRecordId===row.id" :disabled="!!openingRecordId" @click="openDocument(row.id)">{{ row.title || '未命名文档' }}</el-button>
            </template>
          </el-table-column>
        <el-table-column label="版本" width="100" align="center">
          <template #default="{ row }">
            <span class="version-cell">{{ row.version }}</span>
          </template>
        </el-table-column>
          <el-table-column label="同步状态" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="syncMeta(row.syncStatus).type" effect="light">
                {{ syncMeta(row.syncStatus).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="使用状态" width="110" align="center">
            <template #default="{ row }">{{ row.enabled === 1 ? '已启用' : '已停用' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="280" align="center" fixed="right">
            <template #default="{ row }">
              <div class="action-buttons">
                <el-button link type="primary" @click="openMove(row)">移动</el-button>
                <el-button link type="primary" :loading="downloadingId === row.id" @click="downloadRecord(row)">下载</el-button>
                <el-button link type="primary" :icon="Edit" @click="openReplace(row)">编辑</el-button>
                <el-button link type="danger" :icon="Delete" :loading="deletingId === row.id" @click="confirmDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="keyword.trim() || syncStatus ? '没有符合条件的文档' : '当前层级暂无文档'" :image-size="92" />
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
          @current-change="loadRecords"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="uploadVisible"
      title="新增知识库资料"
      width="640px"
      :close-on-click-modal="false"
      @closed="resetCreateDialog"
    >
      <el-tabs v-model="createMode" class="record-create-tabs" stretch>
        <el-tab-pane label="上传文件" name="file">
          <el-upload
            v-model:file-list="fileList"
            drag
            multiple
            :auto-upload="false"
            :limit="10"
            accept=".docx,.xlsx,.xls"
          >
            <el-icon class="upload-icon"><Upload /></el-icon>
            <div>拖入 Word/Excel 文件，或点击选择</div>
            <template #tip>
              <div class="upload-tip">最多 10 个文件，单个不超过 10 MB。保留原文件并同步向量。解析文字和表格，图片、图表暂未识别。</div>
            </template>
          </el-upload>
        </el-tab-pane>
        <el-tab-pane label="手动录入" name="manual">
          <el-form label-position="top" class="manual-record-form">
            <el-form-item label="资料标题" required>
              <el-input
                v-model="manualForm.title"
                maxlength="255"
                show-word-limit
                clearable
                placeholder="请输入资料标题"
              />
            </el-form-item>
            <el-form-item label="知识正文" required>
              <el-input
                v-model="manualForm.content"
                type="textarea"
                :autosize="{ minRows: 10, maxRows: 18 }"
                maxlength="60000"
                show-word-limit
                resize="vertical"
                placeholder="请输入需要写入知识库的完整内容"
              />
            </el-form-item>
            <div class="manual-record-tip">保存后会立即写入知识库并同步向量。</div>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitCreate">
          {{ createMode === 'file' ? '上传并同步' : '保存并同步' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="replaceVisible" title="编辑文档" width="720px" :close-on-click-modal="false">
      <div v-loading="editLoading">
        <p class="manual-record-tip">当前文档：{{ replacing?.title || '未命名文档' }}。保存后会删除原来的段落和向量，再按新内容用原来的方式重新切分并写入。</p>
        <el-input v-model="editContent" type="textarea" :autosize="{ minRows: 14, maxRows: 22 }" />
      </div>
      <template #footer>
        <el-button :disabled="replacingNow" @click="replaceVisible = false">取消</el-button>
        <el-button type="primary" :loading="replacingNow" :disabled="editLoading" @click="submitEditContent">保存</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="moveOpen" title="移动文档" width="min(560px,94vw)" :close-on-click-modal="false" :show-close="!moving" :close-on-press-escape="!moving"><p>选择目标文档，整份文档会一起移动。</p><el-select v-model="moveTarget" filterable style="width:100%" :disabled="moving" placeholder="选择目标文档"><el-option label="知识库根层" :value="0" /><el-option v-for="item in folderScope?.allFolders || []" :key="item.id" :label="folderLabel(item.id)" :value="item.id" /></el-select><el-alert v-if="moveError" :title="moveError" type="error" :closable="false" /><template #footer><el-button :disabled="moving" @click="moveOpen=false">取消</el-button><el-button type="primary" :loading="moving" :disabled="moveTarget===folderId" @click="submitMove">确定移动</el-button></template></el-dialog>
    <KnowledgeGraphDialog v-model="graphOpen" :tenant-id="tenantId" :folder-id="folderId" :name="graphName" :can-build="true" @open-document="openDocument" @manage-documents="graphOpen=false" @add-documents="graphOpen=false;openCreateDialog()" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ArrowLeft, Delete, Edit, Refresh, Search, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type TagProps, type UploadUserFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import KnowledgeGraphDialog from './KnowledgeGraphDialog.vue'

import {
  getKnowledgeFolders, saveKnowledgeFolder, deleteKnowledgeFolder, moveKnowledgeDocuments, openKnowledgeDocument,
  type KnowledgeFolder, type KnowledgeFolderScope,
  createKnowledgeRecord,
  deleteKnowledgeRecord,
  downloadKnowledgeRecord,
  getKnowledgeDocument,
  getTenantRecordPage,
  saveKnowledgeDocument,
  syncTenantRecords,
  uploadTenantRecords,
  type KnowledgeRecord,
  type KnowledgeTenant
} from '@/api/knowledge'


const route = useRoute()
const router = useRouter()
const tenantId = Number(route.params.tenantId)
const tenant = ref<KnowledgeTenant | null>(null)
const graphOpen = ref(false)
const folderId=ref(0),folderScope=ref<KnowledgeFolderScope>(),folderLoading=ref(false),folderError=ref('')
let folderVersion=0,folderDisposed=false
const graphName=computed(()=>[tenant.value?.tenantName||'知识库',...(folderScope.value?.breadcrumbs||[]).map(item=>item.folderName)].join(' / '))
const moveOpen=ref(false),moveTarget=ref(0),moving=ref(false),moveError=ref(''),moveRecord=ref<KnowledgeRecord>()
const openingRecordId=ref<number>()
const documentEntries=computed(()=>(folderScope.value?.children||[]).filter(item=>!item.documentKey))
async function openDocument(recordId:number){
  if(openingRecordId.value)return
  const version=folderVersion;openingRecordId.value=recordId
  try{const res=await openKnowledgeDocument(tenantId,recordId);if(!res.success)throw new Error(res.message||'文档打开失败');if(version!==folderVersion||folderDisposed)return;await enterFolder(res.data.id)}
  catch(cause){if(!folderDisposed)ElMessage.error(cause instanceof Error?cause.message:'文档打开失败')}
  finally{openingRecordId.value=undefined}
}
function folderLabel(id:number){const nodes=new Map((folderScope.value?.allFolders||[]).map(item=>[item.id,item]));const parts:string[]=[];const seen=new Set<number>();while(id&&nodes.has(id)&&!seen.has(id)){seen.add(id);const item=nodes.get(id)!;parts.unshift(item.folderName);id=item.parentId}return parts.join(' / ').slice(-220)}
async function returnToParent(){
  if(folderLoading.value)return
  if(!folderId.value){await router.push('/knowledge');return}
  const current=folderScope.value?.breadcrumbs.at(-1)
  if(!current){ElMessage.error('上级文档信息未加载，请重新加载文档');return}
  await enterFolder(current.parentId)
}
async function enterFolder(id:number){
  const version=++folderVersion;++requestSequence;folderLoading.value=true;folderError.value='';graphOpen.value=false;moveOpen.value=false;uploadVisible.value=false
  try{const res=await getKnowledgeFolders(tenantId,id);if(!res.success)throw new Error(res.message||'文档加载失败');if(version!==folderVersion||folderDisposed)return;folderId.value=id;folderScope.value=res.data;pageNo.value=1;recordList.value=[];await loadRecords()}
  catch(cause){if(version===folderVersion&&!folderDisposed)folderError.value=cause instanceof Error?cause.message:'文档加载失败'}
  finally{if(version===folderVersion)folderLoading.value=false}
}
async function editFolder(item?:KnowledgeFolder){
  const parentId=item?.parentId??folderId.value,version=folderVersion
  try{const {value}=await ElMessageBox.prompt('文档可继续创建下级，权限继承当前知识库。',item?'重命名文档':'新建文档',{inputValue:item?.folderName||'',inputValidator:value=>!!value?.trim()&&value.trim().length<=100&&!/[\\/\x00]/.test(value)||'请输入1至100字的文档名称，不能包含斜杠',confirmButtonText:'保存',cancelButtonText:'取消'});if(version!==folderVersion||folderDisposed)return;const res=await saveKnowledgeFolder(tenantId,{folderName:value.trim(),parentId},item?.id);if(!res.success)throw new Error(res.message||'文档保存失败');ElMessage.success('文档已保存');await enterFolder(folderId.value)}catch(cause){if(cause!=='cancel'&&cause!=='close')ElMessage.error(cause instanceof Error?cause.message:'文档保存失败')}
}
async function removeFolder(item:KnowledgeFolder){
  const version=folderVersion
  try{await ElMessageBox.confirm(`确定永久删除空文档“${item.folderName}”吗？有子文档或资料时无法删除。`,'删除空文档',{type:'warning',confirmButtonText:'删除',cancelButtonText:'取消'});if(version!==folderVersion||folderDisposed)return;const res=await deleteKnowledgeFolder(tenantId,item.id);if(!res.success)throw new Error(res.message||'删除失败');await enterFolder(folderId.value)}catch(cause){if(cause!=='cancel'&&cause!=='close')ElMessage.error(cause instanceof Error?cause.message:'删除失败')}
}
function openMove(row:KnowledgeRecord){moveRecord.value=row;moveTarget.value=folderId.value;moveError.value='';moveOpen.value=true}
async function submitMove(){if(!moveRecord.value||moving.value)return;const version=folderVersion;moving.value=true;moveError.value='';try{const res=await moveKnowledgeDocuments(tenantId,[moveRecord.value.id],moveTarget.value);if(!res.success)throw new Error(res.message||'移动失败');if(version!==folderVersion||folderDisposed)return;moveOpen.value=false;ElMessage.success('文档已移动');await loadRecords()}catch(cause){if(version===folderVersion)moveError.value=cause instanceof Error?cause.message:'移动失败'}finally{moving.value=false}}
onBeforeUnmount(()=>{folderDisposed=true;++folderVersion;++requestSequence})
const recordList = ref<KnowledgeRecord[]>([])
const keyword = ref('')
const syncStatus = ref<'' | 'synced' | 'pending'>('')
const pageNo = ref(1)
const pageSize = 5
const total = ref(0)
const listLoading = ref(false)
const listError = ref('')
let requestSequence = 0
let searchTimer: ReturnType<typeof setTimeout> | undefined
const syncing = ref(false)
const deletingId = ref<number | null>(null)
const downloadingId = ref<number | null>(null)

const replaceVisible = ref(false)
const replacingNow = ref(false)
const editLoading = ref(false)
const replacing = ref<KnowledgeRecord | null>(null)
const editContent = ref('')

const openReplace = async (record: KnowledgeRecord) => {
  replacing.value = record
  editContent.value = ''
  replaceVisible.value = true
  editLoading.value = true
  try {
    const response = await getKnowledgeDocument(tenantId, record.id)
    if (!response.success) {
      ElMessage.warning(response.message || '文档内容加载失败')
      replaceVisible.value = false
      return
    }
    editContent.value = response.data.content || ''
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文档内容加载失败')
    replaceVisible.value = false
  } finally {
    editLoading.value = false
  }
}

const submitEditContent = async () => {
  const record = replacing.value
  const content = editContent.value.trim()
  if (!record || !content) {
    ElMessage.warning('文档内容不能为空')
    return
  }
  replacingNow.value = true
  try {
    const response = await saveKnowledgeDocument(tenantId, record.id, content)
    if (!response.success) {
      ElMessage.warning(response.message || '保存失败')
      return
    }
    ElMessage.success(response.message || '已用新内容覆盖，原数据和向量已删除')
    replaceVisible.value = false
    await loadRecords()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    replacingNow.value = false
  }
}

const downloadRecord = async (record: KnowledgeRecord) => {
  downloadingId.value = record.id
  try {
    await downloadKnowledgeRecord(record.id, record.fileUrl || record.title)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '下载失败')
  } finally {
    downloadingId.value = null
  }
}
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadWarnings = ref<string[]>([])
const fileList = ref<UploadUserFile[]>([])
const createMode = ref<'file' | 'manual'>('file')
const manualForm = reactive({ title: '', content: '' })

const syncStateMap: Record<KnowledgeRecord['syncStatus'], { label: string; type: TagProps['type'] }> = {
  synced: { label: '已同步', type: 'success' },
  missing: { label: '缺少向量', type: 'danger' },
  outdated: { label: '版本落后', type: 'warning' },
  orphaned: { label: '待清理', type: 'warning' }
}

const syncMeta = (status: KnowledgeRecord['syncStatus']) => syncStateMap[status]

const loadRecords = async () => {
  if (!Number.isInteger(tenantId) || tenantId <= 0) {
    listError.value = '知识库 ID 无效'
    return
  }
  const sequence = ++requestSequence
  listLoading.value = true
  listError.value = ''
  try {
    const response = await getTenantRecordPage(tenantId, {
      folderId:folderId.value,
      keyword: keyword.value.trim() || undefined,
      syncStatus: syncStatus.value || undefined,
      pageNo: pageNo.value,
      pageSize
    })
    if (sequence !== requestSequence) return
    if (!response.success) {
      listError.value = response.message || '知识数据加载失败'
      return
    }
    tenant.value = response.data.tenant
    recordList.value = response.data.list
    total.value = response.data.total
  } catch (error) {
    if (sequence === requestSequence) {
      listError.value = error instanceof Error ? error.message : '知识数据加载失败'
    }
  } finally {
    if (sequence === requestSequence) listLoading.value = false
  }
}

const resetCreateDialog = () => {
  createMode.value = 'file'
  fileList.value = []
  Object.assign(manualForm, { title: '', content: '' })
}

const openCreateDialog = () => {
  resetCreateDialog()
  uploadVisible.value = true
}

const submitUpload = async () => {
  const files = fileList.value.flatMap((item) => item.raw ? [item.raw] : [])
  if (!files.length) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  uploading.value = true
  try {
    const response = await uploadTenantRecords(tenantId, files,folderId.value)
    if (!response.success) {
      ElMessage.warning(response.message || '资料上传失败')
      return
    }
    ElMessage.success(response.message || '文件已上传')
    uploadWarnings.value = response.data.warnings || []
    uploadVisible.value = false
    pageNo.value = 1
    await loadRecords()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '资料上传失败')
  } finally {
    uploading.value = false
  }
}

const submitManualRecord = async () => {
  const title = manualForm.title.trim()
  const content = manualForm.content.trim()
  if (!title || !content) {
    ElMessage.warning('请填写资料标题和知识正文')
    return
  }
  if (new TextEncoder().encode(content).length > 60000) {
    ElMessage.warning('知识正文不能超过 60000 字节')
    return
  }
  uploading.value = true
  try {
    const response = await createKnowledgeRecord(tenantId, { title, content,folderId:folderId.value })
    if (!response.success) {
      ElMessage.warning(response.message || '知识资料新增失败')
      return
    }
    ElMessage.success(response.message || '知识资料新增并同步成功')
    uploadVisible.value = false
    pageNo.value = 1
    await loadRecords()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '知识资料新增失败')
  } finally {
    uploading.value = false
  }
}

const submitCreate = () => createMode.value === 'file' ? submitUpload() : submitManualRecord()

const confirmDelete = async (record: KnowledgeRecord) => {
  try {
    await ElMessageBox.confirm(
      `确定删除“${record.title || '未命名文档'}”吗？文档和对应的检索数据都会删除。`,
      '删除文档',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  deletingId.value = record.id
  try {
    const response = await deleteKnowledgeRecord(record.id, tenantId)
    if (!response.success) {
      ElMessage.warning(response.message || '文档删除失败')
      return
    }
    ElMessage.success(response.message || '文档已删除')
    await loadRecords()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文档删除失败')
  } finally {
    deletingId.value = null
  }
}

const syncRecords = async () => {
  syncing.value = true
  try {
    const response = await syncTenantRecords(tenantId)
    if (!response.success) {
      ElMessage.warning(response.message || '同步失败')
      return
    }
    ElMessage.success(
      `同步完成：更新 ${response.data.synced} 条，清理 ${response.data.deletedOrphans} 条`
    )
    await loadRecords()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '同步失败')
  } finally {
    syncing.value = false
  }
}

watch(keyword, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pageNo.value = 1
    loadRecords()
  }, 300)
})

watch(syncStatus, () => {
  pageNo.value = 1
  loadRecords()
})

onMounted(()=>enterFolder(0))
</script>

<style scoped lang="scss">
.folder-breadcrumb{display:flex;align-items:center;gap:8px;overflow-x:auto;white-space:nowrap;padding:8px 0}.folder-list{max-height:230px;overflow:auto;flex-shrink:0}.folder-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:8px 12px;border-bottom:1px solid var(--el-border-color-lighter)}.folder-hint{color:var(--el-text-color-secondary);font-size:13px}
.folder-entry{flex:1;min-width:0;min-height:40px;padding:8px 12px;justify-content:flex-start;text-align:left}.folder-entry :deep(>span){display:flex;align-items:center;gap:16px;width:100%;min-width:0}.folder-entry-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.folder-enter-label{flex-shrink:0;font-size:13px}.folder-entry:hover,.folder-entry:focus-visible{background:var(--el-color-primary-light-9);border-radius:6px}.folder-row>div{flex-shrink:0}
.knowledge-page { height: calc(100vh - 60px); padding: 24px; box-sizing: border-box; background: var(--bg-dark, #f5f7fa); }
.knowledge-card { height: 100%; border: 0; border-radius: 14px; }
.knowledge-card :deep(.el-card__body) { display: flex; height: calc(100% - 102px); flex-direction: column; box-sizing: border-box; }
.page-header, .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.header-actions { display: flex; align-items: center; flex-wrap:wrap; gap: 10px; }
.title-area h2 { margin: 0; color: #1f2937; font-size: 22px; }
.toolbar { margin-bottom: 18px; }
.record-search { width: 420px; }
.record-search :deep(.el-input__wrapper) { border-radius: 20px; background: #f5f7fa; }
.status-filter { width: 160px; }
.list-alert { margin-bottom: 16px; }
.table-area { min-height: 0; flex: 0 1 auto; overflow: auto; }
.record-title { color: #1f2937; font-weight: 600; }
.version-cell { white-space: nowrap; }
.action-buttons { display: flex; align-items: center; justify-content: center; gap: 14px; white-space: nowrap; }
.action-buttons :deep(.el-button + .el-button) { margin-left: 0; }
.pagination-area { display: flex; align-items: center; justify-content: flex-end; flex-shrink: 0; padding-top: 16px; }
.upload-icon { margin-bottom: 8px; color: var(--el-color-primary); font-size: 36px; }
.upload-tip { color: #6b7280; font-size: 12px; }
.record-create-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.manual-record-form { padding: 0 4px; }
.manual-record-tip { margin-top: -4px; color: #6b7280; font-size: 12px; line-height: 1.6; }
@media (max-width: 760px) {
  .knowledge-page { height: auto; min-height: calc(100vh - 60px); padding: 14px; }
  .knowledge-card :deep(.el-card__body) { height: auto; min-height: 520px; }
  .toolbar { align-items: stretch; flex-direction: column; }
  .page-header { align-items: stretch; flex-direction: column; }
  .header-actions { justify-content: flex-start; }
  .record-search, .status-filter { width: 100%; }
  .pagination-area { justify-content: center; overflow-x: auto; }
}
</style>
