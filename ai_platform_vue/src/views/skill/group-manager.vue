<template>
  <div class="skill-group-page">
    <div class="page-heading">
      <div><h2>技能管理</h2><p>按技能组管理技能，并授权给一个或多个用户组。</p></div>
      <el-button type="primary" @click="openGroup()">新建技能组</el-button>
    </div>
    <el-card shadow="never" class="group-panel" :class="{ 'is-saving': busy }">
      <div class="skill-toolbar">
        <el-input v-model="groupKeyword" placeholder="搜索技能组" clearable aria-label="搜索技能组" @keyup.enter="searchGroups" @clear="searchGroups" />
        <el-button @click="searchGroups">查询</el-button>
      </div>
      <el-alert v-if="groupError" :title="groupError" type="error" :closable="false" show-icon />
      <el-button v-if="groupError" link type="primary" @click="loadGroups">重新加载</el-button>
      <el-table v-loading="groupLoading" :data="groups" row-key="id" empty-text="暂无技能组，请先新建" @row-click="openSkillDetail">
        <el-table-column label="技能组" min-width="180">
          <template #default="{ row }"><el-button link type="primary" @click.stop="openSkillDetail(row)">{{ row.groupName }}</el-button></template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="授权用户组" min-width="220">
          <template #default="{ row }">
            <el-tag v-for="item in row.userGroups" :key="item.id" :type="item.enabled === 1 ? 'primary' : 'info'">{{ item.groupName }}{{ item.enabled === 0 ? '（停用）' : '' }}</el-tag>
            <span v-if="!row.userGroups.length" class="muted">未授权</span>
          </template>
        </el-table-column>
        <el-table-column label="技能" width="100"><template #default="{ row }">{{ row.skillCount }} 个</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.enabled === 1 ? 'success' : 'info'">{{ row.enabled === 1 ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }"><el-button link type="primary" @click.stop="openGroup(row)">编辑</el-button><el-button link type="danger" @click.stop="confirmDeleteGroup(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination layout="total, prev, pager, next" :total="groupTotal" :page-size="10" v-model:current-page="groupPage" @current-change="loadGroups" />
    </el-card>

    <el-dialog v-model="skillDetailOpen" :title="selected?.groupName || '组内技能'" width="min(1100px, 96vw)" top="6vh" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <template v-if="selected">
        <div class="section-heading">
          <p class="group-description">{{ selected.description || '暂无技能组说明' }}</p>
          <div><el-button @click="openGroup(selected)">用户组授权</el-button><el-button type="danger" plain @click="confirmDeleteGroup(selected)">删除技能组</el-button></div>
        </div>
        <div class="authorization"><span>授权用户组：</span>
          <el-tag v-for="item in selected.userGroups" :key="item.id" :type="item.enabled === 1 ? 'primary' : 'info'">{{ item.groupName }}{{ item.enabled === 0 ? '（停用）' : '' }}</el-tag>
          <span v-if="!selected.userGroups.length" class="muted">未授权，外部用户暂不可使用</span>
        </div>
        <el-alert v-if="selected.enabled === 0" title="技能组已停用，外部用户无法执行组内技能。" type="info" :closable="false" show-icon />
        <div class="skill-toolbar">
          <el-input v-model="skillKeyword" placeholder="搜索组内技能" clearable aria-label="搜索组内技能" @keyup.enter="searchSkills" @clear="searchSkills" />
          <el-button @click="searchSkills">查询</el-button>
          <el-button type="primary" @click="openSkill()">新增技能</el-button>
        </div>
        <el-alert v-if="skillError" :title="skillError" type="error" :closable="false" show-icon />
        <el-button v-if="skillError" link type="primary" @click="loadSkills">重新加载</el-button>
        <el-table v-loading="skillLoading" :data="skills" row-key="id" empty-text="暂无技能，可新增技能">
          <el-table-column prop="skillName" label="技能名称" min-width="150" show-overflow-tooltip />
          <el-table-column label="类型" width="90"><template #default="{ row }"><el-tag :type="row.skillLevelType === 2 ? 'success' : 'primary'">{{ row.skillLevelType === 2 ? '子技能' : '主技能' }}</el-tag></template></el-table-column>
          <el-table-column label="来源" min-width="150"><template #default="{ row }">{{ row.skillType === 1 ? '公共技能' : (row.projectSkillGroupName || '项目组技能') }}</template></el-table-column>
          <el-table-column prop="skillDescription" label="说明" min-width="180" show-overflow-tooltip />
          <el-table-column label="状态" width="80"><template #default="{ row }"><el-tag :type="row.enabled === 1 ? 'success' : 'info'">{{ row.enabled === 1 ? '启用' : '停用' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="135"><template #default="{ row }"><el-button link type="primary" @click="openSkill(row)">编辑</el-button><el-button link type="danger" @click="confirmRemove(row)">移出</el-button></template></el-table-column>
        </el-table>
        <p class="muted">技能可整合模型、MCP、跨库数据表和知识库。未在此保存配置的旧技能继续按原方式执行。</p>
        <el-pagination layout="total, prev, pager, next" :total="skillTotal" :page-size="10" v-model:current-page="skillPage" @current-change="loadSkills" />
      </template>
    </el-dialog>

    <el-dialog v-model="groupDialog" :title="editingGroupId ? '编辑技能组' : '新建技能组'" width="min(620px, 94vw)" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <el-form ref="groupFormRef" :model="groupForm" :rules="groupRules" label-position="top" :disabled="busy">
        <el-form-item label="技能组名称" prop="groupName"><el-input v-model="groupForm.groupName" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="说明"><el-input v-model="groupForm.description" type="textarea" :rows="3" maxlength="1000" /></el-form-item>
        <el-form-item label="授权用户组">
          <div class="user-group-picker">
            <div class="selected-tables">
              <el-tag v-for="item in selectedUserGroups" :key="item.id" closable :type="item.enabled === 1 ? 'primary' : 'info'" @close="removeUserGroup(item.id)">{{ item.groupName }}{{ item.enabled === 0 ? '（停用）' : '' }}</el-tag>
              <span v-if="!groupForm.userGroupIds.length" class="muted">未选择，外部用户暂不可使用</span>
            </div>
            <div class="skill-toolbar">
              <el-input v-model="userGroupKeyword" clearable placeholder="搜索用户组" aria-label="搜索用户组" :disabled="userGroupLoading" />
              <el-button :disabled="userGroupLoading || !filteredUserGroups.length || filteredAllSelected" @click="selectFilteredUserGroups">全选</el-button>
              <el-button :disabled="userGroupLoading || !filteredSelectedCount" @click="clearFilteredUserGroups">取消全选</el-button>
            </div>
            <div v-loading="userGroupLoading" class="user-group-list">
              <el-empty v-if="!userGroupLoading && !filteredUserGroups.length" :image-size="64" :description="userGroupKeyword.trim() ? '没有符合条件的用户组' : '暂无用户组'" />
              <el-checkbox-group v-else v-model="groupForm.userGroupIds" aria-label="授权用户组，可多选">
                <el-checkbox v-for="item in filteredUserGroups" :key="item.id" :value="item.id">{{ item.groupName }}{{ item.enabled === 0 ? '（停用）' : '' }}</el-checkbox>
              </el-checkbox-group>
            </div>
            <div class="muted">可搜索后勾选多个，或全选当前搜索结果。未选择时，外部用户无法使用组内技能。停用用户组的授权不生效。</div>
          </div>
        </el-form-item>
        <el-alert v-if="userGroupError" :title="userGroupError" type="error" :closable="false" /><el-button v-if="userGroupError" link type="primary" @click="loadUserGroups">重新加载用户组</el-button>
        <el-form-item label="排序"><el-input-number v-model="groupForm.sortOrder" :min="0" :max="1000000" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="groupForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="busy" @click="groupDialog = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="!!userGroupError || userGroupLoading" @click="submitGroup">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="skillDialog" :title="editingSkill ? '编辑技能与资源' : '新增技能'" width="min(980px, 94vw)" top="5vh" class="skill-editor" :close-on-click-modal="!busy" :show-close="!busy" :close-on-press-escape="!busy">
      <el-alert v-if="resourceError" :title="resourceError" type="error" :closable="false" /><el-button v-if="resourceError" link type="primary" @click="loadSkillResources">重新加载配置</el-button>
      <el-form ref="skillFormRef" v-loading="resourceLoading" :model="skillForm" :rules="skillRules" label-position="top" :disabled="busy || resourceLoading || !!resourceError">
        <el-form-item label="技能名称" prop="skillName"><el-input v-model="skillForm.skillName" maxlength="100" /></el-form-item>
        <el-form-item label="技能类型">
          <el-radio-group v-model="skillForm.skillLevelType" @change="handleSkillLevelChange">
            <el-radio-button :value="1">主技能</el-radio-button>
            <el-radio-button :value="2">子技能</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="skillForm.skillLevelType === 1" label="关联子技能">
          <el-select v-model="skillForm.subSkillIds" multiple filterable clearable collapse-tags collapse-tags-tooltip :loading="subSkillLoading" placeholder="搜索并勾选子技能，一个主技能可以绑定多个" style="width: 100%" no-data-text="暂无已启用的子技能">
            <el-option v-for="item in subSkillOptions" :key="item.id" :value="item.id" :label="item.skillName" />
          </el-select>
          <div class="muted">只能选择当前技能组里已启用的子技能。先建成子技能，再由主技能勾选多个。子技能不能再绑定下一层。</div>
          <el-alert v-if="subSkillError" :title="subSkillError" type="error" :closable="false" /><el-button v-if="subSkillError" link type="primary" @click="loadSubSkillOptions">重新加载子技能</el-button>
          <el-alert v-else-if="missingSubSkillIds.length" title="部分已绑定的子技能已失效，请移除后保存。" type="warning" :closable="false" />
        </el-form-item>
        <el-form-item label="技能说明"><el-input v-model="skillForm.skillDescription" maxlength="255" /></el-form-item>
        <el-form-item label="执行规则" prop="ruleContent"><el-input v-model="skillForm.ruleContent" type="textarea" :rows="10" placeholder="说明技能解决什么问题、使用哪些信息、如何分析和输出。" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="skillForm.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-divider content-position="left">模型与温度</el-divider>
        <el-form-item v-for="item in modelFields" :key="item.field" :label="item.label">
          <el-select v-model="skillForm[item.field]" clearable filterable :placeholder="item.placeholder" style="width: 100%">
            <el-option v-for="model in modelsOfType(item.type)" :key="model.id" :value="model.id" :label="model.label" />
          </el-select>
          <div class="muted">{{ item.hint }}</div>
          <el-alert v-if="orphanModel(item.field, item.type)" title="原模型已失效或用途不匹配，请重新选择或清空。" type="warning" :closable="false" />
        </el-form-item>
        <el-form-item label="温度">
          <el-checkbox :model-value="skillForm.temperature === null" @change="skillForm.temperature = $event ? null : 0.3">沿用技能温度</el-checkbox>
          <el-input-number v-if="skillForm.temperature !== null" v-model="skillForm.temperature" :min="0" :max="2" :step="0.1" :precision="2" />
        </el-form-item>
        <el-divider content-position="left">数据与资料（均可选）</el-divider>
        <el-form-item label="数据表">
          <div class="resource-block"><el-button @click="openTablePicker">选择数据表（支持跨库多选）</el-button>
            <div class="selected-tables"><el-tag v-for="id in skillForm.tableIds" :key="id" closable @close="removeTable(id)">{{ tableLabel(id) }}</el-tag><span v-if="!skillForm.tableIds.length" class="muted">不查询数据库</span></div>
            <div class="muted">可从多个数据项目组选表。不同连接分别取数，关联查询只使用已登记关系。</div>
          </div>
        </el-form-item>
        <el-form-item label="知识库">
          <el-select v-model="skillForm.tenantIds" multiple filterable clearable placeholder="可选多个知识库，供资料检索和内容补充" style="width: 100%">
            <el-option v-for="tenant in resourceOptions.tenants" :key="tenant.id" :value="tenant.id" :label="tenant.tenantName + '（' + (tenant.scopeType === 1 ? '公司公有' : '公司私有') + '，ID ' + tenant.id + '）'" />
          </el-select>
          <div class="muted">执行时仍检查用户实际授权；知识资料不能代替缺失的真实业务数据。</div>
          <el-alert v-if="skillForm.tenantIds.some(id => !resourceOptions.tenants.some(item => item.id === id))" title="部分原知识库已失效，请移除后保存。" type="warning" :closable="false" />
        </el-form-item>
        <SkillMcpBinding ref="mcpRef" :open="skillDialog" :skill-id="editingSkill?.id" :skill-type="editingSkill?.skillType || 1" @ready="mcpReady = $event" />
      </el-form>
      <template #footer><el-button :disabled="busy" @click="skillDialog = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="resourceLoading || !!resourceError || !mcpReady || subSkillLoading || (skillForm.skillLevelType === 1 && !!subSkillError)" @click="submitSkill">保存技能</el-button></template>
    </el-dialog>

    <el-dialog v-model="tablePicker" title="选择已导入的数据表" width="min(1000px, 95vw)" append-to-body>
      <div class="skill-toolbar">
        <el-select v-model="tableProjectId" filterable placeholder="选择数据项目组" @change="tablePage = 1; loadTables()"><el-option v-for="group in resourceOptions.projectGroups" :key="group.id" :value="group.id" :label="group.groupName + (group.libraryName ? ' / ' + group.libraryName : '')" /></el-select>
        <el-input v-model="tableKeyword" placeholder="搜索中英文表名" clearable @keyup.enter="tablePage = 1; loadTables()" @clear="tablePage = 1; loadTables()" /><el-button @click="tablePage = 1; loadTables()">查询</el-button>
      </div>
      <el-alert v-if="tableError" :title="tableError" type="error" :closable="false" /><el-button v-if="tableError" link type="primary" @click="loadTables">重新加载</el-button>
      <el-table :data="tableRows" v-loading="tableLoading" row-key="id" empty-text="该项目组没有符合条件的已导入表">
        <el-table-column width="50"><template #default="{ row }"><el-checkbox :model-value="skillForm.tableIds.includes(row.id)" :aria-label="'选择数据表 ' + row.tableName" @change="toggleTable(row, $event)" /></template></el-table-column>
        <el-table-column prop="tableName" label="数据库.表名" min-width="220" /><el-table-column prop="tableCnName" label="中文名称" min-width="160" />
        <el-table-column prop="projectGroupName" label="数据项目组" min-width="150" />
        <el-table-column label="字段" width="100"><template #default="{ row }"><el-popover trigger="click" width="420"><template #reference><el-button link type="primary">{{ tableFields(row).length }} 个字段</el-button></template><div class="field-list"><div v-for="field in tableFields(row)" :key="field.name">{{ field.name }} · {{ field.type }} · {{ field.comment }}</div></div></el-popover></template></el-table-column>
      </el-table>
      <el-pagination layout="total, prev, pager, next" v-model:current-page="tablePage" :page-size="20" :total="tableTotal" @current-change="loadTables" />
      <div class="selected-tables"><el-tag v-for="id in skillForm.tableIds" :key="id" closable @close="removeTable(id)">{{ tableLabel(id) }}</el-tag></div>
      <template #footer><span class="muted">已选 {{ skillForm.tableIds.length }} 张，跨项目组的选择会保留。</span><el-button type="primary" @click="tablePicker = false">完成选择</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import SkillMcpBinding from '@/views/mcp/SkillMcpBinding.vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { getUserGroupOptions } from '@/api/user'
