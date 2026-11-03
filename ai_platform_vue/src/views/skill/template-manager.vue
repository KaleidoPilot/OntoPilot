<template>
  <div class="template-manager"><el-card shadow="never"><template #header><div class="heading"><h2>模板管理</h2><el-button type="primary" @click="openGenerate">生成模板</el-button></div></template>
    <p class="hint">从模板或范文提炼写作规则。可选多个项目组，补充表字段来源和取数口径；不选则使用通用写作规则。</p>
    <el-dialog v-model="generateOpen" title="生成模板" width="min(720px,96vw)" :close-on-click-modal="false" :close-on-press-escape="!submitting" :show-close="!submitting">
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="模板名称（可选）"><el-input v-model="name" maxlength="100" :disabled="submitting" @input="key=''" /></el-form-item>
        <el-form-item label="模板文件" required><el-upload ref="upload" drag :auto-upload="false" :show-file-list="false" :accept="formats.map(ext=>'.'+ext).join(',')" :disabled="submitting" :on-change="choose"><span>点击或拖入一份模板 / 参考范文</span><template #tip><div class="hint">DOC、DOCX、文字型 PDF、TXT、Markdown，每份10MB。</div></template></el-upload></el-form-item>
        <p v-if="file">{{ file.name }} <el-button link type="danger" :disabled="submitting" @click="clearFile">移除</el-button></p>
        <el-form-item label="使用权限"><span>{{ accessLabel(createAccessIds) }}</span><el-button link type="primary" :disabled="submitting" @click="openAccess('create')">设置用户组</el-button></el-form-item>
        <el-form-item label="关联项目组（可选，可多选）">
          <div class="project-choice" v-loading="groupsLoading"><el-input v-model="groupKeyword" placeholder="搜索项目组" clearable aria-label="搜索可选项目组" /><el-alert v-if="groupsError" :title="groupsError" type="warning" :closable="false"><template #default><el-button link @click="loadGroups">重试加载</el-button><span>也可不选择项目组继续。</span></template></el-alert>
            <el-checkbox-group v-model="projectGroupIds" :disabled="submitting" @change="key=''" class="project-options"><el-checkbox v-for="group in filteredGroups" :key="group.id" :value="group.id" :disabled="projectGroupIds.length>=20&&!projectGroupIds.includes(group.id)">{{ group.groupName }}</el-checkbox></el-checkbox-group>
            <el-empty v-if="!groupsLoading&&!groupsError&&!filteredGroups.length" description="暂无可选项目组，可不选择继续" :image-size="50" /><small class="hint">已选 {{ projectGroupIds.length }} / 20 个。只匹配已导入的表结构和关系，不在此处查询业务数据。</small>
          </div>
        </el-form-item><el-alert v-if="submitError" :title="submitError" type="error" :closable="false" />
      </el-form><template #footer><el-button :disabled="submitting" @click="generateOpen=false">取消</el-button><el-button type="primary" :disabled="!file" :loading="submitting" @click="submit">生成模板</el-button></template>
    </el-dialog>
    <div v-if="task" class="task"><el-tag :type="task.status==='completed'?'success':canRetry?'danger':'primary'">{{ task.progress }}</el-tag><p>任务号：{{ task.taskId }}</p><el-alert v-for="warning in task.warnings||[]" :key="warning" :title="warning" type="warning" :closable="false" /><el-alert v-if="task.error" :title="task.error.message" type="error" :closable="false" /><el-button v-if="canRetry" :loading="submitting" @click="retry">重试提炼</el-button><el-button :loading="checking" @click="check">刷新进度</el-button><el-alert v-if="taskError" :title="taskError" type="error" :closable="false" /></div>
  </el-card>
  <el-card shadow="never"><div class="list-tools"><h3>公司模板</h3><el-input v-model="keyword" clearable maxlength="100" placeholder="搜索模板名称或用途" aria-label="搜索公司模板" @keyup.enter="search" @clear="search" /><el-button @click="search">查询</el-button><el-button :loading="loading" @click="load">刷新</el-button><el-button :disabled="!accessSelection.length||loading" @click="openAccess('edit',accessSelection)">批量设置权限（{{ accessSelection.length }}）</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table ref="templateTable" v-loading="loading" :data="rows" row-key="id" @selection-change="accessSelection=$event" empty-text="暂无公司模板，点击生成模板开始">
      <el-table-column type="selection" width="48" :selectable="(row:CompanyTemplate)=>row.status!=='deleting'" />
      <el-table-column prop="skillName" label="模板名称" min-width="180" />
      <el-table-column prop="description" label="用途" min-width="230" show-overflow-tooltip />
      <el-table-column label="使用权限" min-width="160"><template #default="{row}"><span>{{ accessLabel(row.accessUserGroupIds) }}</span></template></el-table-column>
      <el-table-column label="关联项目组" min-width="180"><template #default="{row}"><el-tag v-for="group in row.projectGroups||[]" :key="group.id">{{ group.groupName }}</el-tag><span v-if="!row.projectGroups?.length" class="hint">未关联项目组</span></template></el-table-column>
      <el-table-column prop="createdAt" label="创建时间" min-width="170" />
      <el-table-column label="操作" min-width="380"><template #default="{row}"><el-button link type="primary" :disabled="row.status==='deleting'||deletingId===row.id" @click="show(row)">查看写作规则</el-button><el-button link type="primary" :disabled="row.status==='deleting'" @click="openAccess('edit',[row])">使用权限</el-button><el-button link type="primary" :disabled="row.status==='deleting'" @click="openStructure(row)">结构图谱</el-button><el-button link type="danger" :loading="deletingId===row.id" :disabled="!!deletingId" @click="removeTemplate(row)">{{ row.status==='deleting'?'重试删除':'删除' }}</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="total,prev,pager,next" @current-change="load" />
  </el-card>
  <el-dialog v-model="detailOpen" :title="selected?.skillName || '模板写作规则'" width="min(960px,96vw)" @closed="++detailVersion"><div v-loading="detailLoading" class="rules-content"><el-alert v-if="detailError" :title="detailError" type="error" :closable="false" /><el-alert v-for="warning in selected?.warnings||[]" :key="warning" :title="warning" type="warning" :closable="false" /><article v-if="detail" class="markdown-body" v-html="renderedDetail" /><el-empty v-else-if="!detailLoading&&!detailError" description="暂无写作规则" /></div><template #footer><el-button v-if="selected" link type="primary" @click="openStructure(selected)">结构图谱</el-button><el-button :loading="detailLoading" @click="loadDetail">重新加载</el-button><el-button @click="detailOpen=false">关闭</el-button></template></el-dialog>
  <TemplateStructureDialog v-model="structureOpen" :skill-id="structureTemplate?.id || ''" :name="structureTemplate?.skillName || '模板'" />
  <el-dialog v-model="accessOpen" :title="accessMode==='create'?'设置新模板使用权限':`设置 ${accessTargets.length} 份模板的使用权限`" width="min(680px,96vw)" :close-on-click-modal="false" :close-on-press-escape="!accessSaving" :show-close="!accessSaving" @closed="++accessVersion">
    <el-alert title="这里只授予模板使用权限，不会开放模板关联的项目组、数据库或知识库。" type="info" :closable="false" />
    <p v-if="accessTargets.length>1" class="hint">保存后，所选模板统一使用下面的授权范围，原有授权将被替换。</p>
    <el-radio-group v-model="accessScope" :disabled="accessSaving"><el-radio value="all">全部用户组</el-radio><el-radio value="selected">指定用户组</el-radio></el-radio-group>
    <div v-if="accessScope==='selected'" class="access-picker" v-loading="accessLoading">
      <el-input v-model="accessKeyword" clearable placeholder="搜索用户组" aria-label="搜索用户组" :disabled="accessSaving" />
      <div class="list-tools"><el-button :disabled="accessLoading||!!accessError||accessSaving||!filteredAccessGroups.length" @click="selectFilteredGroups">全选搜索结果</el-button><el-button :disabled="accessSaving" @click="accessIds=[]">清空选择</el-button><span class="hint">已选 {{ accessIds.length }} 个</span></div>
      <el-checkbox-group v-model="accessIds" :disabled="accessSaving" class="access-options"><el-checkbox v-for="group in filteredAccessGroups" :key="group.id" :value="group.id">{{ group.groupName }}{{ group.enabled?'':'（已停用）' }}</el-checkbox><el-checkbox v-for="id in missingAccessIds" :key="id" :value="id">已失效用户组 #{{ id }}（请取消选择）</el-checkbox></el-checkbox-group>
      <el-empty v-if="!accessLoading&&!accessError&&!filteredAccessGroups.length&&!missingAccessIds.length" description="暂无匹配用户组" :image-size="50" />
      <small class="hint">不选择用户组时，仅管理员可用。停用用户组的用户不能使用模板。</small>
    </div>
    <el-alert v-if="accessError" :title="accessError" type="error" :closable="false"><template #default><el-button link :disabled="accessSaving" @click="loadAccessGroups">重新加载用户组</el-button></template></el-alert>
    <template #footer><el-button :disabled="accessSaving" @click="accessOpen=false">取消</el-button><el-button type="primary" :loading="accessSaving" :disabled="accessLoading||!!accessError||!!missingAccessIds.length" @click="saveAccess">{{ accessMode==='create'?'确定':'保存权限' }}</el-button></template>
  </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed,onMounted,onBeforeUnmount,ref } from 'vue'
