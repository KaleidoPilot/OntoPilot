<template>
  <div class="private-page">
    <el-card shadow="never" class="private-card">
      <template #header>
        <div class="page-header">
          <h2>{{ isLibraryPage ? '技能库' : (isExternal ? '我的私有技能' : '私有技能管理') }}</h2>
          <div v-if="!isLibraryPage" class="header-actions">
            <el-button type="primary" :icon="Plus" @click="openSkillDialog()">新增私有技能</el-button>
          </div>
        </div>
      </template>

      <div v-if="isLibraryPage" class="library-view">
        <div class="toolbar">
          <el-input v-model="libraryKeyword" clearable :prefix-icon="Search" placeholder="搜索技能或发布人" />
        </div>
        <el-table v-loading="libraryLoading" :data="library" row-key="id">
          <el-table-column prop="skillName" label="技能名称" min-width="180" />
          <el-table-column label="技能类型" width="110" align="center"><template #default="{row}"><el-tag :type="row.skillLevelType===1?'primary':'success'">{{row.skillLevelType===1?'主技能':'子技能'}}</el-tag></template></el-table-column>
          <el-table-column prop="skillDescription" label="技能描述" min-width="240" show-overflow-tooltip />
          <el-table-column prop="publisherUserName" label="发布人" min-width="120" />
          <el-table-column prop="groupName" label="用户组" min-width="140" />
          <el-table-column label="操作" width="210" align="center">
            <template #default="{row}">
              <el-button link type="primary" @click="addLibrarySkill(row)">添加到我的技能</el-button>
              <el-button v-if="row.publisherUserId===userInfo.id" link type="danger" @click="removeLibrarySkill(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty><el-empty description="本组暂无共享技能" /></template>
        </el-table>
        <div class="pagination"><el-pagination v-model:current-page="libraryPage" :page-size="10" :total="libraryTotal" layout="total, prev, pager, next" @current-change="loadLibrary" /></div>
      </div>

      <el-tabs v-else v-model="activeTab" @tab-change="loadActiveTab">
        <el-tab-pane label="私有技能" name="skills">
          <div class="toolbar">
            <el-input v-model="skillFilters.skillName" clearable :prefix-icon="Search" placeholder="技能名称" />
            <template v-if="!isExternal">
              <el-input v-model="skillFilters.userName" clearable placeholder="用户名" />
              <el-select v-model="skillFilters.groupId" clearable placeholder="用户组"><el-option v-for="g in groups" :key="g.id" :label="g.groupName" :value="g.id" /></el-select>
              <el-input v-model="skillFilters.account" clearable placeholder="登录账号" />
            </template>
            <el-select v-model="skillFilters.skillLevelType" clearable placeholder="全部类型"><el-option label="主技能" :value="1" /><el-option label="子技能" :value="2" /></el-select>
            <el-select v-model="skillFilters.enabled" clearable placeholder="全部状态"><el-option label="已启用" :value="1" /><el-option label="已停用" :value="0" /></el-select>
          </div>
          <el-table v-loading="skillLoading" :data="skills" row-key="id">
            <el-table-column prop="skillName" label="技能名称" min-width="170" />
            <el-table-column label="技能类型" width="110" align="center"><template #default="{row}"><el-tag :type="row.skillLevelType===1?'primary':'success'">{{row.skillLevelType===1?'主技能':'子技能'}}</el-tag></template></el-table-column>
            <el-table-column prop="skillDescription" label="技能描述" min-width="220" show-overflow-tooltip />
            <el-table-column v-if="!isExternal" prop="userId" label="用户ID" width="90" />
            <el-table-column v-if="!isExternal" prop="userName" label="用户名" min-width="120" />
            <el-table-column v-if="!isExternal" prop="groupName" label="用户组" min-width="140" />
            <el-table-column v-if="!isExternal" prop="account" label="登录账号" min-width="140" />
            <el-table-column label="状态" width="100" align="center"><template #default="{row}"><el-tag :type="row.enabled?'success':'info'">{{row.enabled?'已启用':'已停用'}}</el-tag></template></el-table-column>
            <el-table-column label="操作" :width="isExternal ? 300 : 150" align="center">
              <template #default="{row}">
                <el-button link type="primary" :icon="Edit" @click="openSkillDialog(row)">编辑</el-button>
                <el-button v-if="isExternal" link type="success" @click="openShareDialog(row)">分享</el-button>
                <el-button v-if="isExternal" link type="warning" @click="publishSkill(row)">发布到技能库</el-button>
                <el-button link type="danger" :icon="Delete" @click="removeSkill(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty description="暂无私有技能" /></template>
          </el-table>
          <div class="pagination"><el-pagination v-model:current-page="skillPage" :page-size="10" :total="skillTotal" layout="total, prev, pager, next" @current-change="loadSkills" /></div>
        </el-tab-pane>

        <el-tab-pane :label="isExternal ? '接收分享' : '分享记录'" name="inbox">
          <share-table :rows="inbox" direction="inbox" :external="isExternal" @accept="acceptShare" @reject="rejectShare" />
          <div class="pagination"><el-pagination v-model:current-page="inboxPage" :page-size="10" :total="inboxTotal" layout="total, prev, pager, next" @current-change="loadInbox" /></div>
        </el-tab-pane>

        <el-tab-pane v-if="isExternal" label="我的分享" name="outbox">
          <share-table :rows="outbox" direction="outbox" :external="isExternal" @revoke="revokeShare" />
          <div class="pagination"><el-pagination v-model:current-page="outboxPage" :page-size="10" :total="outboxTotal" layout="total, prev, pager, next" @current-change="loadOutbox" /></div>
        </el-tab-pane>

      </el-tabs>
    </el-card>

    <el-dialog v-model="skillDialog" :title="skillForm.id?'编辑私有技能':'新增私有技能'" width="min(620px, 94vw)">
      <el-form label-width="90px">
        <el-form-item v-if="!isExternal" label="所属用户" required><el-select v-model="skillForm.userId" class="full-width" filterable @change="handlePrivateSkillOwnerChange"><el-option v-for="u in userOptions" :key="u.id" :label="`${u.realName}（${u.account}）`" :value="u.id" /></el-select></el-form-item>
        <el-form-item label="技能名称" required><el-input v-model="skillForm.skillName" maxlength="100" /></el-form-item>
        <el-form-item label="技能类型" required><el-radio-group v-model="skillForm.skillLevelType" @change="handlePrivateSkillLevelTypeChange"><el-radio-button :value="1">主技能</el-radio-button><el-radio-button :value="2">子技能</el-radio-button></el-radio-group></el-form-item>
        <el-form-item v-if="skillForm.skillLevelType === 1" label="关联子技能">
          <el-tree-select
            v-model="skillForm.subSkillIds"
            :data="privateSubSkillOptions"
            :props="{ label: 'skillName', value: 'id' }"
            class="full-width"
            node-key="id"
            multiple
            show-checkbox
            check-strictly
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            :disabled="!isExternal && !skillForm.userId"
            :placeholder="!isExternal && !skillForm.userId ? '请先选择所属用户' : '搜索并勾选私有子技能'"
            no-data-text="当前用户暂无已启用的私有子技能"
          />
        </el-form-item>
        <el-form-item label="技能描述"><el-input v-model="skillForm.skillDescription" type="textarea" :rows="3" maxlength="255" /></el-form-item>
        <el-form-item label="规则内容" required><el-input v-model="skillForm.ruleContent" type="textarea" :rows="9" /></el-form-item>
        <SkillMcpBinding ref="skillMcpRef" :open="skillDialog" :skill-id="skillForm.id || undefined" :skill-type="3" :owner-id="isExternal ? Number(userInfo.id) : skillForm.userId" :personal="isExternal" @ready="skillMcpReady = $event" />
        <el-form-item label="状态"><el-switch v-model="skillForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="skillDialog=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!skillMcpReady" @click="saveSkill">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="shareDialog" title="分享给同组或其他外部用户" width="760px">
      <div class="share-toolbar"><el-input v-model="targetKeyword" clearable :prefix-icon="Search" placeholder="搜索用户名、账号或用户组" /></div>
      <el-table :data="targets" row-key="id" height="360" @selection-change="selectedTargets=$event">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="realName" label="用户名" />
        <el-table-column prop="groupName" label="用户组" />
        <el-table-column prop="account" label="登录账号" />
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="targetPage" :page-size="20" :total="targetTotal" layout="total, prev, pager, next" @current-change="loadTargets" /></div>
      <template #footer><el-button @click="shareDialog=false">取消</el-button><el-button type="primary" :disabled="!selectedTargets.length" :loading="saving" @click="saveShare">分享给选中用户</el-button></template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import SkillMcpBinding from '@/views/mcp/SkillMcpBinding.vue'
