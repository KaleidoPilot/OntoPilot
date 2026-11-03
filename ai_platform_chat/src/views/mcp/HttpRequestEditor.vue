<template>
  <div class="http-editor">
    <el-form-item label="请求方式"><el-select v-model="method" aria-label="请求方式"><el-option label="GET" value="GET" /><el-option label="POST" value="POST" /></el-select></el-form-item>
    <el-form-item label="接口用途"><el-input v-model="description" type="textarea" :rows="2" maxlength="2000" placeholder="说明接口能完成什么任务，帮助技能组选择" /></el-form-item>
    <el-tabs v-model="tab">
      <el-tab-pane v-for="section in sections" :key="section.name" :label="section.label" :name="section.name" :disabled="section.name === 'body' && method === 'GET'">
        <el-table :data="section.rows" size="small" empty-text="暂无参数">
          <el-table-column label="启用" width="58"><template #default="{ row, $index }"><el-checkbox v-model="row.enabled" :aria-label="`${section.name === 'body' ? '启用 JSON 参数' : '启用参数'} ${$index + 1}`" /></template></el-table-column>
          <el-table-column label="参数名" min-width="130"><template #default="{ row, $index }"><el-input v-model="row.key" :readonly="section.name === 'body' && bodyArray" :aria-label="fieldLabel(section.name, '名', $index)" maxlength="200" placeholder="参数名" /></template></el-table-column>
          <el-table-column label="测试值" min-width="165"><template #default="{ row, $index }"><el-input v-model="row.value" :aria-label="fieldLabel(section.name, '测试值', $index)" maxlength="4000" /></template></el-table-column>
          <el-table-column label="是否必填" width="96"><template #default="{ row, $index }"><el-checkbox v-model="row.required" :aria-label="fieldLabel(section.name, '是否必填', $index)" /></template></el-table-column>
          <el-table-column label="类型" width="110"><template #default="{ row, $index }"><el-select v-model="row.type" :aria-label="fieldLabel(section.name, '类型', $index)"><el-option v-for="(label, value) in types" :key="value" :value="value" :label="label" /></el-select></template></el-table-column>
          <el-table-column label="备注" min-width="200"><template #default="{ row, $index }"><el-input v-model="row.description" :aria-label="fieldLabel(section.name, '备注', $index)" maxlength="450" placeholder="说明参数含义、如何填写" /></template></el-table-column>
          <el-table-column width="64"><template #default="{ $index }"><el-button link type="danger" :aria-label="`${section.name === 'body' ? '删除 JSON 参数' : '删除参数'} ${$index + 1}`" @click="section.rows.splice($index, 1)">删除</el-button></template></el-table-column>
        </el-table>
        <el-button class="add-param" :disabled="section.rows.length >= 60" @click="section.rows.push(newRow(section.name === 'body' && bodyArray ? String(section.rows.length) : ''))">{{ section.name === 'body' ? '添加 JSON 参数' : '添加参数' }}</el-button>
      </el-tab-pane>
    </el-tabs>
    <el-text v-if="method === 'POST'" type="warning">POST 调用会先展示动态参数，确认后执行。</el-text>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { HttpRequestConfig } from '@/api/mcp'
type Variable = HttpRequestConfig['variables'][number]
type Row = { key: string; value: string; enabled: boolean; required: boolean; type: Variable['type']; description: string; variableName?: string }
const props = defineProps<{ initial?: HttpRequestConfig | null }>()
const method = ref<'GET' | 'POST'>(props.initial?.method || 'GET')
const description = ref(props.initial?.description || ''), tab = ref('params')
const types = { string: '文本', integer: '整数', number: '数字', boolean: '布尔值', array: '数组', object: '对象', null: '空值' }
const savedVariables = new Map([...(props.initial?.variables || []), ...(props.initial?.inactiveVariables || [])].map(item => [item.name, item]))
const bodyArray = Array.isArray(props.initial?.body)
const displayValue = (value: unknown): string => typeof value === 'string' ? value : JSON.stringify(value)
const inferType = (value: unknown): Variable['type'] => value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value === 'object' ? 'object' : typeof value === 'boolean' ? 'boolean' : typeof value === 'number' ? (Number.isInteger(value) ? 'integer' : 'number') : 'string'
const newRow = (key = ''): Row => ({ key, value: '', enabled: true, required: true, type: 'string', description: '' })
function restoreRow(key: string, value: unknown, type?: Variable['type'], note = '', enabled = true, required?: boolean): Row {
  const variableName = typeof value === 'string' ? value.match(/^\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}$/)?.[1] : undefined
  const variable = variableName ? savedVariables.get(variableName) : undefined
  const variableNote = variable?.description?.startsWith(key + ': ') ? variable.description.slice(key.length + 2) : variable?.description || ''
  const testValue = variableName && Object.hasOwn(props.initial?.testValues || {}, variableName)
    ? props.initial!.testValues![variableName] : variable?.example
  return { key, value: variable ? (testValue === undefined || testValue === null && variable.type !== 'null' ? '' : displayValue(testValue)) : displayValue(value), enabled, required: variable?.required ?? required ?? true, type: variable?.type || type || inferType(value), description: note || variableNote, variableName }
}
const params = ref<Row[]>((props.initial?.params || []).map(item => restoreRow(item.key, item.value, item.type, item.description, item.enabled, item.required)))
const savedBody = new Map(Object.entries(props.initial?.body || {}))
const bodyRows = ref<Row[]>(props.initial?.bodyFields?.length
  ? props.initial.bodyFields.map(item => ({ ...restoreRow(item.key, savedBody.has(item.key) ? savedBody.get(item.key) : item.value, item.type, item.description, item.enabled, item.required), value: item.value }))
  : Object.entries(props.initial?.body || {}).map(([key, value]) => restoreRow(key, value, undefined, props.initial?.bodyNotes?.[JSON.stringify(bodyArray ? [Number(key)] : [key])])))