import { deleteSkillGroup, getManagedGroupSkills, getSkillGroups,
  removeManagedGroupSkills, saveSkillGroup, getSkillResourceOptions, getSkillExecutionDetail,
  getSkillTableOptions, saveSkillExecution, type SkillTableOption, type SkillResourceOptions, type SkillExecutionWrite,
  type ManagedGroupSkill, type ManagedSkillGroup, type SkillGroupWrite, type SubSkillOption } from '@/api/skill'

const groups = ref<ManagedSkillGroup[]>([]), selected = ref<ManagedSkillGroup | null>(null), skillDetailOpen = ref(false)
const groupKeyword = ref(''), groupPage = ref(1), groupTotal = ref(0), groupLoading = ref(false), groupError = ref('')
const skills = ref<ManagedGroupSkill[]>([]), skillKeyword = ref(''), skillPage = ref(1), skillTotal = ref(0), skillLoading = ref(false), skillError = ref('')
const busy = ref(false), groupDialog = ref(false), editingGroupId = ref<number>(), groupFormRef = ref<FormInstance>()
const groupForm = reactive<SkillGroupWrite>({ groupName: '', description: '', sortOrder: 0, enabled: 1, userGroupIds: [] })
const groupRules = { groupName: [{ required: true, whitespace: true, message: '请输入技能组名称', trigger: 'blur' }] }
const userGroups = ref<Array<{ id: number; groupName: string; enabled: 0 | 1 }>>([]), userGroupLoading = ref(false), userGroupError = ref(''), userGroupKeyword = ref('')
const filteredUserGroups = computed(() => {
  const keyword = userGroupKeyword.value.trim().toLocaleLowerCase()
  if (!keyword) return userGroups.value
  return userGroups.value.filter(item => item.groupName.toLocaleLowerCase().includes(keyword))
})
const selectedUserGroups = computed(() => groupForm.userGroupIds.map(id => userGroups.value.find(item => item.id === id) || { id, groupName: `用户组 #${id}`, enabled: 0 as const }))
const filteredAllSelected = computed(() => filteredUserGroups.value.length > 0 && filteredUserGroups.value.every(item => groupForm.userGroupIds.includes(item.id)))
const filteredSelectedCount = computed(() => filteredUserGroups.value.filter(item => groupForm.userGroupIds.includes(item.id)).length)
const skillDialog = ref(false), editingSkill = ref<ManagedGroupSkill | null>(null), skillFormRef = ref<FormInstance>()
const subSkillOptions = ref<SubSkillOption[]>([]), subSkillLoading = ref(false), subSkillError = ref('')
const missingSubSkillIds = computed(() => skillForm.subSkillIds.filter(id => !subSkillOptions.value.some(item => item.id === id)))
let skillScope: { skillType: 1 | 2; projectGroupId: number | null } = { skillType: 1, projectGroupId: null }
const skillForm = reactive<SkillExecutionWrite>({ skillName: '', skillDescription: '', ruleContent: '', skillLevelType: 1, subSkillIds: [], enabled: 1, intentLlmId: null, taskLlmId: null, executLlmId: null, summaryLlmId: null, temperature: null, tableIds: [], tenantIds: [] })
const mcpRef = ref<InstanceType<typeof SkillMcpBinding>>(), mcpReady = ref(false)
const resourceOptions = reactive<SkillResourceOptions>({ models: [], tenants: [], projectGroups: [] })
// 四类模型与废弃的智能体保持一致：意图筛选 / 任务分解 / 执行代码 / 总结。
// 按 MODEL_CONFIG.TYPE 过滤可选模型，避免把总结模型选到执行位上。
const modelFields: Array<{ field: 'intentLlmId' | 'taskLlmId' | 'executLlmId' | 'summaryLlmId'; type: 1 | 2 | 3 | 4; label: string; placeholder: string; hint: string }> = [
  { field: 'intentLlmId', type: 1, label: '意图模型', placeholder: '不选则使用公司默认模型', hint: '负责意图识别，判断问题是否命中本技能。' },
  { field: 'taskLlmId', type: 2, label: '任务分解模型', placeholder: '不选则使用公司默认模型', hint: '负责把问题拆解为可执行的步骤。' },
  { field: 'executLlmId', type: 3, label: '执行模型', placeholder: '不选则使用公司默认模型', hint: '负责调用数据表、知识库等工具生成执行结果。' },
  { field: 'summaryLlmId', type: 4, label: '总结模型', placeholder: '不选则使用公司默认模型', hint: '负责汇总执行结果，并结合知识图谱补充输出。' },
]
type SkillModelField = typeof modelFields[number]['field']
function modelsOfType(type: number) {
  return resourceOptions.models
    .filter(item => Number(item.type) === type)
    .map(item => ({ ...item, label: item.model + '（ID ' + item.id + '）' }))
}
function orphanModel(field: SkillModelField, type: number) {
  const selected = skillForm[field]
  return !!selected && !resourceOptions.models.some(item => item.id === selected && Number(item.type) === type)
}
const resourceLoading = ref(false), resourceError = ref(''), tablePicker = ref(false), tableProjectId = ref<number>()
const tableKeyword = ref(''), tablePage = ref(1), tableTotal = ref(0), tableLoading = ref(false), tableError = ref('')
const tableRows = ref<SkillTableOption[]>([]), selectedTables = ref<SkillTableOption[]>([])
let resourceSequence = 0, tableSequence = 0, subSkillSequence = 0
const skillRules = { skillName: [{ required: true, whitespace: true, message: '请输入技能名称', trigger: 'blur' }], ruleContent: [{ required: true, whitespace: true, message: '请输入执行规则', trigger: 'blur' }] }
let groupSequence = 0, skillSequence = 0, userSequence = 0
let disposed = false
const errorText = (e: any): string => {
  const value = e?.response?.data?.message || e?.response?.data?.detail || e?.message
  if (Array.isArray(value)) return value.map(item => item.msg || '输入内容不符合要求').join('；')
  return typeof value === 'string' ? value : '操作失败，请重试'
}
const checked = <T,>(response: { success: boolean; message?: string; data: T }): T => {
  if (!response.success) throw new Error(response.message || '操作失败')
  return response.data
}