import { computed, defineComponent, h, onMounted, reactive, ref, watch, type PropType } from 'vue'
import { useRoute } from 'vue-router'
import { Delete, Edit, Plus, Search } from '@element-plus/icons-vue'
import { ElButton, ElMessage, ElMessageBox, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getExternalUserPage, getUserGroupOptions, type ExternalUser } from '@/api/user'
import {
  acceptPrivateSkillShare, addGroupSkillToMine, createPrivateSkill, deleteGroupSkillLibraryItem,
  deletePrivateSkill, getGroupSkillLibraryPage, getPrivateSkillPage, getPrivateSkillSharePage,
  getPrivateSkillShareTargets, getPrivateSubSkillOptions, publishPrivateSkill, rejectPrivateSkillShare, revokePrivateSkillShare,
  sharePrivateSkill, updatePrivateSkill, type PrivateSkill, type SkillLibraryItem, type SkillShare, type SubSkillOption
} from '@/api/skill'

const statusText: Record<number,string>={0:'待接收',1:'已接收',2:'已拒绝',3:'已撤回'}
const ShareTable=defineComponent({
  props:{rows:{type:Array as PropType<SkillShare[]>,required:true},direction:{type:String,required:true},external:{type:Boolean,required:true}},
  emits:['accept','reject','revoke'],
  setup(props,{emit}){return()=>h(ElTable,{data:props.rows,rowKey:'id'},()=>[
    h(ElTableColumn,{prop:'skillName',label:'技能名称',minWidth:180}),
    h(ElTableColumn,{label:'技能类型',width:110,align:'center'},{default:({row}:any)=>h(ElTag,{type:row.skillLevelType===1?'primary':'success'},()=>row.skillLevelType===1?'主技能':'子技能')}),
    h(ElTableColumn,{prop:props.direction==='inbox'?'sourceUserName':'targetUserName',label:props.direction==='inbox'?'分享人':'接收人',minWidth:130}),
    h(ElTableColumn,{label:'状态',width:100,align:'center'},{default:({row}:any)=>h(ElTag,{type:row.receiveStatus===0?'warning':'info'},()=>statusText[row.receiveStatus])}),
    h(ElTableColumn,{label:'操作',width:180,align:'center'},{default:({row}:any)=>row.receiveStatus===0&&props.external?(props.direction==='inbox'?[h(ElButton,{link:true,type:'primary',onClick:()=>emit('accept',row)},()=> '接收'),h(ElButton,{link:true,type:'danger',onClick:()=>emit('reject',row)},()=> '拒绝')]:[h(ElButton,{link:true,type:'danger',onClick:()=>emit('revoke',row)},()=> '撤回')]):null})
  ])}
})

