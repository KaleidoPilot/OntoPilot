<template>
  <el-dialog :model-value="modelValue" :title="`${title} · 结构图谱`" width="min(1120px,96vw)" append-to-body
    @update:model-value="emit('update:modelValue', $event)" @opened="load" @closed="close">
    <el-alert title="中心是这份模板的名称，向外展开它由哪些主题组成。主题下面是呈现形式、分析、资料和要求，不是业务实体关系。" type="info" :closable="false" />
    <div class="legend" aria-hidden="true"><span v-for="item in legend" :key="item.kind"><i :style="{ background: item.color }" />{{ item.kind }}</span></div>
    <div class="graph-tools"><el-button :loading="loading" @click="load">刷新</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="graph-state">
      <el-empty v-if="!loading && !error && !tree" description="模板生成完成后，这里显示它的主题结构" />
      <div v-else-if="tree" class="structure-layout">
        <div ref="canvas" class="structure-canvas" role="img" aria-label="模板结构图谱，中心为模板名称，向外为主题及其组成" />
        <aside ref="panel">
          <h3>{{ selected?.kind || '文档' }}</h3>
          <p class="node-name">{{ selected?.fullName || title }}</p>
          <p v-if="selected?.detail" class="node-detail">{{ selected.detail }}</p>
          <p v-else class="node-detail">图上是简写。点击节点后，这里显示完整内容。</p>
          <el-tree :data="[tree]" node-key="id" default-expand-all :expand-on-click-node="false" @node-click="choose">
            <template #default="{ data }"><span class="tree-label">{{ data.kind }} · {{ data.kind === '数据来源' ? data.fullName : data.name }}</span></template>
          </el-tree>
        </aside>
      </div>
    </div>
  </el-dialog>
</template>
<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { init, use, type ECharts } from 'echarts/core'
import { TreeChart } from 'echarts/charts'
import { SVGRenderer } from 'echarts/renderers'
import { getCompanyTemplate, type CompanyWritingSkill } from '@/api/skill'
use([TreeChart, SVGRenderer])