import { ElMessage,ElMessageBox,type UploadFile,type UploadInstance,type TableInstance } from 'element-plus'
import { getUserGroupOptions } from '@/api/user'
import MarkdownIt from 'markdown-it'
import TemplateStructureDialog from './TemplateStructureDialog.vue'
import { updateCompanyTemplateAccess,deleteCompanyTemplate,getCompanyTemplates,getCompanyTemplate,getCompanyTemplateProjectGroups,getCompanyTemplateTask,retryCompanyTemplateTask,getCompanyTemplateCapabilities,uploadCompanyTemplate,type CompanyTemplate,type CompanyTemplateTask,type TemplateProjectGroupOption } from '@/api/skill'
const file=ref<File>(),upload=ref<UploadInstance>(),name=ref(''),submitting=ref(false),submitError=ref(''),formats=ref(['docx','pdf','txt','md','markdown'])
const task=ref<CompanyTemplateTask>(),checking=ref(false),taskError=ref(''),canRetry=computed(()=>['failed','interrupted'].includes(task.value?.status||''))
const rows=ref<CompanyTemplate[]>([]),page=ref(1),total=ref(0),keyword=ref(''),loading=ref(false),error=ref('')
const deletingId=ref('')
const templateTable=ref<TableInstance>(),accessSelection=ref<CompanyTemplate[]>([])
const createAccessIds=ref<number[]|null>([]),accessOpen=ref(false),accessSaving=ref(false),accessLoading=ref(false),accessError=ref('')
const accessMode=ref<'create'|'edit'>('edit'),accessTargets=ref<CompanyTemplate[]>([]),accessScope=ref<'all'|'selected'>('selected'),accessIds=ref<number[]>([]),accessKeyword=ref('')
const accessGroups=ref<Array<{id:number;groupName:string;enabled:0|1}>>([])
let accessVersion=0
const filteredAccessGroups=computed(()=>accessGroups.value.filter(group=>group.groupName.toLowerCase().includes(accessKeyword.value.trim().toLowerCase())))
const missingAccessIds=computed(()=>accessScope.value==='selected'&&!accessLoading.value?accessIds.value.filter(id=>!accessGroups.value.some(group=>group.id===id)):[])
function accessLabel(ids?:number[]|null){return ids===null?'全部用户组':ids?.length?`已授权 ${ids.length} 个用户组`:'仅管理员'}
function openAccess(mode:'create'|'edit',targets:CompanyTemplate[]=[]){
  if(accessSaving.value)return
  ++accessVersion;accessMode.value=mode;accessTargets.value=[...targets];accessKeyword.value='';accessGroups.value=[];accessError.value=''
  const ids=mode==='create'?createAccessIds.value:targets.length===1?targets[0].accessUserGroupIds:[]
  accessScope.value=ids===null?'all':'selected';accessIds.value=[...(ids||[])];accessOpen.value=true;void loadAccessGroups()
}
async function loadAccessGroups(){
  const version=++accessVersion,scope=scopeVersion;accessLoading.value=true;accessError.value=''
  try{const res=await getUserGroupOptions(true);if(!res.success)throw new Error(res.message||'用户组加载失败');if(!disposed&&version===accessVersion&&scope===scopeVersion)accessGroups.value=res.data.list}
  catch(cause){if(!disposed&&version===accessVersion&&scope===scopeVersion)accessError.value=cause instanceof Error?cause.message:'用户组加载失败'}
  finally{if(version===accessVersion)accessLoading.value=false}
}
function selectFilteredGroups(){const ids=[...new Set([...accessIds.value,...filteredAccessGroups.value.map(group=>group.id)])];if(ids.length>1000){ElMessage.warning('每份模板最多授权1000个用户组');return}accessIds.value=ids}
async function saveAccess(){
  if(accessSaving.value||accessLoading.value||accessError.value||missingAccessIds.value.length)return
  const ids=accessScope.value==='all'?null:[...accessIds.value].sort((a,b)=>a-b)
  if(accessMode.value==='create'){createAccessIds.value=ids;key='';accessOpen.value=false;return}
  const version=accessVersion,scope=scopeVersion;accessSaving.value=true;accessError.value=''
  try{const res=await updateCompanyTemplateAccess(accessTargets.value.map(row=>row.id),ids);if(!res.success)throw new Error(res.message||'权限保存失败');if(disposed||scope!==scopeVersion||version!==accessVersion)return;accessOpen.value=false;ElMessage.success('模板使用权限已保存');await load()}
  catch(cause){if(!disposed&&scope===scopeVersion&&version===accessVersion)accessError.value=cause instanceof Error?cause.message:'权限保存失败，请重试'}
  finally{if(scope===scopeVersion)accessSaving.value=false}
}
const selected=ref<CompanyTemplate>(),detailOpen=ref(false),detail=ref(''),detailLoading=ref(false),detailError=ref('')
const structureOpen=ref(false),structureTemplate=ref<CompanyTemplate>()
let key='',timer:ReturnType<typeof setTimeout>|undefined,disposed=false,listVersion=0,detailVersion=0,scopeVersion=0
const generateOpen=ref(false),projectGroupIds=ref<number[]>([]),groups=ref<TemplateProjectGroupOption[]>([]),groupsLoading=ref(false),groupsError=ref(''),groupKeyword=ref('')
const filteredGroups=computed(()=>groups.value.filter(g=>g.groupName.toLowerCase().includes(groupKeyword.value.trim().toLowerCase())))
const markdown=new MarkdownIt({html:false,linkify:false,breaks:false}).disable('image')
const renderedDetail=computed(()=>markdown.render(detail.value.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/,'')))
function openGenerate(){clearFile();name.value='';projectGroupIds.value=[];createAccessIds.value=[];groupKeyword.value='';submitError.value='';generateOpen.value=true;void loadGroups()}
async function loadGroups(){const scope=scopeVersion;groupsLoading.value=true;groupsError.value='';try{const res=await getCompanyTemplateProjectGroups();if(!res.success)throw new Error(res.message||'项目组加载失败');if(scope===scopeVersion&&!disposed)groups.value=res.data.list}catch(cause){if(scope===scopeVersion&&!disposed)groupsError.value=cause instanceof Error?cause.message:'项目组加载失败'}finally{if(scope===scopeVersion)groupsLoading.value=false}}
function storageKey(){try{const user=JSON.parse(localStorage.getItem('userInfo')||'{}'),org=JSON.parse(localStorage.getItem('currentOrganization')||'null');return `company-template-task:${user.id}:${user.deptLevel===1?user.orgId:org?.id}`}catch{return ''}}
function remember(){try{if(task.value)localStorage.setItem(storageKey(),task.value.taskId)}catch{/* 可用页面上的任务号查询 */}}
function clearFile(){file.value=undefined;upload.value?.clearFiles();key=''}
function choose(item:UploadFile){clearFile();submitError.value='';if(!item.raw)return;if(!formats.value.includes(item.name.split('.').pop()?.toLowerCase()||'')){submitError.value='当前服务器不支持该文件格式';return}if(!item.raw.size||item.raw.size>10*1024*1024){submitError.value='文件不能为空且不能超过10MB';return}file.value=item.raw}
function schedule(){clearTimeout(timer);if(!disposed&&['queued','running'].includes(task.value?.status||''))timer=setTimeout(()=>void check(),2500)}
async function submit(){
  if(!file.value||submitting.value)return
  const scope=scopeVersion;submitting.value=true;submitError.value='';key||='company-template-'+crypto.randomUUID()
  try{const res=await uploadCompanyTemplate(file.value,name.value.trim(),key,projectGroupIds.value,createAccessIds.value);if(!res.success)throw new Error(res.message||'上传失败');if(disposed||scope!==scopeVersion)return;task.value=res.data;remember();clearFile();name.value='';generateOpen.value=false;schedule()}
  catch(cause){if(!disposed&&scope===scopeVersion)submitError.value=cause instanceof Error?cause.message:'上传失败'}
  finally{if(scope===scopeVersion)submitting.value=false}
}
async function check(){
  if(!task.value||checking.value||disposed)return
  const scope=scopeVersion,id=task.value.taskId;checking.value=true;taskError.value='';clearTimeout(timer)
  try{const res=await getCompanyTemplateTask(id);if(!res.success)throw new Error(res.message||'进度读取失败');if(disposed||scope!==scopeVersion||task.value?.taskId!==id)return;const done=task.value.status!=='completed'&&res.data.status==='completed';task.value=res.data;if(done){page.value=1;void load()}schedule()}
  catch(cause){if(!disposed&&scope===scopeVersion&&task.value?.taskId===id)taskError.value=cause instanceof Error?cause.message:'进度读取失败，请刷新'}
  finally{if(scope===scopeVersion)checking.value=false}
}
async function retry(){
  if(!task.value||submitting.value)return
  const scope=scopeVersion;submitting.value=true;taskError.value=''
  try{const res=await retryCompanyTemplateTask(task.value.taskId,task.value.attempt);if(!res.success)throw new Error(res.message||'重试失败');if(!disposed&&scope===scopeVersion){task.value=res.data;schedule()}}
  catch(cause){if(!disposed&&scope===scopeVersion)taskError.value=cause instanceof Error?cause.message:'重试失败'}
  finally{if(scope===scopeVersion)submitting.value=false}
}
async function load(){const v=++listVersion;accessSelection.value=[];templateTable.value?.clearSelection();loading.value=true;error.value='';try{const res=await getCompanyTemplates({keyword:keyword.value.trim(),pageNo:page.value,pageSize:10});if(!res.success)throw new Error(res.message||'模板加载失败');if(v===listVersion&&!disposed){rows.value=res.data.list;total.value=res.data.total}}catch(cause){if(v===listVersion&&!disposed){rows.value=[];total.value=0;error.value=cause instanceof Error?cause.message:'模板加载失败'}}finally{if(v===listVersion)loading.value=false}}
function search(){page.value=1;void load()}
async function removeTemplate(row:CompanyTemplate){
  if(deletingId.value)return
  const scope=scopeVersion;deletingId.value=row.id
  try{
    try{await ElMessageBox.confirm(`确定永久删除模板“${row.skillName}”吗？模板记录和提炼任务将物理删除，无法恢复。已生成的历史文档保留；处理中的模板需先完成任务。`,'删除模板',{type:'warning',confirmButtonText:'永久删除',cancelButtonText:'取消',closeOnClickModal:false})}catch{return}
    if(disposed||scope!==scopeVersion)return
    const res=await deleteCompanyTemplate(row.id)
    if(!res.success)throw new Error(res.message||'删除失败')
    if(disposed||scope!==scopeVersion)return
    if(selected.value?.id===row.id){++detailVersion;detailOpen.value=false;selected.value=undefined}
    if(structureTemplate.value?.id===row.id)structureOpen.value=false
    if(task.value?.skillId===row.id){clearTimeout(timer);task.value=undefined;taskError.value='';try{localStorage.removeItem(storageKey())}catch{/* 删除结果不依赖浏览器存储 */}}
    ElMessage.success('模板已永久删除');await load()
    if(scope===scopeVersion&&!error.value&&!rows.value.length&&page.value>1){page.value=Math.max(1,Math.ceil(total.value/10));await load()}
  }catch(cause){if(!disposed&&scope===scopeVersion){await load();if(scope===scopeVersion)error.value=cause instanceof Error?cause.message:'删除失败，请重试'}}
  finally{deletingId.value=''}
}
function show(row:CompanyTemplate){selected.value=row;detailOpen.value=true;void loadDetail()}
function openStructure(row:CompanyTemplate){structureTemplate.value=row;structureOpen.value=true}
async function loadDetail(){if(!selected.value)return;const v=++detailVersion;detailLoading.value=true;detailError.value='';detail.value='';try{const res=await getCompanyTemplate(selected.value.id);if(!res.success)throw new Error(res.message||'模板详情加载失败');if(v===detailVersion&&!disposed)detail.value=res.data.skillMarkdown}catch(cause){if(v===detailVersion)detailError.value=cause instanceof Error?cause.message:'详情加载失败'}finally{if(v===detailVersion)detailLoading.value=false}}
async function restore(){const scope=scopeVersion;void load();try{const res=await getCompanyTemplateCapabilities();if(disposed||scope!==scopeVersion)return;if(res.success)formats.value=[...new Set([...res.data.templateFormats,'markdown'])];else submitError.value=res.message||'文件能力检查失败'}catch{if(scope===scopeVersion)submitError.value='文件能力检查失败，请刷新页面重试'}if(disposed||scope!==scopeVersion)return;try{const id=localStorage.getItem(storageKey());if(id&&/^[a-f0-9]{24}$/.test(id)){task.value={taskId:id,status:'queued',progress:'正在恢复进度',attempt:0};void check()}}catch{/* 列表仍可查看已保存模板 */}}
function organizationChanged(){++scopeVersion;++listVersion;++detailVersion;++accessVersion;accessOpen.value=false;accessSaving.value=false;accessLoading.value=false;accessGroups.value=[];accessSelection.value=[];clearTimeout(timer);detailOpen.value=false;structureOpen.value=false;generateOpen.value=false;projectGroupIds.value=[];groups.value=[];task.value=undefined;rows.value=[];submitting.value=false;checking.value=false;submitError.value='';taskError.value='';clearFile();void restore()}
onMounted(()=>{void restore();window.addEventListener('organization-changed',organizationChanged)})
onBeforeUnmount(()=>{disposed=true;++listVersion;++detailVersion;++accessVersion;clearTimeout(timer);window.removeEventListener('organization-changed',organizationChanged)})
</script>
<style scoped>
.access-picker{margin-top:16px}.access-picker .list-tools{margin:12px 0}.access-options{display:flex;flex-direction:column;max-height:300px;overflow:auto;padding:4px}.access-options .el-checkbox{min-height:32px;height:auto;white-space:normal}
.template-manager{flex:1;min-height:0;overflow:auto;padding:20px}.el-card{margin-bottom:20px}h2,h3{margin:0}.hint{color:var(--el-text-color-secondary);line-height:1.7}.el-form{max-width:680px}.el-alert{margin:12px 0}.task{margin-top:20px;padding:16px;background:var(--el-fill-color-light);overflow-wrap:anywhere}.list-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}.list-tools .el-input{width:260px}.row-actions{display:flex;flex-wrap:wrap;gap:4px 8px}.el-pagination{margin-top:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;max-height:55vh;overflow:auto}@media(max-width:600px){.template-manager{padding:8px}.list-tools .el-input{width:100%}}
.heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.project-choice{width:100%}.project-options{display:flex;flex-direction:column;align-items:flex-start;max-height:220px;overflow:auto;padding:8px}.project-options .el-checkbox{height:auto;min-height:32px}.rules-content{max-height:65vh;overflow:auto;padding:0 16px 16px 0}.markdown-body{font-size:15px;line-height:1.85;color:var(--el-text-color-primary);overflow-wrap:anywhere}.markdown-body :deep(h1){font-size:26px;margin:0 0 24px}.markdown-body :deep(h2){font-size:21px;border-bottom:1px solid var(--el-border-color-lighter);padding-bottom:10px;margin:32px 0 16px}.markdown-body :deep(h3){font-size:17px;margin:24px 0 12px}.markdown-body :deep(p){margin:10px 0}.markdown-body :deep(ul),.markdown-body :deep(ol){padding-left:24px}.markdown-body :deep(table){display:block;overflow:auto;border-collapse:collapse;margin:16px 0}.markdown-body :deep(th),.markdown-body :deep(td){border:1px solid var(--el-border-color);padding:10px 14px;text-align:left}.markdown-body :deep(th){background:var(--el-fill-color-light)}.markdown-body :deep(pre){padding:16px;background:var(--el-fill-color-light);border-radius:8px}.el-tag{margin:2px 6px 2px 0}
</style>
