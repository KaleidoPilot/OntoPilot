<template>
  <div class="agent-detail-container">
    <div class="layout-split">
      
      <!-- 左侧：智能体配置 -->
      <el-card class="left-card config-card">
        <template #header>
          <div class="card-header">
            <span class="title">智能体配置</span>
            <el-button @click="handleBack">返回上级菜单</el-button>
          </div>
        </template>
        
        <el-form 
          :model="form" 
          :rules="rules" 
          ref="formRef" 
          label-width="120px" 
          class="agent-form scrollable-form"
        >
          <div class="form-section-title">基本信息</div>
          <el-form-item label="智能体名称" prop="agentName">
            <el-input v-model="form.agentName" placeholder="如：粤语客服助手" class="round-input" />
          </el-form-item>
          <el-form-item label="调用 Key" prop="key" v-if="form.key">
            <el-input v-model="form.key" placeholder="后台自动生成" class="round-input" disabled />
          </el-form-item>
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
              placeholder="请选择项目组或技能"
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
          <!-- 技能未命中时按这里的模板生成报告；模板来自 TEMPLATE_GENERATION，可多选 -->
          <el-form-item label="报告模板">
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
          <el-alert v-if="bindingOptionsError || modelOptionsError || detailError" :title="bindingOptionsError || modelOptionsError || detailError" type="error" :closable="false" />
          <el-form-item label="智能体描述" prop="agentDescription">
            <el-input v-model="form.agentDescription" type="textarea" :rows="2" placeholder="描述用途" class="round-input" />
          </el-form-item>

          <div class="form-section-title">提示词配置</div>
          <el-form-item label="系统提示词" prop="systemPrompt">
            <el-input v-model="form.systemPrompt" type="textarea" :rows="15" placeholder="System Prompt" class="round-input" />
          </el-form-item>
          <!-- <el-form-item label="用户提示模板" prop="userPromptTemplate">
            <el-input v-model="form.userPromptTemplate" type="textarea" :rows="3" placeholder="支持占位，如 {{text}}" class="round-input" />
          </el-form-item> -->

          <div class="form-section-title">模型配置</div>

          <el-form-item label="意图模型" prop="intentLlmId">
            <el-select v-model="form.intentLlmId" placeholder="请选择意图模型" clearable>
              <el-option v-for="item in intentModelOptions" :key="item.id" :label="item.model" :value="item.id" />
            </el-select>
          </el-form-item>

          <el-form-item label="任务分解模型" prop="taskLlmId">
            <el-select v-model="form.taskLlmId" placeholder="请选择任务分解模型" clearable>
              <el-option v-for="item in taskModelOptions" :key="item.id" :label="item.model" :value="item.id" />
            </el-select>
          </el-form-item>

          <el-form-item label="执行模型(代码)" prop="executLlmId">
            <el-select v-model="form.executLlmId" placeholder="请选择执行模型" clearable>
              <el-option v-for="item in executModelOptions" :key="item.id" :label="item.model" :value="item.id" />
            </el-select>
          </el-form-item>

          <el-form-item label="总结模型" prop="summaryLlmId">
            <el-select v-model="form.summaryLlmId" placeholder="请选择总结模型" clearable>
              <el-option v-for="item in summaryModelOptions" :key="item.id" :label="item.model" :value="item.id" />
            </el-select>
          </el-form-item>

          <div class="form-section-title">参数调整</div>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="温度" prop="temperature">
                <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input :show-input-controls="false" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="核采样" prop="topP">
                <el-slider v-model="form.topP" :min="0" :max="1" :step="0.1" show-input :show-input-controls="false" />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="form-section-title">知识库检索配置</div>
          
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
            <el-col :span="24">
              <el-form-item label="返回数量 (Top K)" prop="tenantTopK">
                <el-input-number v-model="form.tenantTopK" :min="1" :max="50" style="width: 100%" placeholder="检索返回文档数" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="最低置信度" prop="tenantScore">
                <el-slider v-model="form.tenantScore" :min="0" :max="1" :step="0.01" show-input :show-input-controls="false" />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="form-actions">
            <el-button type="primary" class="submit-btn" :loading="submitting" :disabled="detailLoading || !!detailError || modelOptionsLoading || !!modelOptionsError || bindingOptionsLoading || !!bindingOptionsError" @click="submitForm">保存配置</el-button>
          </div>
        </el-form>
      </el-card>

    </div>
  </div>
