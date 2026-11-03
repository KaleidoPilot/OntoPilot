<template>
  <div class="agent-container">
    <el-card class="main-card">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <div class="search-inputs">
          <el-input v-model="searchForm.agentName" placeholder="智能体名称" class="round-input" clearable @keyup.enter="handleSearch" />
          <el-input v-model="searchForm.key" placeholder="调用Key" class="round-input" clearable @keyup.enter="handleSearch" />
          <el-button type="primary" class="search-btn" :icon="Search" @click="handleSearch">检索</el-button>
        </div>
        <div class="action-buttons">
          <el-button type="primary" class="add-btn" :icon="Plus" @click="handleAdd">创建智能体</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-wrapper" v-loading="loading">
        <el-table
          :data="agentList"
          style="width: 100%"
          size="large"
          :header-cell-style="{ background: '#f8fafc', color: '#1e293b', fontWeight: '600', height: '60px' }"
          :cell-style="{ height: '57px' }"
          class="custom-table"
        >
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="agentName" label="智能体名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="key" label="调用Key" min-width="150" />
          <el-table-column label="技能" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ getSkillNames(row.skillIds) }}</template>
          </el-table-column>
          <el-table-column prop="agentDescription" label="描述" min-width="180" show-overflow-tooltip />
          <!-- <el-table-column prop="temperature" label="温度" min-width="80" /> -->
          <el-table-column prop="createTime" label="创建时间" min-width="170" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="scope">
              <div class="operation-icons">
                <el-icon class="op-icon edit" title="编辑配置" @click="handleEdit(scope.row)"><Edit /></el-icon>
                <el-icon class="op-icon config" title="调试预览" @click="handleConfig(scope.row)"><Monitor /></el-icon>
                <el-icon class="op-icon delete" title="删除" @click="handleDelete(scope.row)"><Delete /></el-icon>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 30, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          background
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '创建智能体' : '编辑智能体'"
      width="850px"
      destroy-on-close
      class="custom-dialog"
    >
      <el-form :model="form" label-width="140px" ref="formRef" :rules="rules" class="agent-form">
        <el-row :gutter="20">
          <el-col :span="dialogType === 'add' ? 24 : 24">
            <el-form-item label="智能体名称" prop="agentName">
              <el-input v-model="form.agentName" placeholder="如：粤语客服助手" />
            </el-form-item>
          </el-col>
          <!-- <el-col :span="12" v-if="dialogType === 'edit'">
            <el-form-item label="调用 Key" prop="key">
              <el-input v-model="form.key" placeholder="后台自动生成" disabled />
            </el-form-item>
          </el-col> -->
        </el-row>

        <el-form-item label="技能选择" prop="skillIds">
          <el-tree-select
            v-model="form.skillIds"
            :data="projectGroupTree"
            multiple
            :render-after-expand="false"
            show-checkbox
            check-strictly
            node-key="id"
            :props="{ label: 'label', children: 'children', class: getTreeNodeClass }"
            placeholder="请选择技能"
            style="width: 100%"
            popper-class="custom-agent-tree-select"
            :max-collapse-tags="5"
            collapse-tags-tooltip
          >
            <template #default="{ node, data }">
              <div style="display: flex; justify-content: space-between; width: 100%; align-items: center; padding-right: 8px;">
                <span>{{ node.label }}</span>
                <el-button
                  v-if="isGroup(data) && hasSkills(data)"
                  type="primary"
                  link
                  size="small"
                  @click.stop="toggleGroupSelection(data)"
                >
                  {{ isGroupAllSelected(data) ? '取消全选' : '全选' }}
                </el-button>
              </div>
            </template>
          </el-tree-select>
        </el-form-item>

        <!-- 技能没匹配上时，才会按这里选的模板编排取数并生成报告，最多绑多个但执行时只会命中一个 -->
        <el-form-item label="报告模板" prop="templateIdsArray">
          <el-select
            v-model="form.templateIdsArray"
            multiple
            clearable
            :max-collapse-tags="3"
            collapse-tags-tooltip
            placeholder="技能匹配失败时，按所选模板编排取数并生成报告"
            style="width: 100%"
          >
            <el-option v-for="item in templateOptions" :key="item.id" :label="item.skillName" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-alert v-if="bindingOptionsError" :title="bindingOptionsError" type="error" :closable="false" />

        <el-form-item label="智能体描述" prop="agentDescription">
          <el-input v-model="form.agentDescription" type="textarea" :rows="2" placeholder="描述用途" />
        </el-form-item>

        <el-form-item label="系统提示词" prop="systemPrompt">
          <el-input v-model="form.systemPrompt" type="textarea" :rows="8" placeholder="定义角色、任务、约束等" />
        </el-form-item>

        <!-- <el-form-item label="用户提示词模板" prop="userPromptTemplate">
          <el-input v-model="form.userPromptTemplate" type="textarea" :rows="6" placeholder="支持变量占位，如 {{text}}" />
        </el-form-item> -->

        <div class="form-section-title" style="margin-left: 140px; margin-bottom: 16px; font-weight: bold;">模型配置</div>
        <el-alert v-if="modelOptionsError" :title="modelOptionsError" type="error" :closable="false"><template #default><el-button link @click="fetchModelOptions">重新加载模型选项</el-button></template></el-alert>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="意图模型" prop="intentLlmId">
              <el-select v-model="form.intentLlmId" placeholder="请选择意图模型" aria-label="意图模型" clearable filterable :loading="modelOptionsLoading" :disabled="modelOptionsLoading || !!modelOptionsError || bindingOptionsLoading || !!bindingOptionsError">
                <el-option v-for="item in intentModelOptions" :key="item.id" :label="item.model" :value="item.id" />
                <el-option v-if="form.intentLlmId && !intentModelOptions.some(item => item.id === form.intentLlmId)" :value="form.intentLlmId" label="原意图模型已停用或不可用" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务分解模型" prop="taskLlmId">
              <el-select v-model="form.taskLlmId" placeholder="请选择任务分解模型" aria-label="任务分解模型" clearable filterable :loading="modelOptionsLoading" :disabled="modelOptionsLoading || !!modelOptionsError">
                <el-option v-for="item in taskModelOptions" :key="item.id" :label="item.model" :value="item.id" />
                <el-option v-if="form.taskLlmId && !taskModelOptions.some(item => item.id === form.taskLlmId)" :value="form.taskLlmId" label="原任务模型已停用或不可用" disabled />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="执行模型(代码)" prop="executLlmId">
              <el-select v-model="form.executLlmId" placeholder="请选择执行模型" aria-label="执行模型(代码)" clearable filterable :loading="modelOptionsLoading" :disabled="modelOptionsLoading || !!modelOptionsError">
                <el-option v-for="item in executModelOptions" :key="item.id" :label="item.model" :value="item.id" />
                <el-option v-if="form.executLlmId && !executModelOptions.some(item => item.id === form.executLlmId)" :value="form.executLlmId" label="原执行模型已停用或不可用" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="总结模型" prop="summaryLlmId">
              <el-select v-model="form.summaryLlmId" placeholder="请选择总结模型" aria-label="总结模型" clearable filterable :loading="modelOptionsLoading" :disabled="modelOptionsLoading || !!modelOptionsError">
                <el-option v-for="item in summaryModelOptions" :key="item.id" :label="item.model" :value="item.id" />
                <el-option v-if="form.summaryLlmId && !summaryModelOptions.some(item => item.id === form.summaryLlmId)" :value="form.summaryLlmId" label="原总结模型已停用或不可用" disabled />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="温度 (Temp)" prop="temperature">
              <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input :show-input-controls="false" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="核采样 (Top P)" prop="topP">
              <el-slider v-model="form.topP" :min="0" :max="1" :step="0.1" show-input :show-input-controls="false" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="form-section-title" style="margin-left: 140px; margin-bottom: 16px; font-weight: bold;">知识库检索配置</div>

        <el-form-item label="关联知识库" prop="tenantIdsArray">
          <el-select 
            v-model="form.tenantIdsArray" 
            multiple 
            :max-collapse-tags="5"
            collapse-tags-tooltip
            placeholder="请选择要关联的知识库" 
            style="width: 100%"
          >
            <el-option 
              v-for="item in tenantOptions" 
              :key="item.id" 
              :label="item.name" 
              :value="String(item.id)" 
            />
          </el-select>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="返回数量 (Top K)" prop="tenantTopK">
              <el-input-number v-model="form.tenantTopK" :min="1" :max="50" style="width: 100%" placeholder="检索返回文档数" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最低置信度" prop="tenantScore">
              <el-slider v-model="form.tenantScore" :min="0" :max="1" :step="0.01" show-input :show-input-controls="false" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm" :loading="submitLoading" :disabled="modelOptionsLoading || !!modelOptionsError || bindingOptionsLoading || !!bindingOptionsError">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Search, Plus, Edit, Delete, Monitor } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAgentList, insertAgent, updateAgent, deleteLjAgent, getSkillTree, getTenantList, getAgentBindings } from '@/api/agent'