const sections = computed(() => [{ name: 'params', label: 'Params', rows: params.value }, { name: 'body', label: 'Body · JSON', rows: bodyRows.value }])
const fieldLabel = (section: string, field: string, index: number) => `${section === 'body' ? 'JSON ' : ''}参数${field} ${index + 1}`
watch(method, value => { if (value === 'GET' && tab.value === 'body') tab.value = 'params' })
function testValue(row: Row): unknown {
  if (row.type === 'string') return row.value
  try {
    const value = JSON.parse(row.value)
    const valid = row.type === 'null' ? value === null : row.type === 'array' ? Array.isArray(value) : row.type === 'object' ? value !== null && typeof value === 'object' && !Array.isArray(value) : row.type === 'integer' ? Number.isInteger(value) : typeof value === row.type
    if (valid) return value
  } catch { /* 使用字段校验消息。 */ }
  throw new Error(`${row.key} 的测试值必须符合所选类型`)
}
function getRequest(): HttpRequestConfig {
  const validateRows = (rows: Row[]) => {
    if (rows.some(row => !row.key.trim() && (row.value !== '' || row.description.trim()))) throw new Error('请填写参数名')
    return rows.filter(row => row.key.trim()).map(row => ({ ...row, key: row.key.trim() }))
  }
  const queryRows = validateRows(params.value), jsonRows = method.value === 'POST' ? validateRows(bodyRows.value) : []
  if (new Set(jsonRows.map(row => row.key)).size !== jsonRows.length) throw new Error('JSON 参数名不能重复')
  const definitions = new Map<string, Variable>()
  const reserved = new Set(savedVariables.keys())
  const bodyNotes: Record<string, string> = {}
  const testValues: Record<string, unknown> = {}
  function valueFor(row: Row, prefix: string, index: number): unknown {
    let name = row.variableName
    if (!name) {
      name = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(row.key) && !reserved.has(row.key) ? row.key : undefined
      if (!name) { let suffix = index + 1; do { name = `${prefix}_${suffix++}` } while (reserved.has(name)) }
      reserved.add(name)
    }
    const definition: Variable = { name, type: row.type, description: `${row.key}: ${row.description.trim() || '根据用户问题填写'}`.slice(0, 500), required: row.required }
    if (definitions.has(name) && definitions.get(name)!.type !== definition.type) throw new Error('同名 AI 参数的类型不一致')
    if (definitions.has(name) && definitions.get(name)!.required !== definition.required) throw new Error('同名 AI 参数的必填设置不一致')
    definitions.set(name, definition)
    if (row.value !== '') Object.defineProperty(testValues, name, { value: testValue(row), enumerable: true, configurable: true })
    return `{{${name}}}`
  }
  const query = queryRows.map((row, index) => {
    const value = valueFor(row, 'param', index)
    return { key: row.key, value: typeof value === 'string' ? value : JSON.stringify(value), enabled: row.enabled, type: row.type, description: row.description.trim(), required: row.required }
  })
  const body: Record<string, unknown> | unknown[] | null = jsonRows.some(row => row.enabled) ? (bodyArray ? [] : {}) : null
  jsonRows.forEach((row, index) => {
    if (!row.enabled || body === null) return
    const value = valueFor(row, 'body', index)
    if (Array.isArray(body)) body.push(value)
    else Object.defineProperty(body, row.key, { value, enumerable: true, writable: true, configurable: true })
    if (row.description.trim()) bodyNotes[JSON.stringify(bodyArray ? [Array.isArray(body) ? body.length - 1 : index] : [row.key])] = row.description.trim()
  })
  const scanNames = (value: unknown): string[] => typeof value === 'string' ? [...value.matchAll(/\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}/g)].map(match => match[1]) : value && typeof value === 'object' ? Object.values(value).flatMap(scanNames) : []
  const activeNames = new Set([...query.filter(item => item.enabled).flatMap(item => scanNames(item.value)), ...scanNames(body)])
  const disabledNames = new Set(query.filter(item => !item.enabled).flatMap(item => scanNames(item.value)))
  // 保留已有嵌入式模板的执行定义，新参数无需用户编写模板。
  for (const name of [...activeNames, ...disabledNames]) if (!definitions.has(name) && savedVariables.has(name)) definitions.set(name, { ...savedVariables.get(name)! })
  if ([...activeNames].some(name => !definitions.has(name))) throw new Error('参数定义无效，请重新编辑参数')
  const active = [...definitions.values()].filter(item => activeNames.has(item.name))
  const inactive = [...definitions.values()].filter(item => !activeNames.has(item.name) && disabledNames.has(item.name))
  if (active.length + inactive.length > 30) throw new Error('AI 填写参数最多 30 个')
  return { method: method.value, description: description.value.trim(), params: query, body, variables: active, inactiveVariables: inactive, bodyNotes, testValues,
    bodyFields: jsonRows.map(row => ({ key: row.key, value: row.value, enabled: row.enabled, type: row.type, description: row.description.trim(), required: row.required })) }
}
defineExpose({ getRequest })
</script>

<style scoped lang="scss">
.http-editor { min-width: 0; }.add-param { margin-top: 12px; }.el-select { width: 100%; }
</style>
