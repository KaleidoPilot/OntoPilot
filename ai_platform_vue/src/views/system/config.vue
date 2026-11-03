<template>
  <div class="config-page">
    <el-card class="config-card" shadow="never">
      <template #header>
        <div class="page-header">
          <h1>系统配置管理</h1>
          <p>当前公司：{{ organizationName }}。沙箱支持配置多条，创建项目组时选择使用。</p>
        </div>
      </template>

      <el-tabs v-model="activeSection" class="config-tabs">
        <el-tab-pane label="数据库说明" name="database" />
        <el-tab-pane label="基础模型配置" name="base-model" />
        <el-tab-pane label="AI 模型配置" name="ai-model" />
        <el-tab-pane label="向量库配置" name="vector" />
        <el-tab-pane label="沙箱配置" name="sandbox" />
      </el-tabs>

      <el-alert
        v-if="errorMessage"
        class="error-alert"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
      >
        <template #default>
          <el-button link type="primary" @click="loadConfigurations">重新加载</el-button>
        </template>
      </el-alert>

      <div v-loading="loading" class="config-content">
        <template v-if="activeSection === 'sandbox'">
          <div class="section-heading">
            <div><h2>沙箱配置</h2><p>沙箱配置数据库连接；具体数据库在项目组导入数据表时选择，由沙箱执行查询。</p></div>
            <el-button type="primary" :disabled="loading || Boolean(errorMessage)" @click="openSandboxDialog()">新增沙箱</el-button>
          </div>
          <el-form inline @submit.prevent="searchSandboxes">
            <el-form-item><el-input v-model="sandboxKeyword" placeholder="搜索沙箱名称或 URL" aria-label="搜索沙箱名称或 URL" clearable @clear="searchSandboxes" /></el-form-item>
            <el-form-item><el-button type="primary" :disabled="loading" @click="searchSandboxes">查询</el-button><el-button @click="resetSandboxSearch">重置</el-button></el-form-item>
          </el-form>
          <el-table :data="pagedSandboxRecords" row-key="id">
            <el-table-column type="index" :index="sandboxRowIndex" label="序号" width="90" />
            <el-table-column label="沙箱名称" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.configJson.name || row.configJson.url || '待配置' }}</template>
            </el-table-column>
            <el-table-column label="URL" min-width="270" show-overflow-tooltip>
              <template #default="{ row }">{{ row.configJson.url || '待配置' }}</template>
            </el-table-column>
            <el-table-column label="Token" width="120">
              <template #default="{ row }">{{ row.configJson.token ? '已配置' : '未设置' }}</template>
            </el-table-column>
            <el-table-column label="数据库" min-width="160">
              <template #default="{ row }">{{ row.configJson.database?.host ? `${row.configJson.database.host}:${row.configJson.database.port || 3306}` : '待补充连接配置' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }"><el-tag :type="row.enabled === 1 ? 'success' : 'info'">{{ row.enabled === 1 ? '已启用' : '已停用' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="230" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :disabled="sandboxBusyId !== null" @click="openSandboxDialog(row)">编辑</el-button>
                <el-button link type="primary" :loading="sandboxBusyId === row.id" :disabled="sandboxBusyId !== null" @click="toggleSandbox(row)">{{ row.enabled === 1 ? '停用' : '启用' }}</el-button>
                <el-button link type="danger" :disabled="sandboxBusyId !== null" @click="removeSandbox(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="sandboxAppliedKeyword ? '未找到匹配的沙箱' : '暂无沙箱，请先新增沙箱'" /></template>
          </el-table>
          <div class="sandbox-pagination">
            <el-pagination v-model:current-page="sandboxPage" v-model:page-size="sandboxPageSize" :page-sizes="[5, 10, 20, 50]" :total="filteredSandboxRecords.length" layout="total, sizes, prev, pager, next" @size-change="sandboxPage = 1" />
          </div>
        </template>
        <template v-else-if="activeSection === 'ai-model'">
          <div class="section-heading"><div><h2>AI 模型配置</h2></div><el-button type="primary" :disabled="modelBusy || modelLoading || !!modelError" @click="openModelDialog()">新增模型</el-button></div>
          <el-alert v-if="modelError" :title="modelError" type="error" show-icon :closable="false"><template #default><el-button link @click="loadModels">重新加载模型</el-button></template></el-alert>
          <el-form inline @submit.prevent="searchModels">
            <el-form-item><el-input v-model="modelKeyword" :disabled="modelBusy" clearable placeholder="搜索模型名称" aria-label="搜索模型名称" @clear="searchModels" /></el-form-item>
            <el-form-item><el-select v-model="modelType" :disabled="modelBusy" clearable placeholder="全部用途" aria-label="模型用途筛选" style="width:180px" @change="searchModels"><el-option v-for="block in agentModelBlocks" :key="block.modelType" :label="block.title" :value="block.modelType" /></el-select></el-form-item>
            <el-form-item><el-button :disabled="modelBusy || modelLoading" @click="searchModels">查询模型</el-button></el-form-item>
            <el-form-item><el-button type="danger" :disabled="modelBusy || modelLoading || !!modelError || !selectedModels.length" @click="removeModels()">批量删除{{ selectedModels.length ? `（${selectedModels.length}）` : '' }}</el-button></el-form-item>
          </el-form>
          <el-table ref="modelTable" v-loading="modelLoading" :data="modelRows" row-key="id" :empty-text="modelError ? '加载失败，请重新加载' : '暂无模型，点击新增模型开始配置'" @selection-change="selectedModels = $event">
            <el-table-column type="selection" width="50" fixed="left" :selectable="() => !modelBusy && !modelLoading" />
            <el-table-column prop="model" label="模型名称" min-width="200" fixed="left" show-overflow-tooltip />
            <el-table-column label="模型用途" width="160"><template #default="{ row }">{{ modelTypeLabel(row.type) }}</template></el-table-column>
            <el-table-column prop="baseUrl" label="Base URL" min-width="280" show-overflow-tooltip />
            <el-table-column label="API Key" width="120"><template #default="{ row }">{{ row.hasApiKey ? '已配置' : '未配置' }}</template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="250" fixed="right"><template #default="{ row }"><el-button link type="primary" :disabled="modelBusy || modelLoading" @click="openModelDialog(row)">编辑模型</el-button><el-button link type="primary" :disabled="modelBusy || modelLoading" @click="toggleModel(row)">{{ row.enabled ? '停用模型' : '启用模型' }}</el-button><el-button link type="danger" :disabled="modelBusy || modelLoading" @click="removeModels(row)">删除模型</el-button></template></el-table-column>
          </el-table>
          <div class="sandbox-pagination"><el-pagination v-model:current-page="modelPage" :disabled="modelBusy || modelLoading" :page-size="10" :total="modelTotal" layout="total, prev, pager, next" /></div>
        </template>
        <el-form v-else class="inline-config-form" :model="form" label-width="110px" status-icon @submit.prevent>
          <div class="section-heading">
            <div>
              <h2>{{ sectionTitle }}</h2>
              <p>{{ sectionDescription }}</p>
            </div>
            <el-form-item v-if="activeSection !== 'database'" class="section-status" label="状态">
              <el-switch
                v-model="currentEnabled"
                :active-value="1"
                :inactive-value="0"
                active-text="启用"
                inactive-text="停用"
              />
            </el-form-item>
          </div>

          <template v-if="activeSection === 'database'">
            <el-alert title="客户业务数据通过项目组绑定的沙箱读取" description="请在沙箱配置中维护沙箱地址和对应数据库连接。查询在沙箱内执行；平台账号、公司和技能配置仍使用平台数据库。" type="info" show-icon :closable="false" />
          </template>

          <template v-else-if="activeSection === 'base-model'">
            <section v-for="block in baseModelBlocks" :key="block.key" class="model-block">
              <div class="model-block-title">
                <h3>{{ block.title }}</h3>
                <span>{{ block.description }}</span>
              </div>
              <div class="field-grid">
                <el-form-item label="模型名称" :required="block.required">
                  <el-input v-model="form.baseModels[block.key].model" />
                </el-form-item>
                <el-form-item label="API Key" :required="block.required">
                  <el-input
                    v-model="form.baseModels[block.key].apiKey"
                    :type="isSecretVisible(`base.${block.key}`) ? 'text' : 'password'"
                    autocomplete="new-password"
                  >
                    <template #suffix>
                      <el-button
                        link
                        :icon="isSecretVisible(`base.${block.key}`) ? Hide : View"
                        :loading="isSecretLoading(`base.${block.key}`)"
                        :aria-label="isSecretVisible(`base.${block.key}`) ? '隐藏API Key' : '显示API Key'"
                        @click="toggleSecretVisibility(`base.${block.key}`, primaryRecords['base-model'])"
                      />
                    </template>
                  </el-input>
                </el-form-item>
                <el-form-item class="full-field" label="Base URL" :required="block.required">
                  <el-input v-model="form.baseModels[block.key].baseUrl" placeholder="https://..." />
                </el-form-item>
              </div>
            </section>
          </template>

          <template v-else-if="activeSection === 'vector'">
            <div class="field-grid">
              <el-form-item label="主机地址" required>
                <el-input v-model="form.vector.host" />
              </el-form-item>
              <el-form-item label="端口" required>
                <el-input-number v-model="form.vector.port" :min="1" :max="65535" :controls="false" />
              </el-form-item>
              <el-form-item label="数据库名" required>
                <el-input v-model="form.vector.dbName" />
              </el-form-item>
              <el-form-item label="集合名称" required>
                <el-input v-model="form.vector.collectionName" />
              </el-form-item>
              <el-form-item label="向量维度" required>
                <el-input-number v-model="form.vector.vectorDim" :min="1" :controls="false" />
              </el-form-item>
              <el-form-item label="索引类型">
                <el-input v-model="form.vector.indexType" />
              </el-form-item>
              <el-form-item label="索引 nlist">
                <el-input-number v-model="form.vector.nlist" :min="1" :controls="false" />
              </el-form-item>
            </div>
          </template>

          <div v-if="activeSection !== 'database'" class="config-actions">
            <el-button
              type="primary"
              :loading="submitting"
              :disabled="loading || Boolean(errorMessage)"
              @click="saveCurrentSection"
            >
              保存配置
            </el-button>
          </div>
        </el-form>
      </div>
    </el-card>
    <el-dialog v-model="modelDialog" :title="editingModel ? '编辑模型' : '新增模型'" width="min(560px,94vw)" :close-on-click-modal="!modelBusy" :close-on-press-escape="!modelBusy" :show-close="!modelBusy" destroy-on-close @closed="modelForm.apiKey = ''">
      <el-form label-width="100px" :disabled="modelBusy" @submit.prevent="saveModel">
        <el-form-item label="模型用途" required><el-select v-model="modelForm.type" :disabled="!!editingModel" aria-label="模型用途"><el-option v-for="block in agentModelBlocks" :key="block.modelType" :label="block.title" :value="block.modelType" /></el-select></el-form-item>
        <el-form-item label="模型名称" required><el-input v-model="modelForm.model" maxlength="255" aria-label="模型名称" /></el-form-item>
        <el-form-item label="Base URL" required><el-input v-model="modelForm.baseUrl" maxlength="500" aria-label="模型 Base URL" placeholder="https://服务地址/v1" /></el-form-item>
        <el-form-item label="API Key" :required="!editingModel"><el-input v-model="modelForm.apiKey" type="password" show-password autocomplete="new-password" maxlength="512" aria-label="模型 API Key" :placeholder="editingModel ? '留空保留已有密钥' : '填写模型服务密钥'" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="modelForm.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="modelBusy" @click="modelDialog = false">取消</el-button><el-button type="primary" :loading="modelBusy" @click="saveModel">保存模型</el-button></template>
    </el-dialog>
    <el-dialog v-model="sandboxDialogVisible" :title="editingSandbox ? '编辑沙箱' : '新增沙箱'" width="min(560px, 94vw)" :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting" destroy-on-close @closed="clearSandboxForm">
      <el-form label-width="80px" @submit.prevent="saveSandbox">
        <el-form-item label="名称"><el-input v-model="sandboxForm.name" maxlength="100" show-word-limit placeholder="可选，不填则显示 URL" :disabled="submitting" /></el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="sandboxForm.url" placeholder="http://沙箱地址:端口，可包含服务路径" :disabled="submitting" />
        </el-form-item>
        <el-form-item label="Token">
          <el-input v-model="sandboxForm.token" type="password" show-password autocomplete="new-password" :disabled="submitting" :placeholder="editingSandbox ? '留空保留原 Token' : '填写沙箱访问 Token'" />
        </el-form-item>
        <el-divider content-position="left">数据库连接（MySQL）</el-divider>
        <el-form-item label="地址" required><el-input v-model="sandboxForm.host" placeholder="沙箱能够访问的数据库地址" :disabled="submitting" /></el-form-item>
        <el-form-item label="端口" required><el-input-number v-model="sandboxForm.port" :min="1" :max="65535" :precision="0" :disabled="submitting" /></el-form-item>
        <el-form-item label="账号" required><el-input v-model="sandboxForm.username" autocomplete="off" :disabled="submitting" /></el-form-item>
        <el-form-item label="密码" required><el-input v-model="sandboxForm.password" type="password" show-password autocomplete="new-password" :placeholder="sandboxHasPassword ? '留空保留原数据库密码' : '填写数据库密码'" :disabled="submitting" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="sandboxDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveSandbox">保存沙箱</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, ElTable } from 'element-plus'