async function loadGroups() {
  const seq = ++groupSequence
  groupLoading.value = true; groupError.value = ''
  try {
    const data = checked(await getSkillGroups({ keyword: groupKeyword.value, pageNo: groupPage.value, pageSize: 10 }))
    if (seq !== groupSequence || disposed) return
    if (!data.list.length && data.total > 0 && groupPage.value > 1) { groupPage.value--; await loadGroups(); return }
    groups.value = data.list; groupTotal.value = data.total
    if (selected.value) {
      const fresh = data.list.find(group => group.id === selected.value?.id)
      if (fresh) selected.value = fresh
    }
  } catch (e) { if (seq === groupSequence && !disposed) { groupError.value = errorText(e); groups.value = []; groupTotal.value = 0 } }
  finally { if (seq === groupSequence && !disposed) groupLoading.value = false }
}
function searchGroups() { groupPage.value = 1; void loadGroups() }
function openSkillDetail(group: ManagedSkillGroup) {
  if (busy.value) return
  const changed = selected.value?.id !== group.id || !skillDetailOpen.value
  selected.value = group
  skillDetailOpen.value = true
  if (changed) { ++skillSequence; skills.value = []; skillTotal.value = 0; skillError.value = ''; skillPage.value = 1; skillKeyword.value = ''; void loadSkills() }
}
async function loadSkills() {
  const id = selected.value?.id
  if (!id) return
  const seq = ++skillSequence
  skillLoading.value = true; skillError.value = ''
  try {
    const data = checked(await getManagedGroupSkills(id, { keyword: skillKeyword.value, pageNo: skillPage.value, pageSize: 10 }))
    if (seq !== skillSequence || disposed || selected.value?.id !== id) return
    if (!data.list.length && data.total > 0 && skillPage.value > 1) { skillPage.value--; await loadSkills(); return }
    skills.value = data.list; skillTotal.value = data.total
  } catch (e) { if (seq === skillSequence && !disposed) { skillError.value = errorText(e); skills.value = []; skillTotal.value = 0 } }
  finally { if (seq === skillSequence && !disposed) skillLoading.value = false }
}
function searchSkills() { skillPage.value = 1; void loadSkills() }
async function loadUserGroups() {
  const seq = ++userSequence
  userGroupLoading.value = true; userGroupError.value = ''
  try { const data = checked(await getUserGroupOptions(true)); if (seq === userSequence && !disposed) userGroups.value = data.list }
  catch (e) { if (seq === userSequence && !disposed) userGroupError.value = errorText(e) }
  finally { if (seq === userSequence && !disposed) userGroupLoading.value = false }
}
function selectFilteredUserGroups() {
  const ids = new Set(groupForm.userGroupIds)
  for (const item of filteredUserGroups.value) ids.add(item.id)
  groupForm.userGroupIds = [...ids]
}
function clearFilteredUserGroups() {
  const visible = new Set(filteredUserGroups.value.map(item => item.id))
  groupForm.userGroupIds = groupForm.userGroupIds.filter(id => !visible.has(id))
}
function removeUserGroup(id: number) { groupForm.userGroupIds = groupForm.userGroupIds.filter(item => item !== id) }
function openGroup(group?: ManagedSkillGroup) {
  if (busy.value) return
  editingGroupId.value = group?.id
  userGroupKeyword.value = ''
  Object.assign(groupForm, { groupName: group?.groupName || '', description: group?.description || '', sortOrder: group?.sortOrder || 0, enabled: group?.enabled ?? 1, userGroupIds: [...(group?.userGroupIds || [])] })
  groupFormRef.value?.clearValidate(); groupDialog.value = true; void loadUserGroups()
}
async function submitGroup() {
  if (busy.value || userGroupLoading.value || userGroupError.value || !await groupFormRef.value?.validate().catch(() => false)) return
  busy.value = true
  try {
    checked(await saveSkillGroup({ ...groupForm, groupName: groupForm.groupName.trim(), userGroupIds: [...groupForm.userGroupIds] }, editingGroupId.value))
    groupDialog.value = false; ElMessage.success('技能组已保存')
  } catch (e) { ElMessage.error(errorText(e)); return }
  finally { busy.value = false }
  await loadGroups()
}
async function confirmDeleteGroup(group = selected.value) {
  if (!group || busy.value) return
  try { await ElMessageBox.confirm(`确定物理删除技能组“${group.groupName}”及其用户组授权吗？组内存在技能时无法删除。`, '删除技能组', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) } catch { return }
  busy.value = true
  try { checked(await deleteSkillGroup(group.id)); if (selected.value?.id === group.id) { skillDetailOpen.value = false; selected.value = null }; ElMessage.success('技能组已删除') }
  catch (e) { ElMessage.error(errorText(e)); return }
  finally { busy.value = false }
  await loadGroups()
}
async function confirmRemove(skill: ManagedGroupSkill) {
  const id = selected.value?.id
  if (!id || busy.value) return
  try { await ElMessageBox.confirm(`确定将“${skill.skillName}”移出技能组？技能会保留，并恢复原有授权方式，不再受本技能组的用户组限制。`, '移出技能', { type: 'warning', confirmButtonText: '确认移出', cancelButtonText: '取消' }) } catch { return }
  busy.value = true
  try { checked(await removeManagedGroupSkills(id, [skill.id])); ElMessage.success('技能已移出') }
  catch (e) { ElMessage.error(errorText(e)); return }
  finally { busy.value = false }
  await Promise.all([loadGroups(), loadSkills()])
}
function subSkillIdList(value: string | number[] | null | undefined) {
  if (Array.isArray(value)) return value.map(Number).filter(id => id > 0)
  return String(value || '').split(',').map(Number).filter(id => id > 0)
}
function handleSkillLevelChange(value: string | number | boolean | undefined) {
  if (Number(value) === 2) skillForm.subSkillIds = []
  else void loadSubSkillOptions()
}
async function loadSubSkillOptions() {
  const groupId = selected.value?.id
  if (skillForm.skillLevelType !== 1 || !groupId) { subSkillOptions.value = []; subSkillError.value = ''; return }
  const seq = ++subSkillSequence
  subSkillLoading.value = true; subSkillError.value = ''
  try {
    const collected: ManagedGroupSkill[] = []
    let page = 1
    let total = 0
    do {
      const data = checked(await getManagedGroupSkills(groupId, { pageNo: page, pageSize: 100 }))
      if (seq !== subSkillSequence || disposed || !skillDialog.value || selected.value?.id !== groupId) return
      collected.push(...data.list)
      total = data.total
      page += 1
    } while (collected.length < total && page <= 20)
    if (seq !== subSkillSequence || disposed || !skillDialog.value) return
    subSkillOptions.value = collected.filter(item => item.id !== editingSkill.value?.id && item.enabled === 1 && Number(item.skillLevelType) === 2 && item.skillType === skillScope.skillType && (item.projectGroupId ?? null) === (skillScope.projectGroupId ?? null))
  } catch (e) { if (seq === subSkillSequence && !disposed) { subSkillError.value = errorText(e); subSkillOptions.value = [] } }
  finally { if (seq === subSkillSequence && !disposed) subSkillLoading.value = false }
}
function openSkill(skill?: ManagedGroupSkill) {
  if (busy.value) return
  editingSkill.value = skill || null
  skillScope = { skillType: skill?.skillType || 1, projectGroupId: null }
  Object.assign(skillForm, { skillName: skill?.skillName || '', skillDescription: skill?.skillDescription || '', ruleContent: skill?.ruleContent || '', enabled: skill?.enabled ?? 1,
    skillLevelType: skill?.skillLevelType || 1, subSkillIds: subSkillIdList(skill?.subSkillIds), intentLlmId: null, taskLlmId: null, executLlmId: null, summaryLlmId: null, temperature: null, tableIds: [], tenantIds: [] })
  selectedTables.value = []; subSkillOptions.value = []; subSkillError.value = ''; mcpReady.value = false
  skillFormRef.value?.clearValidate(); skillDialog.value = true; void loadSkillResources()
}
async function loadSkillResources() {
  const groupId = selected.value?.id, skillId = editingSkill.value?.id, seq = ++resourceSequence
  if (!groupId) return
  resourceLoading.value = true; resourceError.value = ''
  try {
    const [choices, saved] = await Promise.all([getSkillResourceOptions(), skillId ? getSkillExecutionDetail(groupId, skillId) : Promise.resolve(undefined)])
    if (seq !== resourceSequence || disposed || !skillDialog.value) return
    Object.assign(resourceOptions, checked(choices))
    if (saved) {
      const data = checked(saved)
      Object.assign(skillForm, { skillName: data.skillName, skillDescription: data.skillDescription || '', ruleContent: data.ruleContent || '',
        enabled: data.enabled, intentLlmId: data.intentLlmId, taskLlmId: data.taskLlmId, executLlmId: data.executLlmId, summaryLlmId: data.summaryLlmId,
        temperature: data.temperature, tableIds: [...data.tableIds], tenantIds: [...data.tenantIds],
        skillLevelType: data.skillLevelType, subSkillIds: subSkillIdList(data.subSkillIds) })
      selectedTables.value = data.tables
      skillScope = { skillType: data.skillType || 1, projectGroupId: data.projectGroupId }
    }
    if (seq === resourceSequence && !disposed && skillDialog.value) void loadSubSkillOptions()
  } catch (e) { if (seq === resourceSequence && !disposed) resourceError.value = errorText(e) }
  finally { if (seq === resourceSequence && !disposed) resourceLoading.value = false }
}
function tableLabel(id: number) { const row = selectedTables.value.find(item => item.id === id); return row ? row.projectGroupName + ' / ' + row.tableName : '表 ID ' + id + '（已失效或未加载）' }
function removeTable(id: number) { skillForm.tableIds = skillForm.tableIds.filter(item => item !== id); selectedTables.value = selectedTables.value.filter(item => item.id !== id) }
function toggleTable(row: SkillTableOption, value: unknown) {
  if (!value) { removeTable(row.id); return }
  if (skillForm.tableIds.includes(row.id)) return
  if (skillForm.tableIds.length >= 100) { ElMessage.warning('每个技能最多选择100张数据表'); return }
  skillForm.tableIds.push(row.id); selectedTables.value.push(row)
}
function tableFields(row: SkillTableOption) {
  try { const fields = typeof row.columnsJson === 'string' ? JSON.parse(row.columnsJson) : row.columnsJson
    return Object.entries(fields || {}).map(([name, item]: [string, any]) => ({ name, type: item.type || '', comment: item.remark || item.columnComment || '' }))
  } catch { return [] }
}
function openTablePicker() { tablePicker.value = true; tableProjectId.value ||= resourceOptions.projectGroups[0]?.id; tableKeyword.value = ''; tablePage.value = 1; void loadTables() }
async function loadTables() {
  const seq = ++tableSequence
  if (!tableProjectId.value) { tableRows.value = []; tableTotal.value = 0; return }
  tableLoading.value = true; tableError.value = ''
  try { const data = checked(await getSkillTableOptions({ projectGroupId: tableProjectId.value, keyword: tableKeyword.value, pageNo: tablePage.value, pageSize: 20 }))
    if (seq === tableSequence && !disposed) { tableRows.value = data.list; tableTotal.value = data.total }
  } catch (e) { if (seq === tableSequence && !disposed) { tableError.value = errorText(e); tableRows.value = []; tableTotal.value = 0 } }
  finally { if (seq === tableSequence && !disposed) tableLoading.value = false }
}
async function submitSkill() {
  const id = selected.value?.id
  if (!id || busy.value || resourceLoading.value || resourceError.value || !mcpReady.value || !await skillFormRef.value?.validate().catch(() => false)) return
  busy.value = true
  try {
    const payload = { ...skillForm, updateHierarchy: true, subSkillIds: skillForm.skillLevelType === 2 ? [] : [...skillForm.subSkillIds], tableIds: [...skillForm.tableIds], tenantIds: [...skillForm.tenantIds], mcpBindings: mcpRef.value?.getBindings() || [], skillName: skillForm.skillName.trim(), ruleContent: skillForm.ruleContent.trim() }
    checked(await saveSkillExecution(id, editingSkill.value?.id, payload))
    skillDialog.value = false; ElMessage.success('技能已保存')
  } catch (e) { ElMessage.error(errorText(e)); return }
  finally { busy.value = false }
  await Promise.all([loadGroups(), loadSkills()])
}
function organizationChanged() { ++groupSequence; ++skillSequence; ++userSequence; ++resourceSequence; ++subSkillSequence; ++tableSequence; groupDialog.value = false; skillDialog.value = false; skillDetailOpen.value = false; tablePicker.value = false; selected.value = null; skills.value = []; groupPage.value = 1; void loadGroups() }
onMounted(() => { void loadGroups(); window.addEventListener('organization-changed', organizationChanged) })
onBeforeUnmount(() => { disposed = true; window.removeEventListener('organization-changed', organizationChanged) })
</script>

