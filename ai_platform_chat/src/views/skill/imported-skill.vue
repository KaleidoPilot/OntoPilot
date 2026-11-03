<template>
  <section class="skill-page">
    <header class="page-header"><div><h1>技能管理</h1><p>查看获授权的技能组和技能，或管理自己的技能。</p></div><el-button type="primary" @click="openEditor()">新增技能</el-button></header>
    <el-card shadow="never">
      <el-tabs v-model="tab">
        <el-tab-pane label="已授权技能组" name="company">
          <el-form inline @submit.prevent><el-form-item><el-input v-model="groupKeyword" clearable placeholder="搜索技能组名称或说明" aria-label="搜索已授权技能组" /></el-form-item><el-form-item><el-button :loading="groupLoading" @click="loadGroups">刷新</el-button></el-form-item></el-form>
          <el-alert v-if="groupError" :title="groupError" type="error" :closable="false" show-icon />
          <el-table v-loading="groupLoading" :data="visibleGroups" row-key="id" empty-text="暂无获授权的技能组，请联系管理员授权" @row-click="openGroup">
            <el-table-column label="技能组" min-width="180"><template #default="{row}"><el-button link type="primary" @click.stop="openGroup(row)">{{ row.groupName }}</el-button></template></el-table-column>
            <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip />
            <el-table-column label="权限" width="120"><template #default><el-tag>已授权 · 只读</el-tag></template></el-table-column>
            <el-table-column label="操作" width="120"><template #default="{row}"><el-button link type="primary" @click.stop="openGroup(row)">查看技能</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="我的技能" name="mine">
          <el-form inline @submit.prevent="searchMine"><el-form-item><el-input v-model="keyword" clearable placeholder="搜索我的技能" aria-label="搜索我的技能" @clear="searchMine" /></el-form-item><el-form-item><el-button native-type="submit">查询</el-button><el-button :loading="loading" @click="loadMine">刷新</el-button></el-form-item></el-form>
          <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
          <el-table v-loading="loading" :data="rows" row-key="id" empty-text="暂无个人技能，可点击新增技能">
            <el-table-column prop="skillName" label="技能名称" min-width="160" show-overflow-tooltip />
            <el-table-column label="类型" width="100"><template #default="{row}"><el-tag>{{ row.skillLevelType === 2 ? '子技能' : '主技能' }}</el-tag></template></el-table-column>
            <el-table-column prop="skillDescription" label="说明" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="160"><template #default="{row}"><el-button link type="primary" @click="openEditor(row.id)">编辑</el-button><el-button link type="danger" :loading="deletingId === row.id" @click="remove(row)">删除</el-button></template></el-table-column>
          </el-table>
          <el-pagination v-if="total" v-model:current-page="page" :page-size="10" :total="total" layout="total, prev, pager, next" @current-change="loadMine" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="groupOpen" :title="selectedGroup?.groupName || '组内技能'" width="min(1100px, 96vw)" top="6vh" @closed="groupVersion++">
      <p>{{ selectedGroup?.description || '本组技能由后台管理，仅显示当前用户获授权且已启用的技能。' }}</p>
      <el-form inline @submit.prevent="searchGroupSkills"><el-form-item><el-input v-model="skillKeyword" clearable placeholder="搜索组内技能" aria-label="搜索组内技能" @clear="searchGroupSkills" /></el-form-item><el-form-item><el-button native-type="submit" :loading="skillLoading">查询</el-button></el-form-item></el-form>
      <el-alert v-if="skillError" :title="skillError" type="error" :closable="false" />
      <el-table v-loading="skillLoading" :data="groupSkills" row-key="id" empty-text="暂无可查看的技能">
        <el-table-column prop="skillName" label="技能名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="100"><template #default="{row}">{{ row.skillLevelType === 2 ? '子技能' : '主技能' }}</template></el-table-column>
        <el-table-column prop="skillDescription" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="120"><template #default="{row}"><el-button link type="primary" @click="viewSkill = row">查看规则</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="skillTotal" v-model:current-page="skillPage" :page-size="10" :total="skillTotal" layout="total, prev, pager, next" @current-change="loadGroupSkills" />
    </el-dialog>
    <el-dialog :model-value="!!viewSkill" :title="viewSkill?.skillName || '技能规则'" width="min(850px, 96vw)" append-to-body @close="viewSkill = undefined">
      <p>{{ viewSkill?.skillDescription }}</p><pre class="rule-preview">{{ viewSkill?.ruleContent }}</pre>
    </el-dialog>

    <el-dialog v-model="editorOpen" :title="editingId ? '编辑我的技能' : '新增我的技能'" width="min(980px, 96vw)" top="5vh" class="personal-skill-editor" :close-on-click-modal="!saving && !resourceLoading" :close-on-press-escape="!saving && !resourceLoading" :show-close="!saving && !resourceLoading" @closed="editorVersion++">
      <el-alert v-if="editorError" :title="editorError" type="error" :closable="false" show-icon />
      <el-button v-if="resourceError" link type="primary" @click="openEditor(editingId)">重新加载配置</el-button>
      <el-form v-loading="resourceLoading" label-position="top" :disabled="saving || resourceLoading || !!resourceError" @submit.prevent="save">
        <el-tabs v-model="editorTab">
        <el-tab-pane label="基本信息" name="basic">
        <el-form-item label="技能名称" required><el-input v-model="form.skillName" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="技能类型"><el-radio-group v-model="form.skillLevelType" @change="changeLevel"><el-radio-button :value="1">主技能</el-radio-button><el-radio-button :value="2">子技能</el-radio-button></el-radio-group></el-form-item>
        <el-form-item v-if="form.skillLevelType === 1" label="关联子技能"><el-select v-model="form.subSkillIds" multiple filterable clearable placeholder="选择本人已启用的子技能"><el-option v-for="item in resources.subSkills.filter(item=>item.id!==editingId)" :key="item.id" :label="item.skillName" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="技能说明"><el-input v-model="form.skillDescription" type="textarea" :rows="2" maxlength="255" /></el-form-item>
        <el-form-item label="执行规则" required><el-input v-model="form.ruleContent" type="textarea" :rows="5" placeholder="说明解决什么问题、需要哪些资料、如何分析以及输出要求。" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
        </el-tab-pane>
        <el-tab-pane label="模型设置" name="models">
        <div class="model-grid">
        <el-form-item v-for="role in roles" :key="role.field" :label="role.label">
          <el-select v-model="form[role.field]" filterable clearable placeholder="选择对应用途的公司模型（可选）"><el-option v-for="model in resources.models.filter(item=>item.type===role.type)" :key="model.id" :label="model.model" :value="model.id" /></el-select>
          <small v-if="form[role.field] && !resources.models.some(item=>item.id===form[role.field] && item.type===role.type)" class="invalid">原模型已失效或用途不匹配，请重新选择或清空。</small>
        </el-form-item>
        </div>
        <el-form-item label="温度"><el-checkbox :model-value="form.temperature === null" @change="form.temperature = $event ? null : 0.3">沿用默认温度</el-checkbox><el-input-number v-if="form.temperature !== null" v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="2" /></el-form-item>
        </el-tab-pane>
        <el-tab-pane label="数据与知识库" name="resources">
        <el-form-item label="数据表"><el-select v-model="form.tableIds" multiple filterable clearable collapse-tags collapse-tags-tooltip placeholder="选择已授权数据表，支持跨项目组、跨库多选"><el-option v-for="item in resources.tables" :key="item.id" :value="item.id" :label="item.projectGroupName + ' / ' + item.tableName + (item.tableCnName ? ' · ' + item.tableCnName : '')" /></el-select><small>只展示已授权技能组中可用的数据表，不选择则不配置数据库取数。</small></el-form-item>
        <el-form-item label="知识库"><el-select v-model="form.tenantIds" multiple filterable clearable collapse-tags collapse-tags-tooltip placeholder="选择有权使用的知识库"><el-option v-for="item in resources.tenants" :key="item.id" :value="item.id" :label="item.tenantName" /></el-select></el-form-item>
        <el-alert v-if="missingResources" title="部分原数据表、知识库或子技能已失效，请移除或重新选择后保存。" type="warning" :closable="false" />
        </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer><el-button :disabled="saving || resourceLoading" @click="editorOpen = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="resourceLoading || !!resourceError" @click="save">保存技能</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsableSkillGroups, getUsableGroupSkills, getMyManagedSkills, getMyManagedSkill, getPersonalSkillResources, saveMyManagedSkill, deleteMyManagedSkill, type ManagedSkill, type PersonalSkillForm, type PersonalSkillResources, type UsableSkillGroup } from '@/api/skill'