interface StructureNode { id: string; name: string; fullName: string; kind: string; detail?: string; collapsed?: boolean; itemStyle?: { color: string; borderColor?: string; borderWidth?: number }; children?: StructureNode[] }
const props = defineProps<{ modelValue: boolean; skillId: string; name: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
const colors: Record<string, string> = { 文档: '#2f6fed', 主题: '#0f8a6a', 呈现形式: '#b26a00', 分析: '#6b4c9a', 资料: '#3d6b8a', 要求: '#a33b4a', 数据来源: '#3f6f4a', 需确认口径: '#8a5a2b', 前文结果: '#4e5d78' }
const legend = Object.entries(colors).map(([kind, color]) => ({ kind, color }))
const formatLabel: Record<string, string> = { prose: '正文', table: '表格', chart: '图表', list: '列表', flow: '流程', auto: '按内容选择' }
const loading = ref(false), error = ref(''), tree = ref<StructureNode>(), selected = ref<StructureNode>(), canvas = ref<HTMLElement>(), panel = ref<HTMLElement>()
const title = ref(props.name || '模板')
let chart: ECharts | undefined, version = 0, disposed = false
function clip(value: string) { return value.length > 8 ? value.slice(0, 8) + '…' : value }
function node(id: string, fullName: string, kind: string, detail?: string, children?: StructureNode[]): StructureNode {
  const text = fullName.replace(/\s+/g, ' ').trim()
  const extra = detail?.replace(/\s+/g, ' ').trim()
  return { id, name: kind === '数据来源' ? text : clip(text), fullName: text, kind, detail: extra && extra !== text ? extra : undefined, itemStyle: { color: colors[kind] || '#607080' }, children: children?.filter(item => item.fullName) }
}
function build(skill: CompanyWritingSkill): StructureNode {
  return node('document', skill.title || props.name || '模板', '文档', skill.purpose, skill.sections.map((section, index) => {
    const formats = section.formats?.length ? section.formats : section.format ? [section.format] : []
    const children = [
      ...formats.map((format, formatIndex) => node(`${section.id}-format-${formatIndex}`, formatLabel[format] || format, '呈现形式', section.intent || section.instruction)),
      ...(section.analysis || []).map((item, itemIndex) => node(`${section.id}-analysis-${itemIndex}`, item, '分析')),
      ...(section.dataNeeds || []).map((item, itemIndex) => node(`${section.id}-need-${itemIndex}`, item, '资料')),
      ...(section.requirements || []).map((item, itemIndex) => node(`${section.id}-rule-${itemIndex}`, item.instruction, '要求')),
      ...(section.dataSources || []).map((source, sourceIndex) => {
        const fields = (source.sources || []).map(field => [field.tableName, field.columnName].filter(Boolean).join('.')).filter(Boolean)
        return node(`${section.id}-source-${sourceIndex}`, fields.join('、') || source.dataNeed || '数据来源', '数据来源', [source.dataNeed, source.derivation].filter(Boolean).join('\n'))
      }),
      ...(section.dataInputs || []).map((input, inputIndex) => node(`${section.id}-input-${inputIndex}`, input.dataNeed, input.kind === 'section_result' ? '前文结果' : '需确认口径', input.reason))
    ]
    return node(section.id || `section-${index}`, section.heading, '主题', section.intent || section.instruction, children)
  }))
}
function viewOf(source: StructureNode, targetId?: string): StructureNode {
  const visit = (current: StructureNode): { node: StructureNode; hit: boolean } => {
    const children = (current.children || []).map(visit)
    const hit = current.id === targetId || children.some(child => child.hit)
    return { hit, node: { ...current, children: children.map(child => child.node), collapsed: !!targetId && !!current.children?.length && !hit, itemStyle: current.id === targetId ? { ...current.itemStyle, color: current.itemStyle?.color || '#607080', borderColor: '#172033', borderWidth: 3 } : current.itemStyle } }
  }
  return visit(source).node
}
function locate(id: string) {
  if (!chart) return
  const model = (chart as unknown as { getModel: () => { getSeriesByIndex: (index: number) => unknown } }).getModel()
  const seriesModel = model.getSeriesByIndex(0) as {
    id: string
    coordinateSystem?: { dataToPoint?: (point: number[]) => number[] }
    getData: () => { count: () => number; getRawDataItem: (index: number) => StructureNode | undefined; getItemLayout: (index: number) => { x?: number; y?: number } }
  }
  if (!seriesModel) return
  const data = seriesModel.getData()
  let dataIndex = -1
  for (let index = 0; index < data.count(); index++) if (data.getRawDataItem(index)?.id === id) { dataIndex = index; break }
  const layout = dataIndex >= 0 ? data.getItemLayout(dataIndex) : undefined
  const point = layout?.x != null && layout.y != null ? seriesModel.coordinateSystem?.dataToPoint?.([layout.x, layout.y]) : undefined
  if (!point) return
  chart.dispatchAction({ type: 'treeRoam', seriesId: seriesModel.id, dx: chart.getWidth() / 2 - point[0], dy: chart.getHeight() / 2 - point[1] })
  const view = (chart as unknown as { _chartsViews?: Array<{ type?: string; _updateViewCoordSys?: (model: unknown) => void }> })._chartsViews?.find(item => item.type === 'tree')
  view?._updateViewCoordSys?.(seriesModel)
  chart.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex })
}
function choose(value: StructureNode) {
  const scroller = panel.value
  const dialog = scroller?.closest('.el-dialog__body') as HTMLElement | null
  const panelTop = scroller?.scrollTop || 0
  const dialogTop = dialog?.scrollTop || 0
  selected.value = value
  locate(value.id)
  void nextTick(() => { if (scroller) scroller.scrollTop = panelTop; if (dialog) dialog.scrollTop = dialogTop })
}
async function draw() {
  await nextTick()
  if (!canvas.value || !tree.value || disposed || !props.modelValue) return
  if (!chart) chart = init(canvas.value, undefined, { renderer: 'svg' })
  chart.setOption({
    series: [{ type: 'tree', data: [viewOf(tree.value)], layout: 'orthogonal', orient: 'LR', roam: true, left: 16, right: 340, top: 24, bottom: 24, symbol: 'circle', symbolSize: 8, initialTreeDepth: 2, expandAndCollapse: true, edgeShape: 'polyline', animationDuration: 240, lineStyle: { color: '#c5ced6', width: 1.2 }, label: { position: 'right', rotate: 0, align: 'left', verticalAlign: 'middle', fontSize: 12, color: '#243140', distance: 8 }, leaves: { label: { position: 'right', rotate: 0, align: 'left' } }, emphasis: { focus: 'relative' } }]
  }, true)
  chart.off('click')
  chart.on('click', event => { const data = event.data as StructureNode | null | undefined; if (data?.kind) selected.value = data })
  chart.resize()
}
async function load() {
  if (!props.modelValue || !props.skillId || disposed) return
  const requested = ++version
  loading.value = true; error.value = ''
  try {
    const res = await getCompanyTemplate(props.skillId)
    if (!res.success) throw new Error(res.message || '结构加载失败')
    if (requested !== version || disposed || !props.modelValue) return
    if (!res.data.skill?.sections?.length) throw new Error('模板还没有可展示的主题结构')
    tree.value = build(res.data.skill)
    title.value = res.data.skill.title || props.name || '模板'
    selected.value = tree.value
    await draw()
  } catch (cause) {
    if (requested === version && !disposed) { tree.value = undefined; error.value = cause instanceof Error ? cause.message : '结构加载失败' }
  } finally { if (requested === version && !disposed) loading.value = false }
}
function close() { ++version; chart?.dispose(); chart = undefined; tree.value = undefined; selected.value = undefined; error.value = '' }
onBeforeUnmount(() => { disposed = true; chart?.dispose() })
</script>
<style scoped>
.legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 12px 0; color: var(--el-text-color-secondary); font-size: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 8px; height: 8px; border-radius: 50%; }
.graph-tools { margin-bottom: 12px; }
.graph-state { min-height: 180px; }
.structure-layout { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(260px, .8fr); gap: 16px; align-items: stretch; height: 520px; }
.structure-canvas { width: 100%; height: 520px; position: sticky; top: 0; }
aside { height: 520px; overflow: auto; padding-right: 4px; overscroll-behavior: contain; }
.tree-label { display: inline-block; white-space: normal; overflow-wrap: anywhere; line-height: 1.45; padding: 3px 0; }
aside :deep(.el-tree-node__content) { height: auto; align-items: flex-start; }
aside h3 { margin: 0 0 8px; font-size: 14px; }
.node-name { margin: 0 0 8px; font-weight: 600; overflow-wrap: anywhere; }
.node-detail { margin: 0 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; color: var(--el-text-color-secondary); }
@media (max-width: 800px) { .structure-layout { grid-template-columns: 1fr; } .structure-canvas { height: 360px; } aside { max-height: 320px; } }
</style>