<style scoped lang="scss">
.skill-group-page { padding: 24px; }
.page-heading, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.page-heading { margin-bottom: 20px; h2 { margin: 0 0 8px; } p { margin: 0; color: #68778c; } }
.group-panel { min-width: 0; &.is-saving { pointer-events: none; } }
.group-panel :deep(.el-table__row) { cursor: pointer; }
.group-panel :deep(.el-tag) { margin: 0 6px 6px 0; }
.muted { color: #758297; font-size: 13px; line-height: 1.7; }
.group-description { white-space: pre-wrap; margin: 0; }
.authorization, .skill-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
.skill-toolbar { .el-input { flex: 1; min-width: 180px; } }
.user-group-picker { width: 100%; }
.user-group-list { max-height: 220px; overflow: auto; border: 1px solid var(--el-border-color); border-radius: 8px; padding: 8px 12px; }
.user-group-list :deep(.el-checkbox-group) { display: flex; flex-direction: column; align-items: flex-start; }
.user-group-list :deep(.el-checkbox) { height: auto; min-height: 32px; margin-right: 0; max-width: 100%; }
.user-group-list :deep(.el-checkbox__label) { white-space: normal; overflow-wrap: anywhere; }
.el-pagination { margin-top: 18px; justify-content: flex-end; }
.el-alert { margin: 12px 0; }
.resource-block { width: 100%; }
.selected-tables { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.field-list { max-height: 280px; overflow: auto; line-height: 1.8; word-break: break-word; }
:global(.skill-editor .el-dialog__body) { max-height: 68vh; overflow-y: auto; }
@media (max-width: 1100px) { .skill-group-page { padding: 14px; } }
</style>