const userInfo=(()=>{try{return JSON.parse(localStorage.getItem('fijo-chat-userInfo')||'{}')}catch{return {}}})()
const isExternal=userInfo.userType==='external'
const route=useRoute()
const isLibraryPage=computed(()=>route.path==='/skill/library')
const activeTab=ref('skills'), saving=ref(false), skillLoading=ref(false), libraryLoading=ref(false)
const skills=ref<PrivateSkill[]>([]), skillPage=ref(1), skillTotal=ref(0)
const privateSubSkillOptions=ref<SubSkillOption[]>([])
const skillFilters=reactive<{skillName:string;userName:string;groupId:''|number;account:string;skillLevelType:''|1|2;enabled:''|0|1}>({skillName:'',userName:'',groupId:'',account:'',skillLevelType:'',enabled:''})
const groups=ref<Array<{id:number;groupName:string}>>([]), userOptions=ref<ExternalUser[]>([])
const skillDialog=ref(false), skillForm=reactive({id:0,userId:undefined as number|undefined,skillName:'',skillDescription:'',skillLevelType:1 as 1|2,subSkillIds:[] as number[],ruleContent:'',enabled:1 as 0|1})
const skillMcpRef=ref<InstanceType<typeof SkillMcpBinding>>(),skillMcpReady=ref(false)
const shareDialog=ref(false), sharingSkillId=ref(0), targets=ref<any[]>([]), selectedTargets=ref<any[]>([]), targetKeyword=ref(''), targetPage=ref(1), targetTotal=ref(0)
const inbox=ref<SkillShare[]>([]),outbox=ref<SkillShare[]>([]),inboxPage=ref(1),outboxPage=ref(1),inboxTotal=ref(0),outboxTotal=ref(0)
const library=ref<SkillLibraryItem[]>([]),libraryKeyword=ref(''),libraryGroupId=ref<''|number>(''),libraryPage=ref(1),libraryTotal=ref(0)
let skillTimer:ReturnType<typeof setTimeout>|undefined,libraryTimer:ReturnType<typeof setTimeout>|undefined,targetTimer:ReturnType<typeof setTimeout>|undefined
const fail=(m?:string)=>ElMessage.error(m||'操作失败')