import { Hide, View } from '@element-plus/icons-vue'
import {
  createSystemConfig,
  deleteSystemConfig,
  querySystemConfigs,
  revealSystemConfig,
  updateSystemConfig,
  queryModelConfigs, createModelConfig, updateModelConfig, deleteModelConfig, batchDeleteModelConfigs,
  type ModelConfigItem,
  type SystemConfig,
  type SystemConfigSecretPath,
  type SystemConfigSaveParams,
  type SystemConfigType
} from '@/api/system'

type ConfigSection = 'database' | 'base-model' | 'ai-model' | 'vector' | 'sandbox'
type BaseModelKey = 'llm' | 'embedding' | 'rerank'
type AgentModelKey = 'intent' | 'task' | 'execute' | 'summary'
type JsonObject = Record<string, any>
type EnabledBySection = Record<ConfigSection, 0 | 1>

interface ModelEndpointForm {
  model: string
  apiKey: string
  baseUrl: string
}

interface AgentModelBlock {
  key: AgentModelKey
  title: string
  description: string
  modelType: 1 | 2 | 3 | 4
}

const activeSection = ref<ConfigSection>('sandbox')
const organizationName = (() => {
  try {
    return JSON.parse(localStorage.getItem('currentOrganization') || '{}').name || '未选择'
  } catch {
    return '未选择'
  }
})()

