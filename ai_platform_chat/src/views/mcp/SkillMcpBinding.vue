<template>
  <el-form-item label="MCP 工具">
    <div class="binding-panel">
      <el-alert v-if="error" :title="error" :type="skillType === 3 && !ownerId ? 'info' : 'error'" show-icon :closable="false"><template #default><el-button link @click="load">重新加载</el-button></template></el-alert>
      <el-skeleton v-if="loading" :rows="2" animated />
      <template v-else>
        <p class="hint">{{ skillType === 3 ? '可选。选择所属用户有权使用的 MCP 和具体工具。' : '可选。公共和项目组技能使用公司公用 MCP；执行时仍校验当前用户权限。' }}</p>
        <el-button :disabled="!!error" aria-label="选择技能 MCP" @click="openPicker">选择 MCP（已选 {{ selectedIds.length }}/5）</el-button>
        <el-empty v-if="!options.length && !error" description="暂无可绑定的工具。请先配置 MCP、测试连接并选择工具。" :image-size="48" />
        <div v-for="binding in value" :key="binding.configId" class="binding-row">
          <strong>{{ options.find(item => item.id === binding.configId)?.name || '失效服务 #' + binding.configId }}</strong>
          <el-button link type="danger" @click="remove(binding.configId)">移除服务</el-button>
          <el-select v-model="binding.toolNames" multiple filterable placeholder="选择具体工具" :disabled="!options.some(item => item.id === binding.configId)" aria-label="技能绑定的具体工具">
            <el-option v-for="name in options.find(item => item.id === binding.configId)?.selectedTools || []" :key="name" :value="name" :label="toolLabel(binding.configId, name)" />
          </el-select>
        </div>
        <el-alert v-if="missingIds.length" title="部分旧绑定已失效，请移除或重新选择后保存；不会自动删除原绑定。" type="warning" :closable="false" />
        <el-dialog v-model="pickerOpen" title="选择 MCP" width="min(760px, 94vw)" append-to-body>
          <div class="picker-toolbar">
            <el-button v-if="!showCategories" @click="returnToCategories">返回分类</el-button>
            <el-input v-model="search" clearable placeholder="直接搜索 MCP 名称" aria-label="搜索技能 MCP" @input="page = 1" />
            <span class="selection-count">已选 {{ selectedIds.length }}/5</span>
          </div>
          <template v-if="showCategories">
            <el-table :data="pageCategories" row-key="id" empty-text="暂无分类或可绑定 MCP">
              <el-table-column prop="name" label="分类名称" min-width="140" />
              <el-table-column prop="total" label="可绑定 MCP" width="120" />
              <el-table-column label="操作" width="110"><template #default="{ row }"><el-button link type="primary" :aria-label="'进入 MCP 分类 ' + row.name" @click="enterCategory(row.id)">进入分类</el-button></template></el-table-column>
            </el-table>
          </template>
          <template v-else>
            <div class="selection-actions">
              <strong>{{ activeCategoryId === undefined ? '全部分类' : categoryLabel(activeCategoryId) }}</strong>
              <el-button link type="primary" :disabled="!pageOptions.length || allPageSelected" @click="togglePage(true)">全选本页</el-button>
              <el-button link :disabled="!somePageSelected" @click="togglePage(false)">取消本页</el-button>
            </div>
            <el-table :data="pageOptions" row-key="id" empty-text="暂无匹配的可绑定 MCP">
              <el-table-column label="选择" width="64"><template #default="{ row }"><el-checkbox :model-value="selectedIds.includes(row.id)" :disabled="!selectedIds.includes(row.id) && selectedIds.length >= 5" :aria-label="'选择 MCP ' + row.name" @change="toggleService(row.id, $event)" /></template></el-table-column>
              <el-table-column prop="name" label="MCP 名称" min-width="150" />
              <el-table-column label="分类" min-width="120"><template #default="{ row }">{{ categoryLabel(row.categoryId || 0) }}</template></el-table-column>
            </el-table>
          </template>
          <el-pagination v-model:current-page="page" :page-size="5" :total="showCategories ? categoryOptions.length : filteredOptions.length" layout="total, prev, pager, next" :pager-count="5" class="picker-pagination" />
          <template #footer><el-button type="primary" @click="pickerOpen = false">完成选择</el-button></template>
        </el-dialog>
      </template>
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { loadSkillMcpOptions, loadSavedSkillMcp, loadSkillMcpCategories, type McpCategory, type McpBinding, type SkillMcpOption } from '@/api/mcp'
const props = withDefaults(defineProps<{ open: boolean; skillId?: number; skillType: 1 | 2 | 3; ownerId?: number; personal?: boolean }>(), { personal: false })
const emit = defineEmits<{ ready: [value: boolean] }>()
const options = ref<SkillMcpOption[]>([]), value = ref<McpBinding[]>([]), selectedIds = ref<number[]>([]), loading = ref(false), error = ref('')
const search = ref('')
const categories = ref<McpCategory[]>([]), pickerOpen = ref(false), activeCategoryId = ref<number>(), page = ref(1)
let version = 0
const categoryOptions = computed(() => [...categories.value, ...(options.value.some(item => !item.categoryId) ? [{id: 0, name: '未分类'}] : [])].map(item => ({...item, total: options.value.filter(config => (config.categoryId || 0) === item.id).length})))
const showCategories = computed(() => activeCategoryId.value === undefined && !search.value.trim())
const pageCategories = computed(() => categoryOptions.value.slice((page.value - 1) * 5, page.value * 5))
const filteredOptions = computed(() => {
  const keyword = search.value.trim().toLocaleLowerCase()
  return options.value.filter(item => (activeCategoryId.value === undefined || (item.categoryId || 0) === activeCategoryId.value) && item.name.toLocaleLowerCase().includes(keyword))
})
const pageOptions = computed(() => filteredOptions.value.slice((page.value - 1) * 5, page.value * 5))
const somePageSelected = computed(() => pageOptions.value.some(item => selectedIds.value.includes(item.id)))
const allPageSelected = computed(() => pageOptions.value.length > 0 && pageOptions.value.every(item => selectedIds.value.includes(item.id)))
const missingIds = computed(() => selectedIds.value.filter(id => !options.value.some(item => item.id === id)))
async function load() {
  const attempt = ++version; emit('ready', false); error.value = ''; loading.value = true
  search.value = ''
  activeCategoryId.value = undefined; page.value = 1; pickerOpen.value = false
  if (!props.open) { loading.value = false; return }
  if (props.skillType === 3 && !props.ownerId) { error.value = '请先选择技能所属用户'; loading.value = false; return }
  try {
    const [available, saved, categoryResponse] = await Promise.all([loadSkillMcpOptions(props.skillType, props.ownerId, props.personal), props.skillId ? loadSavedSkillMcp(props.skillId, props.personal) : Promise.resolve(undefined), loadSkillMcpCategories(props.personal)])
    if (attempt !== version) return
    if (!available.success) throw new Error(available.message || 'MCP 工具加载失败')
    if (saved && !saved.success) throw new Error(saved.message || 'MCP 绑定加载失败')
    if (!categoryResponse.success) throw new Error(categoryResponse.message || 'MCP 分类加载失败')
    categories.value = categoryResponse.data
    options.value = available.data.filter(item => item.enabled && item.selectedTools.length)
    value.value = (saved?.data || []).map(({configId, toolNames}) => ({configId, toolNames: [...toolNames]}))
    selectedIds.value = value.value.map(item => item.configId)
    emit('ready', true)
  } catch (cause) { if (attempt === version) error.value = cause instanceof Error ? cause.message : 'MCP 绑定加载失败' }
  finally { if (attempt === version) loading.value = false }
}
function categoryLabel(id: number) { return id === 0 ? '未分类' : categories.value.find(item => item.id === id)?.name || '已失效分类' }
function openPicker() { returnToCategories(); pickerOpen.value = true }
function returnToCategories() { activeCategoryId.value = undefined; search.value = ''; page.value = 1 }
function enterCategory(id: number) { activeCategoryId.value = id; search.value = ''; page.value = 1 }
function toggleService(id: number, checked: unknown) {
  const ids = checked ? [...new Set([...selectedIds.value, id])] : selectedIds.value.filter(item => item !== id)
  if (ids.length > 5) { ElMessage.warning('每个技能最多绑定 5 个 MCP'); return }
  selectedIds.value = ids; selectServices(ids)
}
function togglePage(checked: boolean) {
  const matchedIds = pageOptions.value.map(item => item.id)
  const ids = checked
    ? [...new Set([...selectedIds.value, ...matchedIds])]
    : selectedIds.value.filter(id => !matchedIds.includes(id))
  if (ids.length > 5) { ElMessage.warning('每个技能最多绑定 5 个 MCP，请取消部分选择后重试'); return }
  selectedIds.value = ids
  selectServices(ids)
}
function selectServices(ids: number[]) {
  value.value = ids.map(configId => value.value.find(item => item.configId === configId) || {
    configId, toolNames: [...(options.value.find(item => item.id === configId)?.selectedTools || [])],
  })
}
function remove(id: number) { selectedIds.value = selectedIds.value.filter(value => value !== id); selectServices(selectedIds.value) }
function toolLabel(id: number, name: string) { const tool = options.value.find(item => item.id === id)?.tools.find(item => item.name === name); return name + (tool?.readOnly ? ' · 只读' : ' · 执行前确认') }
function getBindings(): McpBinding[] {
  if (loading.value || error.value) throw new Error(error.value || 'MCP 绑定正在加载')
  for (const binding of value.value) {
    const config = options.value.find(item => item.id === binding.configId)
    if (!config || !binding.toolNames.length || binding.toolNames.some(name => !config.selectedTools.includes(name))) throw new Error('请为每个 MCP 选择有效工具，或移除失效服务')
  }
  return value.value.map(({configId, toolNames}) => ({configId, toolNames: [...toolNames]}))
}
watch(() => [props.open, props.skillId, props.skillType, props.ownerId, props.personal], load, { immediate: true })
defineExpose({ getBindings })
</script>

<style scoped>
.binding-panel { width: 100%; }.binding-panel .el-select { width: 100%; }.hint { color: #687993; font-size: 13px; margin: 0 0 8px; }.binding-row { margin-top: 14px; }.binding-row strong { margin-right: 12px; }.binding-row>.el-select { margin-top: 6px; }
.selection-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; margin-bottom: 12px; }.selection-count { margin-left: auto; color: #687993; font-size: 13px; white-space: nowrap; }
.picker-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }.picker-toolbar .el-input { flex: 1; min-width: 140px; }.picker-pagination { margin-top: 16px; justify-content: flex-end; }
</style>