const loadSkills=async()=>{skillLoading.value=true;try{const res=await getPrivateSkillPage({skillName:skillFilters.skillName||undefined,userName:skillFilters.userName||undefined,groupId:skillFilters.groupId||undefined,account:skillFilters.account||undefined,skillLevelType:skillFilters.skillLevelType===''?undefined:skillFilters.skillLevelType,enabled:skillFilters.enabled===''?undefined:skillFilters.enabled,pageNo:skillPage.value,pageSize:10});if(res.success){skills.value=res.data.list;skillTotal.value=res.data.total}else fail(res.message)}finally{skillLoading.value=false}}
const loadInbox=async()=>{const res=await getPrivateSkillSharePage({direction:'inbox',pageNo:inboxPage.value,pageSize:10});if(res.success){inbox.value=res.data.list;inboxTotal.value=res.data.total}}
const loadOutbox=async()=>{const res=await getPrivateSkillSharePage({direction:'outbox',pageNo:outboxPage.value,pageSize:10});if(res.success){outbox.value=res.data.list;outboxTotal.value=res.data.total}}
const loadLibrary=async()=>{libraryLoading.value=true;try{const res=await getGroupSkillLibraryPage({keyword:libraryKeyword.value||undefined,groupId:libraryGroupId.value||undefined,pageNo:libraryPage.value,pageSize:10});if(res.success){library.value=res.data.list;libraryTotal.value=res.data.total}else fail(res.message)}finally{libraryLoading.value=false}}
const loadActiveTab=()=>{if(activeTab.value==='skills')loadSkills();else if(activeTab.value==='inbox')loadInbox();else if(activeTab.value==='outbox')loadOutbox()}
const loadOptions=async()=>{if(!isExternal){const [g,u]=await Promise.all([getUserGroupOptions(),getExternalUserPage({pageNo:1,pageSize:100})]);if(g.success)groups.value=g.data.list;if(u.success)userOptions.value=u.data.list}}
const loadPrivateSubSkillOptions=async()=>{const ownerId=isExternal?Number(userInfo.id):skillForm.userId;if(!ownerId){privateSubSkillOptions.value=[];return}const res=await getPrivateSubSkillOptions({userId:ownerId});if(res.success)privateSubSkillOptions.value=res.data.list.filter(item=>item.id!==skillForm.id);else privateSubSkillOptions.value=[]}
const handlePrivateSkillLevelTypeChange=(value:string|number|boolean|undefined)=>{if(Number(value)===2)skillForm.subSkillIds=[]}
const handlePrivateSkillOwnerChange=()=>{skillForm.subSkillIds=[];loadPrivateSubSkillOptions()}
const openSkillDialog=(row?:PrivateSkill)=>{Object.assign(skillForm,row?{id:row.id,userId:row.userId,skillName:row.skillName,skillDescription:row.skillDescription||'',skillLevelType:row.skillLevelType,subSkillIds:[...row.subSkillIds],ruleContent:row.ruleContent,enabled:row.enabled}:{id:0,userId:undefined,skillName:'',skillDescription:'',skillLevelType:1,subSkillIds:[],ruleContent:'',enabled:1});skillDialog.value=true;loadPrivateSubSkillOptions()}
const saveSkill=async()=>{if((!isExternal&&!skillForm.userId)||!skillForm.skillName.trim()||!skillForm.ruleContent.trim())return ElMessage.warning('请完整填写必填项');if(!skillMcpReady.value)return ElMessage.warning('请等待 MCP 配置加载成功');saving.value=true;try{const payload={...skillForm,mcpBindings:skillMcpRef.value!.getBindings()};const res=skillForm.id?await updatePrivateSkill(payload):await createPrivateSkill(payload);if(res.success){ElMessage.success('保存成功');skillDialog.value=false;await loadSkills()}else fail(res.message)}catch(cause){ElMessage.error(cause instanceof Error?cause.message:'保存失败')}finally{saving.value=false}}
const removeSkill=async(row:PrivateSkill)=>{await ElMessageBox.confirm(`确定物理删除技能“${row.skillName}”吗？`,'删除确认',{type:'warning'});const res=await deletePrivateSkill({id:row.id});if(res.success){ElMessage.success('删除成功');await loadSkills()}else fail(res.message)}
const loadTargets=async()=>{const res=await getPrivateSkillShareTargets({keyword:targetKeyword.value||undefined,pageNo:targetPage.value,pageSize:20});if(res.success){targets.value=res.data.list;targetTotal.value=res.data.total;selectedTargets.value=[]}}
const openShareDialog=async(row:PrivateSkill)=>{sharingSkillId.value=row.id;targetPage.value=1;targetKeyword.value='';shareDialog.value=true;await loadTargets()}
const saveShare=async()=>{saving.value=true;try{const res=await sharePrivateSkill({skillId:sharingSkillId.value,targetUserIds:selectedTargets.value.map(x=>x.id)});if(res.success){ElMessage.success(res.message||'分享成功');shareDialog.value=false;await loadOutbox()}else fail(res.message)}finally{saving.value=false}}
const acceptShare=async(row:SkillShare)=>{const res=await acceptPrivateSkillShare({id:row.id});if(res.success){ElMessage.success('接收成功');await Promise.all([loadInbox(),loadSkills()])}else fail(res.message)}
const rejectShare=async(row:SkillShare)=>{const res=await rejectPrivateSkillShare({id:row.id});if(res.success){ElMessage.success('已拒绝');await loadInbox()}else fail(res.message)}
const revokeShare=async(row:SkillShare)=>{const res=await revokePrivateSkillShare({id:row.id});if(res.success){ElMessage.success('已撤回');await loadOutbox()}else fail(res.message)}
const publishSkill=async(row:PrivateSkill)=>{const res=await publishPrivateSkill({skillId:row.id});if(res.success){ElMessage.success('已发布到技能库');await loadLibrary()}else fail(res.message)}
const addLibrarySkill=async(row:SkillLibraryItem)=>{const res=await addGroupSkillToMine({id:row.id});if(res.success){ElMessage.success('已添加到我的技能');await loadSkills()}else fail(res.message)}
const removeLibrarySkill=async(row:SkillLibraryItem)=>{await ElMessageBox.confirm(`确定删除技能库记录“${row.skillName}”吗？`,'删除确认',{type:'warning'});const res=await deleteGroupSkillLibraryItem({id:row.id});if(res.success){ElMessage.success('删除成功');await loadLibrary()}else fail(res.message)}