import { queryModelConfigs, type ModelConfigItem } from '@/api/system'

const router = useRouter()
const loading = ref(false)
const agentList = ref<any[]>([])

const intentModelOptions = ref<any[]>([])
const taskModelOptions = ref<any[]>([])
const executModelOptions = ref<any[]>([])
const summaryModelOptions = ref<any[]>([])
const modelOptionsLoading = ref(false), modelOptionsError = ref('')
let modelOptionsVersion = 0
const projectGroupTree = ref<any[]>([])
// 可绑定的报告模板，按当前公司从 TEMPLATE_GENERATION 查询
const templateOptions = ref<Array<{ id: string; skillName: string; description?: string }>>([])

const getTreeNodeClass = (data: any) => {
  if (data.type === 'group') {
    // 所有组节点均不可被勾选
    return 'hide-checkbox-node'
  }
  return ''
}

const isGroup = (data: any) => {
  return data.type === 'group'
}

const getAllSkillIds = (nodeData: any): string[] => {
  let ids: string[] = []
  if (nodeData.type === 'skill') {
    // 移除可能存在的 "skill_" 前缀
    ids.push(String(nodeData.originalId || nodeData.id.replace('skill_', '')))
  }
  if (nodeData.children && nodeData.children.length > 0) {
    nodeData.children.forEach((child: any) => {
      ids = ids.concat(getAllSkillIds(child))
    })
  }
  return ids
}