const baseModelBlocks: Array<{
  key: BaseModelKey
  title: string
  description: string
  required: boolean
}> = [
  { key: 'llm', title: '对话模型', description: '平台默认对话与通用生成能力', required: false },
  { key: 'embedding', title: 'Embedding 模型', description: '知识内容向量化', required: true },
  { key: 'rerank', title: 'Rerank 模型', description: '召回结果重排', required: true }
]

const agentModelBlocks: AgentModelBlock[] = [
  { key: 'intent', title: '意图模型', description: '识别用户意图', modelType: 1 },
  { key: 'task', title: '任务分解模型', description: '拆分并规划执行任务', modelType: 2 },
  { key: 'execute', title: '执行模型（代码）', description: '负责代码与工具执行', modelType: 3 },
  { key: 'summary', title: '总结模型', description: '整理并生成最终结果', modelType: 4 }
]

const primarySectionSettings: Record<Exclude<ConfigSection, 'ai-model'>, {
  configType: SystemConfigType
  configName: string
}> = {
  database: { configType: 1, configName: '平台业务数据库' },
  'base-model': { configType: 2, configName: '运行时AI模型' },
  vector: { configType: 3, configName: '知识库向量库' },
  sandbox: { configType: 4, configName: '默认沙箱' }
}

const emptyModel = (): ModelEndpointForm => ({ model: '', apiKey: '', baseUrl: '' })
const emptyForm = () => ({
  database: {
    dbType: 'mysql',
    host: '',
    port: 3306,
    username: '',
    password: '',
    database: '',
    minSize: 1,
    maxSize: 10
  },
  baseModels: {
    llm: emptyModel(),
    embedding: emptyModel(),
    rerank: emptyModel()
  } as Record<BaseModelKey, ModelEndpointForm>,
  vector: {
    host: '',
    port: 19530,
    dbName: '',
    collectionName: '',
    vectorDim: 1536,
    indexType: 'IVF_FLAT',
    nlist: 128
  }
})