watch(()=>Object.values(skillFilters),()=>{clearTimeout(skillTimer);skillTimer=setTimeout(()=>{skillPage.value=1;loadSkills()},300)},{deep:true})
watch([libraryKeyword,libraryGroupId],()=>{clearTimeout(libraryTimer);libraryTimer=setTimeout(()=>{libraryPage.value=1;loadLibrary()},300)})
watch(targetKeyword,()=>{clearTimeout(targetTimer);targetTimer=setTimeout(()=>{targetPage.value=1;loadTargets()},300)})
watch(()=>route.path,(path)=>{if(path==='/skill/library')loadLibrary();else if(path==='/skill/private'){activeTab.value='skills';loadSkills()}})
onMounted(async()=>{await loadOptions();if(isLibraryPage.value)await loadLibrary();else await loadSkills()})
</script>

<style scoped lang="scss">
.private-page{height:100%;padding:20px;background:#f2f4f7}.private-card{min-height:calc(100vh - 100px);border:0}.page-header,.header-actions,.toolbar{display:flex;align-items:center}.page-header{justify-content:space-between}.page-header h2{margin:0;color:#17233d}.header-actions,.toolbar{gap:12px}.toolbar{margin-bottom:18px}.toolbar>.el-input{width:190px}.toolbar>.el-select{width:160px}.pagination{display:flex;justify-content:flex-end;padding-top:18px}.full-width{width:100%}.share-toolbar{margin-bottom:14px}.share-toolbar .el-input{width:320px}@media(max-width:760px){.private-page{padding:12px}.page-header,.toolbar{align-items:stretch;flex-direction:column}.header-actions{width:100%}.toolbar>.el-input,.toolbar>.el-select,.header-actions>.el-button{width:100%}.pagination{justify-content:center;overflow:auto}}
</style>