const hasSkills = (groupData: any) => {
  return getAllSkillIds(groupData).length > 0
}

const isGroupAllSelected = (groupData: any) => {
  const skillIds = getAllSkillIds(groupData)
  if (skillIds.length === 0) return false
  return skillIds.every((id: string) => {
    // 检查 form.skillIds 中是否包含不带前缀的 id 或带前缀的 id
    return form.skillIds.includes(id) || form.skillIds.includes(`skill_${id}`)
  })
}

const toggleGroupSelection = (groupData: any) => {
  const skillIds = getAllSkillIds(groupData)
  if (skillIds.length === 0) return
  
  // currentIds 统一存放带 "skill_" 前缀的 ID 用于前端组件勾选状态显示
  const currentIds = new Set(form.skillIds.map(id => id.startsWith('skill_') ? id : `skill_${id}`))
  
  if (isGroupAllSelected(groupData)) {
    skillIds.forEach((id: string) => currentIds.delete(`skill_${id}`))
  } else {
    skillIds.forEach((id: string) => currentIds.add(`skill_${id}`))
  }
  form.skillIds = Array.from(currentIds)
}

const getSkillNames = (skillIds: string | null | undefined) => {
  if (!skillIds) return '-'
  const ids = skillIds.split(',').filter(Boolean)
  
  // Recursively find labels in the tree
  const findLabel = (nodes: any[], originalId: string): string | null => {
    for (const node of nodes) {
      if (node.type === 'skill' && String(node.originalId) === originalId) return node.label
      if (node.children && node.children.length > 0) {
        const found = findLabel(node.children, originalId)
        if (found) return found
      }
    }
    return null
  }

  const names = ids.map(id => {
    // 后端存的已经是去除前缀的 id
    const label = findLabel(projectGroupTree.value, id)
    return label ? label : id
  })
  return names.join(', ')
}
const bindingOptionsLoading = ref(false), bindingOptionsError = ref('')
const tenantOptions = ref<any[]>([])