const form = reactive(emptyForm())
const sectionEnabled = reactive<EnabledBySection>({
  database: 1,
  'base-model': 1,
  'ai-model': 1,
  vector: 1,
  sandbox: 1
})
const primaryRecords = ref<Partial<Record<Exclude<ConfigSection, 'ai-model'>, SystemConfig>>>({})
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const modelRows = ref<ModelConfigItem[]>([]), modelTotal = ref(0), modelPage = ref(1), modelKeyword = ref(''), modelType = ref<1 | 2 | 3 | 4>()
const modelLoading = ref(false), modelError = ref(''), modelBusy = ref(false), modelDialog = ref(false), editingModel = ref<ModelConfigItem>()
const modelTable = ref<InstanceType<typeof ElTable>>()
const selectedModels = ref<ModelConfigItem[]>([])
const modelForm = reactive<{model:string;apiKey:string;baseUrl:string;type:1|2|3|4;enabled:0|1}>({model:'',apiKey:'',baseUrl:'',type:1,enabled:1})
let modelVersion = 0
const modelTypeLabel = (type: number) => agentModelBlocks.find(block => block.modelType === type)?.title || '未知用途'
const loadModels = async () => {
  const attempt = ++modelVersion; modelLoading.value = true; modelError.value = ''
  modelTable.value?.clearSelection()
  selectedModels.value = []
  try {
    const response = await queryModelConfigs({model:modelKeyword.value.trim() || undefined,type:modelType.value || undefined,pageNo:modelPage.value,pageSize:10})
    if(attempt!==modelVersion)return
    if(!response.success)throw new Error(response.message || '模型加载失败')
    modelRows.value=response.data.list;modelTotal.value=response.data.total
    if(!modelRows.value.length && modelPage.value>1)modelPage.value=Math.max(1,Math.ceil(modelTotal.value/10))
  }catch(cause){if(attempt===modelVersion){modelError.value=cause instanceof Error?cause.message:'模型加载失败';modelRows.value=[];modelTotal.value=0}}
  finally{if(attempt===modelVersion)modelLoading.value=false}
}
const searchModels = () => { if(modelPage.value!==1)modelPage.value=1;else void loadModels() }
const openModelDialog = (row?: ModelConfigItem) => {
  editingModel.value=row;Object.assign(modelForm,{model:row?.model||'',apiKey:'',baseUrl:row?.baseUrl||'',type:row?.type||modelType.value||1,enabled:row?.enabled??1});modelDialog.value=true
}
const saveModel = async () => {
  if(modelBusy.value)return
  if(!modelForm.model.trim() || !modelForm.baseUrl.trim() || (!editingModel.value && !modelForm.apiKey.trim())) { ElMessage.warning('请填写模型名称、Base URL 和 API Key');return }
  try{const url=new URL(modelForm.baseUrl.trim());if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw new Error()}catch{ElMessage.warning('请填写有效的 HTTP(S) Base URL');return}
  modelBusy.value=true
  try{
    const response=editingModel.value?await updateModelConfig({id:editingModel.value.id,model:modelForm.model.trim(),baseUrl:modelForm.baseUrl.trim(),enabled:modelForm.enabled,...(modelForm.apiKey.trim()?{apiKey:modelForm.apiKey.trim()}: {})}):await createModelConfig({...modelForm,model:modelForm.model.trim(),baseUrl:modelForm.baseUrl.trim(),apiKey:modelForm.apiKey.trim()})
    if(!response.success)throw new Error(response.message||'模型保存失败')
    modelForm.apiKey='';modelDialog.value=false;ElMessage.success('模型已保存')
    if(editingModel.value){await loadModels()}
    else{
      modelKeyword.value='';modelType.value=modelForm.type
      if(modelPage.value!==1)modelPage.value=1;else await loadModels()
    }
  }catch(cause){ElMessage.error(cause instanceof Error?cause.message:'模型保存失败')}finally{modelBusy.value=false}
}
const toggleModel = async (row: ModelConfigItem) => {
  if(modelBusy.value)return
  if(row.enabled){try{await ElMessageBox.confirm('停用后，使用此模型的智能体需要改选其他启用模型。是否继续？','停用模型',{type:'warning',confirmButtonText:'停用',cancelButtonText:'取消'})}catch{return}}
  modelBusy.value=true
  try{const response=await updateModelConfig({id:row.id,enabled:row.enabled?0:1});if(!response.success)throw new Error(response.message||'模型状态更新失败');await loadModels()}catch(cause){ElMessage.error(cause instanceof Error?cause.message:'模型状态更新失败')}finally{modelBusy.value=false}
}
const removeModels = async (row?: ModelConfigItem) => {
  if (modelBusy.value || modelLoading.value || modelError.value) return
  const ids = row ? [row.id] : selectedModels.value.map(item => item.id)
  if (!ids.length) return
  modelBusy.value = true
  try {
    try {
      await ElMessageBox.confirm(
        row ? `确定删除模型“${row.model}”（${modelTypeLabel(row.type)}）？删除后无法恢复。` : `确定删除选中的 ${ids.length} 个模型？删除后无法恢复。`,
        row ? '删除模型' : '批量删除模型',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
      )
    } catch { return }
    const response = row ? await deleteModelConfig(row.id) : await batchDeleteModelConfigs(ids)
    if (!response.success) throw new Error(response.message || '模型删除失败')
    ElMessage.success(response.message || '模型已删除')
    await loadModels()
  } catch (cause) {
    await ElMessageBox.alert(cause instanceof Error ? cause.message : '模型删除失败，请重试', '无法删除模型', { type: 'warning', confirmButtonText: '知道了' }).catch(() => {})
  } finally { modelBusy.value = false }
}
watch(modelPage,()=>{void loadModels()},{flush:'sync'})
watch(activeSection,section=>{if(section==='ai-model')void loadModels()})
const sandboxRecords = ref<SystemConfig[]>([])
const sandboxKeyword = ref('')
const sandboxAppliedKeyword = ref('')
const sandboxPage = ref(1)
const sandboxPageSize = ref(10)
const filteredSandboxRecords = computed(() => sandboxRecords.value.filter(record =>
  `${record.configJson.name || ''} ${record.configJson.url || ''}`.toLowerCase().includes(sandboxAppliedKeyword.value)
))
const pagedSandboxRecords = computed(() => filteredSandboxRecords.value.slice((sandboxPage.value - 1) * sandboxPageSize.value, sandboxPage.value * sandboxPageSize.value))
const sandboxRowIndex = (index: number) => (sandboxPage.value - 1) * sandboxPageSize.value + index + 1
const searchSandboxes = () => { sandboxAppliedKeyword.value = sandboxKeyword.value.trim().toLowerCase(); sandboxPage.value = 1 }
const resetSandboxSearch = () => { sandboxKeyword.value = ''; searchSandboxes() }
watch(filteredSandboxRecords, records => { sandboxPage.value = Math.min(sandboxPage.value, Math.max(1, Math.ceil(records.length / sandboxPageSize.value))) })
const sandboxDialogVisible = ref(false)
const editingSandbox = ref<SystemConfig>()
const emptySandboxForm = () => ({ name: '', url: '', token: '', host: '', port: 3306, username: '', password: '' })
const sandboxForm = reactive(emptySandboxForm())
const sandboxHasPassword = computed(() => Boolean((editingSandbox.value?.configJson.database as JsonObject | undefined)?.password))
const sandboxBusyId = ref<number | null>(null)