</template>

<script setup lang="ts">
import { queryModelConfigs } from '@/api/system'
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAgentList, updateAgent, getSkillTree, getTenantList, getAgentBindings } from '@/api/agent'

const route = useRoute()
const router = useRouter()
const intentModelOptions = ref<any[]>([])
const taskModelOptions = ref<any[]>([])
const executModelOptions = ref<any[]>([])
const summaryModelOptions = ref<any[]>([])
const projectGroupTree = ref<any[]>([])

const getTreeNodeClass = (data: any) => {
  if (data.type === 'group') {
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
    return form.skillIds.includes(id) || form.skillIds.includes(`skill_${id}`)
  })
}

const toggleGroupSelection = (groupData: any) => {
  const skillIds = getAllSkillIds(groupData)
  if (skillIds.length === 0) return
  const currentIds = new Set(form.skillIds.map(id => id.startsWith('skill_') ? id : `skill_${id}`))
  
  if (isGroupAllSelected(groupData)) {
    skillIds.forEach((id: string) => currentIds.delete(`skill_${id}`))
  } else {
    skillIds.forEach((id: string) => currentIds.add(`skill_${id}`))
  }
  form.skillIds = Array.from(currentIds)
}

// --- 左侧表单逻辑 ---
const bindingOptionsLoading = ref(false), bindingOptionsError = ref('')
const modelOptionsLoading = ref(false), modelOptionsError = ref('')
const detailLoading = ref(false), detailError = ref('')
const tenantOptions = ref<any[]>([])
// 可绑定的报告模板（按当前公司查询，来自 /agent/binding-options）
const templateOptions = ref<Array<{ id: string; skillName: string; description?: string }>>([])

const formRef = ref()
const submitting = ref(false)

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

const fetchAgentDetail = async () => {
  const id = Number(route.params.id)
  if (!id) { detailError.value = '智能体编号无效'; return }
  detailLoading.value = true; detailError.value = ''
  
  try {
    const res = await getAgentList({ id, pageNo: 1, pageSize: 1 })
    if (res.success || res.code === 200) {
      if (res.data.list && res.data.list.length > 0) {
        const row = res.data.list[0]
        Object.assign(form, row)
        // 回显原来的技能绑定
        form.skillIds = (row.skillIds || '').split(',').filter(Boolean).map((id: string) => `skill_${id}`)
        // 回显绑定的报告模板（24 位字符串，直接按逗号拆分）
        form.templateIdsArray = (row.templateIds || '').split(',').filter(Boolean)
        // 回显 tenantIds
        if (row.tenantIds) {
          form.tenantIdsArray = row.tenantIds.split(',').filter((id: string) => id)
        } else {
          form.tenantIdsArray = []
        }
      } else { throw new Error('智能体不存在或已停用') }
    } else { throw new Error(res.message || '智能体配置加载失败') }
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '智能体配置加载失败'
  } finally { detailLoading.value = false }
}