const searchForm = reactive({
  agentName: '',
  key: ''
})

const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      pageNo: pagination.currentPage,
      pageSize: pagination.pageSize,
      ...searchForm
    }
    const res = await getAgentList(params)
    if (res.success || res.code === 200) {
      agentList.value = res.data.list
      pagination.total = res.data.total
    }
  } catch (error) {
    console.error('Fetch list error:', error)
  } finally {
    loading.value = false
  }
}

const fetchModelOptions = async () => {
  const attempt = ++modelOptionsVersion; modelOptionsLoading.value = true; modelOptionsError.value = ''
  try {
    const allModels: ModelConfigItem[] = []
    for(let pageNo=1;;pageNo++){
      const res = await queryModelConfigs({pageNo,pageSize:100,enabled:1})
      if(!res.success)throw new Error(res.message||'模型选项加载失败')
      allModels.push(...res.data.list)
      if(allModels.length>=res.data.total || !res.data.list.length)break
    }
    if(attempt!==modelOptionsVersion)return
    intentModelOptions.value = allModels.filter(m => m.type === 1 && m.hasApiKey)
    taskModelOptions.value = allModels.filter(m => m.type === 2 && m.hasApiKey)
    executModelOptions.value = allModels.filter(m => m.type === 3 && m.hasApiKey)
    summaryModelOptions.value = allModels.filter(m => m.type === 4 && m.hasApiKey)
  } catch (error) { if(attempt===modelOptionsVersion)modelOptionsError.value=error instanceof Error?error.message:'模型选项加载失败' }
  finally { if(attempt===modelOptionsVersion)modelOptionsLoading.value=false }
}

const fetchTenantOptions = async () => {
  bindingOptionsLoading.value = true; bindingOptionsError.value = ''
  try {
    const [skills, tenants, bindings] = await Promise.all([getSkillTree(), getTenantList(), getAgentBindings()])
    if (!skills.success || !tenants.success) throw new Error(skills.message || tenants.message || '技能和知识库选项加载失败')
    projectGroupTree.value = skills.data || []; tenantOptions.value = tenants.data || []
    templateOptions.value = bindings.data?.templates || []
  } catch (cause) { bindingOptionsError.value = cause instanceof Error ? cause.message : '资源绑定选项加载失败' }
  finally { bindingOptionsLoading.value = false }
}

onMounted(() => {
  fetchList()
  fetchModelOptions()
  fetchTenantOptions()
})

const handleSearch = () => {
  pagination.currentPage = 1
  fetchList()
}

const handleSizeChange = (val: number) => {
  pagination.pageSize = val
  fetchList()
}

const handleCurrentChange = (val: number) => {
  pagination.currentPage = val
  fetchList()
}

// 弹窗表单逻辑
const dialogVisible = ref(false)
const dialogType = ref<'add' | 'edit'>('add')
const submitLoading = ref(false)
const formRef = ref()