const clearSandboxForm = () => {
  editingSandbox.value = undefined
  Object.assign(sandboxForm, emptySandboxForm())
}
const openSandboxDialog = (record?: SystemConfig) => {
  clearSandboxForm()
  editingSandbox.value = record
  sandboxForm.url = String(record?.configJson.url || '')
  sandboxForm.name = String(record?.configJson.name || '')
  const database = record?.configJson.database as JsonObject | undefined
  if (database) Object.assign(sandboxForm, { host: database.host || '', port: database.port || 3306, username: database.username || '' })
  sandboxDialogVisible.value = true
}
const saveSandbox = async () => {
  if (submitting.value) return
  try {
    const url = new URL(sandboxForm.url.trim())
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error()
  } catch {
    ElMessage.error('请填写有效的 HTTP(S) 沙箱 URL，Token 请在单独字段填写')
    return
  }
  if (!sandboxForm.host.trim() || !sandboxForm.username.trim() || (!sandboxForm.password && !sandboxHasPassword.value)) {
    ElMessage.error('请填写完整的数据库地址、账号和密码')
    return
  }
  submitting.value = true
  try {
    const record = editingSandbox.value
    await persistConfiguration(record, {
      configType: 4,
      configName: record?.configName || `沙箱-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      configJson: {
        name: sandboxForm.name.trim(),
        url: sandboxForm.url.trim(), token: sandboxForm.token || (record?.configJson.token ? MASKED_SECRET : ''),
        database: { host: sandboxForm.host.trim(), port: sandboxForm.port, username: sandboxForm.username.trim(), password: sandboxForm.password || (sandboxHasPassword.value ? MASKED_SECRET : '') }
      },
      enabled: record?.enabled ?? 1
    })
    sandboxDialogVisible.value = false
    ElMessage.success('沙箱已保存')
    await loadConfigurations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '沙箱保存失败')
  } finally {
    submitting.value = false
  }
}
const toggleSandbox = async (record: SystemConfig) => {
  if (record.enabled === 1) {
    try {
      await ElMessageBox.confirm('停用后，绑定此沙箱的项目组将暂时无法读取客户数据。是否继续？', '停用沙箱', { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' })
    } catch { return }
  }
  sandboxBusyId.value = record.id
  try {
    const response = await updateSystemConfig({ id: record.id, enabled: record.enabled === 1 ? 0 : 1 })
    if (!response.success) throw new Error(response.message || '状态更新失败')
    ElMessage.success(record.enabled === 1 ? '沙箱已停用' : '沙箱已启用')
    await loadConfigurations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '状态更新失败')
  } finally { sandboxBusyId.value = null }
}
const removeSandbox = async (record: SystemConfig) => {
  try {
    await ElMessageBox.confirm(`确定删除沙箱 ${record.configJson.url || '（未配置 URL）'}？已绑定项目组的沙箱无法删除。`, '删除沙箱', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  sandboxBusyId.value = record.id
  try {
    const response = await deleteSystemConfig(record.id)
    if (!response.success && response.data?.projectGroups?.length) {
      await ElMessageBox.alert(response.message || '沙箱已被项目组绑定，不能删除', '无法删除沙箱', { type: 'warning', confirmButtonText: '知道了' }).catch(() => {})
      return
    }
    if (!response.success) throw new Error(response.message || '沙箱删除失败')
    ElMessage.success('沙箱已删除')
    await loadConfigurations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '沙箱删除失败')
  } finally { sandboxBusyId.value = null }
}
const MASKED_SECRET = '******'
const visibleSecretFields = ref<Set<string>>(new Set())
const loadingSecretFields = ref<Set<string>>(new Set())

const setSecretFieldState = (target: typeof visibleSecretFields, fieldKey: string, enabled: boolean) => {
  const next = new Set(target.value)
  if (enabled) next.add(fieldKey)
  else next.delete(fieldKey)
  target.value = next
}

const isSecretVisible = (fieldKey: string) => visibleSecretFields.value.has(fieldKey)
const isSecretLoading = (fieldKey: string) => loadingSecretFields.value.has(fieldKey)

const currentSecretValue = (fieldKey: string) => {
  if (fieldKey === 'database.password') return form.database.password
  const [scope, modelKey] = fieldKey.split('.')
  if (scope === 'base') return form.baseModels[modelKey as BaseModelKey]?.apiKey || ''
  return ''
}

const secretPathForField = (fieldKey: string): SystemConfigSecretPath => {
  if (fieldKey === 'database.password') return 'mysql.password'
  const [scope, modelKey] = fieldKey.split('.')
  if (scope === 'base') return `${modelKey}.api_key` as SystemConfigSecretPath
  return 'api_key'
}

const applyRevealedSecret = (fieldKey: string, value: string) => {
  if (fieldKey === 'database.password') {
    form.database.password = value
    return
  }
  const [scope, modelKey] = fieldKey.split('.')
  if (scope === 'base') {
    form.baseModels[modelKey as BaseModelKey].apiKey = value
  }
}

const toggleSecretVisibility = async (fieldKey: string, record?: SystemConfig) => {
  if (isSecretLoading(fieldKey)) return
  if (isSecretVisible(fieldKey)) {
    setSecretFieldState(visibleSecretFields, fieldKey, false)
    return
  }
  if (currentSecretValue(fieldKey) !== MASKED_SECRET) {
    setSecretFieldState(visibleSecretFields, fieldKey, true)
    return
  }
  if (!record) {
    ElMessage.warning('当前配置记录不存在，无法读取真实值')
    return
  }

  setSecretFieldState(loadingSecretFields, fieldKey, true)
  try {
    const response = await revealSystemConfig(record.id, secretPathForField(fieldKey))
    if (!response.success) {
      ElMessage.warning(response.message || '真实配置读取失败')
      return
    }
    applyRevealedSecret(fieldKey, response.data.value)
    setSecretFieldState(visibleSecretFields, fieldKey, true)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '真实配置读取失败')
  } finally {
    setSecretFieldState(loadingSecretFields, fieldKey, false)
  }
}

const sectionTitle = computed(() => ({
  database: '数据库配置',
  'base-model': '基础模型配置',
  'ai-model': 'AI 模型配置',
  vector: '向量库配置',
  sandbox: '沙箱配置'
})[activeSection.value])

const sectionDescription = computed(() => ({
  database: '平台数据与客户业务数据分别管理。',
  'base-model': '统一维护对话、Embedding 和 Rerank 模型。',
  'ai-model': '统一维护智能体各用途使用的模型。',
  vector: '维护当前公司的知识库向量存储。',
  sandbox: '维护当前公司的沙箱运行参数。'
})[activeSection.value])

const currentEnabled = computed<0 | 1>({
  get: () => sectionEnabled[activeSection.value],
  set: value => { sectionEnabled[activeSection.value] = value }
})

const endpointFromJson = (value: unknown): ModelEndpointForm => {
  const item = (value && typeof value === 'object' ? value : {}) as JsonObject
  return {
    model: String(item.model || ''),
    apiKey: String(item.api_key || ''),
    baseUrl: String(item.base_url || '')
  }
}

const isBaseModelConfig = (row: SystemConfig) => {
  const value = row.configJson || {}
  return ['llm', 'embedding', 'rerank'].some(key => key in value)
}

const selectPrimaryRecord = (
  rows: SystemConfig[],
  section: Exclude<ConfigSection, 'ai-model'>,
  predicate?: (row: SystemConfig) => boolean
) => {
  const settings = primarySectionSettings[section]
  const candidates = rows.filter(row => row.configType === settings.configType && (!predicate || predicate(row)))
  return candidates.find(row => row.configName === settings.configName) || candidates[0]
}

const resetLoadedState = () => {
  sandboxRecords.value = []
  Object.assign(form, emptyForm())
  Object.assign(sectionEnabled, {
    database: 1,
    'base-model': 1,
    'ai-model': 1,
    vector: 1,
    sandbox: 1
  })
  primaryRecords.value = {}
  visibleSecretFields.value = new Set()
  loadingSecretFields.value = new Set()
}

const hydrateDatabase = (record?: SystemConfig) => {
  if (!record) return
  const value = record.configJson as JsonObject
  const mysql = (value.mysql || {}) as JsonObject
  Object.assign(form.database, {
    dbType: String(value.db_type || 'mysql'),
    host: String(mysql.host || ''),
    port: Number(mysql.port || 3306),
    username: String(mysql.user || ''),
    password: String(mysql.password || ''),
    database: String(mysql.db || ''),
    minSize: Number(mysql.minsize || 1),
    maxSize: Number(mysql.maxsize || 10)
  })
}

const hydrateBaseModels = (record?: SystemConfig) => {
  if (!record) return
  const value = record.configJson as JsonObject
  for (const block of baseModelBlocks) {
    Object.assign(form.baseModels[block.key], endpointFromJson(value[block.key]))
  }
}


const hydrateVector = (record?: SystemConfig) => {
  if (!record) return
  const value = record.configJson as JsonObject
  Object.assign(form.vector, {
    host: String(value.host || ''),
    port: Number(value.port || 19530),
    dbName: String(value.db_name || ''),
    collectionName: String(value.collection_name || ''),
    vectorDim: Number(value.vector_dim || 1536),
    indexType: String(value.index_type || 'IVF_FLAT'),
    nlist: Number((value.index_params as JsonObject | undefined)?.nlist || 128)
  })
}

const hydrateConfigurations = (rows: SystemConfig[]) => {
  resetLoadedState()
  sandboxRecords.value = rows.filter(row => row.configType === 4)
  const databaseRecord = selectPrimaryRecord(rows, 'database')
  const baseModelRecord = selectPrimaryRecord(rows, 'base-model', isBaseModelConfig)
  const vectorRecord = selectPrimaryRecord(rows, 'vector')
  const sandboxRecord = selectPrimaryRecord(rows, 'sandbox')

  primaryRecords.value = {
    database: databaseRecord,
    'base-model': baseModelRecord,
    vector: vectorRecord,
    sandbox: sandboxRecord
  }

  for (const section of ['database', 'base-model', 'vector', 'sandbox'] as const) {
    const record = primaryRecords.value[section]
    if (record) sectionEnabled[section] = record.enabled
  }

  hydrateDatabase(databaseRecord)
  hydrateBaseModels(baseModelRecord)
  hydrateVector(vectorRecord)
}

const loadConfigurations = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const rows: SystemConfig[] = []
    let pageNo = 1
    while (true) {
      const response = await querySystemConfigs({ pageNo, pageSize: 100 })
      if (!response.success) throw new Error(response.message || '系统配置加载失败')
      rows.push(...response.data.list)
      if (rows.length >= response.data.total || response.data.list.length === 0) break
      pageNo += 1
    }
    hydrateConfigurations(rows)
  } catch (error) {
    resetLoadedState()
    errorMessage.value = error instanceof Error ? error.message : '系统配置加载失败'
  } finally {
    loading.value = false
  }
}

const endpointJson = (value: ModelEndpointForm) => ({
  model: value.model.trim(),
  api_key: value.apiKey.trim(),
  base_url: value.baseUrl.trim()
})

const buildDatabaseJson = () => ({
  db_type: form.database.dbType,
  mysql: {
    host: form.database.host.trim(),
    port: form.database.port,
    user: form.database.username.trim(),
    password: form.database.password,
    db: form.database.database.trim(),
    minsize: form.database.minSize,
    maxsize: form.database.maxSize
  }
})

const buildBaseModelsJson = () => {
  const result: Record<string, unknown> = {}
  for (const block of baseModelBlocks) {
    const value = form.baseModels[block.key]
    if (block.required || value.model || value.apiKey || value.baseUrl) {
      result[block.key] = endpointJson(value)
    }
  }
  return result
}

const buildVectorJson = () => ({
  host: form.vector.host.trim(),
  port: form.vector.port,
  db_name: form.vector.dbName.trim(),
  collection_name: form.vector.collectionName.trim(),
  vector_dim: form.vector.vectorDim,
  index_type: form.vector.indexType.trim(),
  index_params: { nlist: form.vector.nlist }
})

const requireText = (value: string, label: string) => {
  if (value.trim()) return true
  ElMessage.error(`请填写${label}`)
  return false
}

const validateEndpoint = (value: ModelEndpointForm, label: string, required: boolean) => {
  const touched = Boolean(value.model || value.apiKey || value.baseUrl)
  if (!required && !touched) return true
  if (
    !requireText(value.model, `${label}的模型名称`) ||
    !requireText(value.apiKey, `${label}的API Key`) ||
    !requireText(value.baseUrl, `${label}的Base URL`)
  ) return false
  if (!/^https?:\/\//.test(value.baseUrl.trim())) {
    ElMessage.error(`${label}的Base URL必须以http://或https://开头`)
    return false
  }
  return true
}

const validateCurrentSection = () => {
  if (activeSection.value === 'database') {
    if (
      !requireText(form.database.host, '主机地址') ||
      !requireText(form.database.username, '用户名') ||
      !requireText(form.database.database, '数据库名')
    ) return false
    if (form.database.maxSize < form.database.minSize) {
      ElMessage.error('最大连接数不能小于最小连接数')
      return false
    }
  }
  if (activeSection.value === 'base-model') {
    return baseModelBlocks.every(block =>
      validateEndpoint(form.baseModels[block.key], block.title, block.required)
    )
  }
  if (activeSection.value === 'vector') {
    return requireText(form.vector.host, '主机地址') &&
      requireText(form.vector.dbName, '数据库名') &&
      requireText(form.vector.collectionName, '集合名称')
  }
  return true
}

const persistConfiguration = async (
  record: SystemConfig | undefined,
  payload: Omit<SystemConfigSaveParams, 'id'>
) => {
  const response = record
    ? await updateSystemConfig({ id: record.id, ...payload })
    : await createSystemConfig(payload)
  if (!response.success) throw new Error(response.message || '系统配置保存失败')
}


const savePrimarySection = async (section: Exclude<ConfigSection, 'ai-model'>) => {
  const record = primaryRecords.value[section]
  const settings = primarySectionSettings[section]
  let configJson: Record<string, unknown>
  if (section === 'database') configJson = buildDatabaseJson()
  else if (section === 'base-model') configJson = buildBaseModelsJson()
  else if (section === 'vector') configJson = buildVectorJson()
  else configJson = record?.configJson || {}

  await persistConfiguration(record, {
    configType: settings.configType,
    configName: record?.configName || settings.configName,
    configJson,
    enabled: sectionEnabled[section]
  })
}

const saveCurrentSection = async () => {
  if (activeSection.value === 'ai-model') return
  if (!validateCurrentSection()) return
  submitting.value = true
  try {
    await savePrimarySection(activeSection.value)
    ElMessage.success(`${sectionTitle.value}保存成功`)
    await loadConfigurations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '系统配置保存失败')
  } finally {
    submitting.value = false
  }
}

onMounted(loadConfigurations)
</script>

<style scoped lang="scss">
.config-page {
  box-sizing: border-box;
  height: 100%;
  min-height: 0;
  padding: 24px 24px 32px;
  overflow-y: auto;
  background: var(--bg-dark);
}

.config-card {
  min-height: 100%;
  border: none;
}

.page-header h1 {
  margin: 0;
  color: #303133;
  font-size: 22px;
}

.page-header p,
.section-heading p {
  margin: 6px 0 0;
  color: #909399;
  font-size: 14px;
}

.config-tabs {
  margin-bottom: 8px;
}

.error-alert {
  margin-bottom: 18px;
}

.config-content {
  min-height: 420px;
}

.inline-config-form {
  max-width: 1120px;
  padding: 8px 4px 0;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid #ebeef5;
}

.section-heading h2 {
  margin: 0;
  color: #303133;
  font-size: 18px;
}

.section-status {
  flex: 0 0 auto;
  margin-bottom: 0;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 24px;
}

.field-grid :deep(.el-input-number) {
  width: 100%;
}

.full-field {
  grid-column: 1 / -1;
}

.model-block {
  margin-bottom: 16px;
  padding: 18px 18px 2px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.model-block-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 14px;
}

.model-block-title h3 {
  margin: 0;
  color: #303133;
  font-size: 15px;
}

.model-block-title span {
  color: #909399;
  font-size: 12px;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid #ebeef5;
}

.sandbox-pagination {
  display: flex;
  margin-top: 20px;
  padding: 4px 0;
  overflow-x: auto;

  :deep(.el-pagination) {
    flex-shrink: 0;
    margin-left: auto;
  }
}

.config-actions .el-button {
  min-width: 112px;
}

@media (max-width: 900px) {
  .config-page {
    padding: 12px 12px 20px;
  }

  .section-heading {
    flex-direction: column;
    gap: 14px;
  }

  .field-grid {
    grid-template-columns: 1fr;
  }

  .full-field {
    grid-column: auto;
  }

  .model-block-title {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
}
</style>