const fetchModelOptions = async () => {
  modelOptionsLoading.value = true; modelOptionsError.value = ''
  try {
    const allModels: any[] = []
    for (let pageNo = 1; pageNo <= 100; pageNo++) {
      const res = await queryModelConfigs({ pageNo, pageSize: 100, enabled: 1 })
      if (!res.success) throw new Error(res.message || '模型选项加载失败')
      allModels.push(...res.data.list)
      if (!res.data.list.length || allModels.length >= res.data.total) break
    }
    intentModelOptions.value = allModels.filter((m: any) => m.type === 1 && m.hasApiKey)
    taskModelOptions.value = allModels.filter((m: any) => m.type === 2 && m.hasApiKey)
    executModelOptions.value = allModels.filter((m: any) => m.type === 3 && m.hasApiKey)
    summaryModelOptions.value = allModels.filter((m: any) => m.type === 4 && m.hasApiKey)
  } catch (error) {
    modelOptionsError.value = error instanceof Error ? error.message : '模型选项加载失败'
  } finally { modelOptionsLoading.value = false }
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
  fetchAgentDetail()
  fetchModelOptions()
  fetchTenantOptions()
})

const handleBack = () => {
  router.push('/agent/list')
}

const submitForm = async () => {
  if (detailLoading.value || detailError.value || modelOptionsLoading.value || modelOptionsError.value || bindingOptionsLoading.value || bindingOptionsError.value) return
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      submitting.value = true
      try {
        const submitData = { ...form }
        // 后台仍使用原来的技能绑定，提交时去除树节点前缀。
        ;(submitData as any).skillIds = form.skillIds.map(id => id.replace('skill_', '')).join(',')
        delete (submitData as any).mcpIds
        // 拼接 tenantIds
        ;(submitData as any).tenantIds = form.tenantIdsArray.join(',')
        // 拼接模板绑定；空数组会传空串，后端据此清空 TEMPLATE_IDS
        ;(submitData as any).templateIds = form.templateIdsArray.join(',')
        
        const res = await updateAgent(submitData as any)
        if (res.success || res.code === 200) {
          ElMessage.success('配置已保存')
        } else {
          ElMessage.error(res.message || '保存失败')
        }
      } catch (error: any) {
        ElMessage.error(error.message || '保存失败')
      } finally {
        submitting.value = false
      }
    }
  })
}
</script>

<style scoped lang="scss">
.agent-detail-container {
  padding: 24px;
  height: calc(100vh - 60px);
  background-color: var(--bg-dark, #f5f7fa);
  box-sizing: border-box;
  overflow: hidden;

  .layout-split {
    display: flex;
    gap: 24px;
    height: 100%;
    
    .left-card {
      flex: 3;
      display: flex;
      flex-direction: column;
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
      border: none;
      min-width: 0; // 防止撑破 flex

      :deep(.el-card__body) {
        flex: 1;
        overflow: hidden;
        padding: 0;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .title {
          font-size: 16px;
          font-weight: 600;
          color: #1e293b;
          position: relative;
          padding-left: 10px;
          
          &::before {
            content: '';
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 4px;
            height: 14px;
            background-color: var(--primary-color, #4f6ef7);
            border-radius: 2px;
          }
        }
      }

      .scrollable-form {
        height: 100%;
        overflow-y: auto;
        padding: 20px 24px;
        box-sizing: border-box;
        
        /* 隐藏滚动条但保留功能 */
        &::-webkit-scrollbar {
          width: 6px;
        }
        &::-webkit-scrollbar-thumb {
          background-color: #cbd5e1;
          border-radius: 3px;
        }

        .form-section-title {
          font-size: 14px;
          font-weight: 600;
          color: #334155;
          margin: 16px 0 16px;
          padding-bottom: 8px;
          border-bottom: 1px solid #f1f5f9;
          
          &:first-child { margin-top: 0; }
        }

        :deep(.round-input) {
          .el-input__wrapper, .el-textarea__inner {
            box-shadow: 0 0 0 1px #e2e8f0 inset;
            border-radius: 6px;
            background-color: #f8fafc;
            
            &:focus, &.is-focus {
              box-shadow: 0 0 0 1px var(--primary-color, #4f6ef7) inset !important;
              background-color: #fff;
            }
          }
        }

        .form-actions {
          margin-top: 30px;
          text-align: center;
          
          .submit-btn {
            width: 160px;
            height: 40px;
            border-radius: 20px;
            font-size: 15px;
          }
        }
      }
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