const form = reactive({
  id: undefined,
  agentName: '',
  key: '',
  skillIds: [] as string[],
  templateIdsArray: [] as string[],
  agentDescription: '',
  systemPrompt: '',
  userPromptTemplate: '',
  intentLlmId: undefined as number | undefined,
  taskLlmId: undefined as number | undefined,
  executLlmId: undefined as number | undefined,
  summaryLlmId: undefined as number | undefined,
  temperature: 0.7,
  topP: 0.9,
  tenantIdsArray: [] as string[],
  tenantTopK: 5,
  tenantScore: 0.4,
  enabled: 1
})

const rules = {
  agentName: [{ required: true, message: '请输入智能体名称', trigger: 'blur' }],
  systemPrompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }]
}

const handleAdd = () => {
  void fetchModelOptions()
  void fetchTenantOptions()
  dialogType.value = 'add'
  Object.assign(form, {
    id: undefined,
    agentName: '',
    key: '',
    skillIds: [],
    templateIdsArray: [],
    agentDescription: '',
    systemPrompt: '',
    userPromptTemplate: '',
    intentLlmId: undefined,
    taskLlmId: undefined,
    executLlmId: undefined,
    summaryLlmId: undefined,
    temperature: 0.7,
    topP: 0.9,
    tenantIdsArray: [],
    tenantTopK: 5,
    tenantScore: 0.4,
    enabled: 1
  })
  dialogVisible.value = true
  if (formRef.value) formRef.value.clearValidate()
}

const handleEdit = (row: any) => {
  void fetchModelOptions()
  void fetchTenantOptions()
  dialogType.value = 'edit'
  Object.assign(form, row)
  // 回显原来的技能绑定
  form.skillIds = (row.skillIds || '').split(',').filter(Boolean).map((id: string) => `skill_${id}`)
  // 回显报告模板（24 位字符串，逗号拼接）
  form.templateIdsArray = (row.templateIds || '').split(',').filter(Boolean)
  // 回显 tenantIds
  if (row.tenantIds) {
    form.tenantIdsArray = row.tenantIds.split(',').filter((id: string) => id)
  } else {
    form.tenantIdsArray = []
  }
  dialogVisible.value = true
  if (formRef.value) formRef.value.clearValidate()
}

const submitForm = async () => {
  if(modelOptionsLoading.value || modelOptionsError.value || bindingOptionsLoading.value || bindingOptionsError.value)return ElMessage.warning('请等待模型和资源选项加载成功')
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      submitLoading.value = true
      try {
        const submitData = { ...form }
        for(const field of ['intentLlmId','taskLlmId','executLlmId','summaryLlmId'] as const) (submitData as any)[field]=form[field] || null
        // 后台仍使用原来的技能绑定，提交时去除树节点前缀。
        ;(submitData as any).skillIds = form.skillIds.map(id => id.replace('skill_', '')).join(',')
        // 报告模板同样拼成英文逗号串；空数组传空串，后端据此清空 TEMPLATE_IDS
        ;(submitData as any).templateIds = form.templateIdsArray.join(',')
        delete (submitData as any).mcpIds
        // 拼接 tenantIds
        ;(submitData as any).tenantIds = form.tenantIdsArray.join(',')
        // 新增/修改时携带 orgId，取自缓存的 currentOrganization，避免后端多租户校验失败
        const organization = JSON.parse(localStorage.getItem('currentOrganization') || '{}')
        if (organization.id) (submitData as any).orgId = Number(organization.id)

        if (dialogType.value === 'add') {
          const res = await insertAgent(submitData as any)
          if (res.success || res.code === 200) {
            ElMessage.success('创建成功')
            dialogVisible.value = false
            fetchList()
          } else {
            ElMessage.error(res.message || '创建失败')
          }
        } else {
          const res = await updateAgent(submitData as any)
          if (res.success || res.code === 200) {
            ElMessage.success('修改成功')
            dialogVisible.value = false
            fetchList()
          } else {
            ElMessage.error(res.message || '修改失败')
          }
        }
      } catch (error: any) {
        ElMessage.error(error.message || '操作失败')
      } finally {
        submitLoading.value = false
      }
    }
  })
}