const tab=ref('company'),groupKeyword=ref(''),groups=ref<UsableSkillGroup[]>([]),groupLoading=ref(false),groupError=ref('')
const visibleGroups=computed(()=>groups.value.filter(item=>(item.groupName+' '+item.description).toLowerCase().includes(groupKeyword.value.trim().toLowerCase())))
const rows=ref<ManagedSkill[]>([]),keyword=ref(''),page=ref(1),total=ref(0),loading=ref(false),error=ref(''),deletingId=ref<number>()
const groupOpen=ref(false),selectedGroup=ref<UsableSkillGroup>(),groupSkills=ref<ManagedSkill[]>([]),skillKeyword=ref(''),skillPage=ref(1),skillTotal=ref(0),skillLoading=ref(false),skillError=ref(''),viewSkill=ref<ManagedSkill>()
let disposed=false,listVersion=0,groupsVersion=0,groupVersion=0,editorVersion=0
const editorOpen=ref(false),editingId=ref<number>(),saving=ref(false),resourceLoading=ref(false),resourceError=ref(''),editorError=ref('')
const editorTab=ref('basic')
const resources=ref<PersonalSkillResources>({models:[],tables:[],tenants:[],subSkills:[]})
const blank=():PersonalSkillForm=>({skillName:'',skillDescription:'',ruleContent:'',enabled:1,skillLevelType:1,subSkillIds:[],intentLlmId:null,taskLlmId:null,executLlmId:null,summaryLlmId:null,temperature:null,tableIds:[],tenantIds:[]})
const form=ref(blank())
const roles:{field:'intentLlmId'|'taskLlmId'|'executLlmId'|'summaryLlmId';label:string;type:number}[]=[{field:'intentLlmId',label:'意图模型',type:1},{field:'taskLlmId',label:'任务分解模型',type:2},{field:'executLlmId',label:'执行模型',type:3},{field:'summaryLlmId',label:'总结模型',type:4}]
const ids=(value:number[]|string|null|undefined)=>Array.isArray(value)?[...value]:String(value||'').split(',').filter(Boolean).map(Number)
const missingResources=computed(()=>form.value.tableIds.some(id=>!resources.value.tables.some(t=>t.id===id))||form.value.tenantIds.some(id=>!resources.value.tenants.some(t=>t.id===id))||form.value.subSkillIds.some(id=>!resources.value.subSkills.some(t=>t.id===id)))
async function loadGroups(){
  const version=++groupsVersion;groupLoading.value=true;groupError.value=''
  try{const res=await getUsableSkillGroups();if(version!==groupsVersion||disposed)return;if(!res.success)throw new Error(res.message||'技能组加载失败');groups.value=res.data.list}
  catch(cause){if(version===groupsVersion&&!disposed){groups.value=[];groupError.value=cause instanceof Error?cause.message:'技能组加载失败'}}
  finally{if(version===groupsVersion)groupLoading.value=false}
}
async function loadMine(){
  const version=++listVersion;loading.value=true;error.value=''
  try{const res=await getMyManagedSkills({keyword:keyword.value.trim(),pageNo:page.value,pageSize:10});if(version!==listVersion||disposed)return;if(!res.success)throw new Error(res.message||'我的技能加载失败');rows.value=res.data.list;total.value=res.data.total}
  catch(cause){if(version===listVersion&&!disposed){rows.value=[];total.value=0;error.value=cause instanceof Error?cause.message:'我的技能加载失败'}}
  finally{if(version===listVersion)loading.value=false}
}
function searchMine(){page.value=1;void loadMine()}
function openGroup(group:UsableSkillGroup){selectedGroup.value=group;groupOpen.value=true;skillKeyword.value='';skillPage.value=1;void loadGroupSkills()}
function searchGroupSkills(){skillPage.value=1;void loadGroupSkills()}
async function loadGroupSkills(){
  if(!selectedGroup.value)return
  const version=++groupVersion,id=selectedGroup.value.id;skillLoading.value=true;skillError.value='';groupSkills.value=[]
  try{const res=await getUsableGroupSkills(id,{keyword:skillKeyword.value.trim(),pageNo:skillPage.value,pageSize:10});if(version!==groupVersion||disposed)return;if(!res.success)throw new Error(res.message||'组内技能加载失败');groupSkills.value=res.data.list;skillTotal.value=res.data.total}
  catch(cause){if(version===groupVersion&&!disposed){skillTotal.value=0;skillError.value=cause instanceof Error?cause.message:'组内技能加载失败'}}
  finally{if(version===groupVersion)skillLoading.value=false}
}
async function openEditor(id?:number){
  if(saving.value||resourceLoading.value)return
  const version=++editorVersion;editingId.value=id;form.value=blank();editorTab.value='basic';editorError.value='';resourceError.value='';editorOpen.value=true;resourceLoading.value=true
  try{
    const [options,detail]=await Promise.all([getPersonalSkillResources(),id?getMyManagedSkill(id):Promise.resolve(undefined)])
    if(version!==editorVersion||disposed)return
    if(!options.success)throw new Error(options.message||'资源加载失败')
    resources.value=options.data
    if(detail){if(!detail.success)throw new Error(detail.message||'技能加载失败');const row=detail.data;form.value={...blank(),skillName:row.skillName,skillDescription:row.skillDescription||'',ruleContent:row.ruleContent,enabled:row.enabled,skillLevelType:row.skillLevelType,subSkillIds:ids(row.subSkillIds),tableIds:ids(row.tableIds),tenantIds:ids(row.tenantIds),intentLlmId:row.intentLlmId,taskLlmId:row.taskLlmId,executLlmId:row.executLlmId,summaryLlmId:row.summaryLlmId,temperature:row.temperature}}
  }catch(cause){if(version===editorVersion){resourceError.value=cause instanceof Error?cause.message:'技能配置加载失败';editorError.value=resourceError.value}}
  finally{if(version===editorVersion)resourceLoading.value=false}
}
function changeLevel(){if(form.value.skillLevelType===2){form.value.subSkillIds=[];for(const role of roles)form.value[role.field]=null}}
async function save(){
  if(saving.value||resourceLoading.value||resourceError.value)return
  if(!form.value.skillName.trim()||!form.value.ruleContent.trim()){editorTab.value='basic';editorError.value='请填写技能名称和执行规则';return}
  if(new TextEncoder().encode(form.value.ruleContent).length>60000){editorError.value='执行规则最多60000字节，请缩短内容';return}
  saving.value=true;editorError.value=''
  try{const payload={...form.value};for(const role of roles)payload[role.field]=payload[role.field]||null;const res=await saveMyManagedSkill(payload,editingId.value);if(!res.success)throw new Error(res.message||'保存失败');editorOpen.value=false;tab.value='mine';page.value=1;keyword.value='';ElMessage.success('个人技能已保存');await loadMine()}
  catch(cause){editorError.value=cause instanceof Error?cause.message:'保存失败'}
  finally{saving.value=false}
}
async function remove(row:ManagedSkill){
  if(deletingId.value)return
  try{await ElMessageBox.confirm('确定永久删除“'+row.skillName+'”吗？此操作无法撤销。','删除我的技能',{type:'warning',confirmButtonText:'删除',cancelButtonText:'取消'})}catch{return}
  deletingId.value=row.id
  try{const res=await deleteMyManagedSkill(row.id);if(!res.success)throw new Error(res.message||'删除失败');ElMessage.success('技能已删除');if(rows.value.length===1&&page.value>1)page.value--;await loadMine()}
  catch(cause){ElMessage.error(cause instanceof Error?cause.message:'删除失败')}
  finally{deletingId.value=undefined}
}
onMounted(()=>{void loadGroups();void loadMine()})
onBeforeUnmount(()=>{disposed=true;++listVersion;++groupVersion;++groupsVersion;++editorVersion})
</script>

<style scoped>
:global(.personal-skill-editor){display:flex;flex-direction:column;max-height:90vh}:global(.personal-skill-editor .el-dialog__body){min-height:0;overflow:auto}:global(.personal-skill-editor .el-dialog__header),:global(.personal-skill-editor .el-dialog__footer){flex-shrink:0}:global(.personal-skill-editor .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);padding-top:14px}.model-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:24px}@media(max-width:600px){.model-grid{grid-template-columns:1fr}}
:global(.personal-skill-editor .el-form-item){margin-bottom:12px}
.skill-page{padding:28px;min-width:0}.page-header{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:20px}h1{font-size:24px;margin:0}p,small{color:var(--text-secondary);line-height:1.6}.el-pagination{justify-content:flex-end;margin-top:16px}.el-select{width:100%}.el-form--inline .el-input{width:300px}.el-alert{margin-bottom:16px}.rule-preview{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto;font:inherit;line-height:1.8}small{display:block;width:100%;margin-top:6px}.invalid{color:var(--el-color-warning)}@media(max-width:700px){.skill-page{padding:16px}.page-header{flex-wrap:wrap}.el-form--inline .el-input{width:100%}}
</style>