const handleDelete = (row: any) => {
  ElMessageBox.confirm('确定要删除该智能体吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await deleteLjAgent({ id: row.id })
      if (res.success || res.code === 200) {
        ElMessage.success('删除成功')
        fetchList()
      } else {
        ElMessage.error(res.message || '删除失败')
      }
    } catch (error: any) {
      ElMessage.error(error.message || '删除失败')
    }
  })
}

const handleConfig = (row: any) => {
  router.push(`/agent/detail/${row.id}`)
}
</script>

<style scoped lang="scss">
.agent-container {
  padding: 24px;
  height: calc(100vh - 60px);
  background-color: var(--bg-dark, #f5f7fa);
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .main-card {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    height: 100%;
    
    :deep(.el-card__body) {
      display: flex;
      flex-direction: column;
      padding: 20px;
      overflow: hidden;
      height: 100%;
    }
  }

  .search-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 4px;
    flex-shrink: 0;

    .search-inputs {
      display: flex;
      gap: 12px;
      align-items: center;

      .round-input {
        width: 240px;
        :deep(.el-input__wrapper) {
          box-shadow: 0 0 0 1px #e2e8f0 inset !important;
          border-radius: 20px !important;
          padding: 8px 20px !important;
          background-color: #f8fafc !important;
          
          &.is-focus, &.is-focused {
            box-shadow: 0 0 0 1px var(--primary-color, #4f6ef7) inset !important;
            background-color: #fff !important;
          }
        }
      }

      .search-btn {
        height: 40px;
        padding: 0 28px;
        border-radius: 20px;
        font-weight: 600;
        transition: all 0.3s;
        &:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(79, 110, 247, 0.3);
        }
      }
    }

    .action-buttons {
      .add-btn {
        height: 40px;
        padding: 0 20px;
        border-radius: 8px;
        font-weight: 600;
      }
    }
  }

  .operation-icons {
    display: flex;
    gap: 12px;
    font-size: 18px;
    color: #4f6ef7;
    
    .op-icon {
      cursor: pointer;
      transition: opacity 0.2s;
      &:hover {
        opacity: 0.7;
      }
      &.delete {
        color: #f56c6c;
      }
      &.config {
        color: #67c23a;
      }
    }
  }

  .pagination-container {
    padding-top: 16px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-shrink: 0;

    :deep(.el-pagination) {
      font-weight: normal;
      
      button, .el-pager li {
        background-color: #f5f7fa !important;
        border-radius: 4px;
        &.is-active {
          background-color: var(--primary-color, #4f6ef7) !important;
          color: #fff !important;
        }
      }
    }
  }

  .table-wrapper {
    flex: 1;
    overflow: hidden;
    margin-bottom: 16px;
    
    .custom-table {
      border-radius: 12px;
      height: 100%;
      box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
      border: 1px solid #e2e8f0;

      :deep(.el-table__inner-wrapper) {
        height: 100% !important;
      }

      :deep(.el-table__inner-wrapper::before) {
        display: none;
      }

      :deep(.el-table__header) {
        th {
          border-bottom: 1px solid #e2e8f0;
        }
      }

      :deep(.el-table__row) {
        td {
          border-bottom: 1px solid #f1f5f9;
        }
        &:last-child td {
          border-bottom: none;
        }
        &:hover > td {
          background-color: #f8fafc !important;
        }
      }
    }
  }

  :deep(.custom-dialog) {
    .el-dialog__body {
      padding-top: 10px;
      padding-bottom: 10px;
    }
    .el-textarea__inner {
      font-family: monospace; /* 提示词通常建议用等宽字体阅读 */
      line-height: 1.6;
    }
  }
}
</style>

<style lang="scss">
.custom-agent-tree-select {
  .hide-checkbox-node > .el-tree-node__content > .el-checkbox {
    display: none !important;
  }
}
</style>
