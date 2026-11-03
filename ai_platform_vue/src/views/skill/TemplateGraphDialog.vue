<template>
  <el-dialog :model-value="modelValue" :title="`${name} · 知识图谱`" width="min(1120px,96vw)" append-to-body
    @update:model-value="emit('update:modelValue', $event)" @opened="draw">
    <el-alert title="这是模板原文的内容图谱；按模板生成新文档时，以本次上传的资料为依据。" type="info" :closable="false" />
    <div class="graph-tools">
      <el-button :loading="loading" :disabled="mutating" @click="load">刷新图谱</el-button>
      <span v-if="graph?.status === 'ready'">{{ graph.nodeCount }} 个节点 · {{ graph.edgeCount }} 条关系</span>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="graph-state">
      <el-empty v-if="graph?.status === 'not_created'" description="此模板还未建立知识图谱">
        <el-button type="primary" :loading="mutating" :disabled="loading" @click="build">建立图谱</el-button>
      </el-empty>
      <template v-else-if="graph && graph.status !== 'ready'">
        <el-alert :title="graph.task?.error?.message || graph.task?.progress || '图谱正在处理'" :type="canRetry ? 'error' : 'info'" :closable="false" />
        <el-button v-if="canRetry" type="primary" :loading="mutating" :disabled="loading" @click="retry">重试建图</el-button>
        <p v-else>任务已排队或正在处理，完成后自动展示。可以先关闭页面。</p>
      </template>
      <template v-else-if="graph">
        <el-alert v-if="graph.isTruncated" title="为保证浏览速度，当前展示部分节点和关系。" type="warning" :closable="false" />
        <el-empty v-if="!graph.nodes.length" description="图谱已处理完成，模板原文中未抽取到可展示的实体关系" />
        <el-tabs v-else v-model="tab" @tab-change="draw">
          <el-tab-pane label="关系图" name="chart">
            <div ref="canvas" class="graph-canvas" role="img" aria-label="模板知识图谱，可缩放、拖动和点击节点查看原文" />
          </el-tab-pane>
          <el-tab-pane label="节点和关系" name="rows">
            <el-table :data="[...graph.nodes, ...graph.edges]" max-height="440" @row-click="select">
              <el-table-column label="节点 / 关系" min-width="190"><template #default="{ row }">{{ row.source ? `${row.source} → ${row.target}` : row.label || row.id }}</template></el-table-column>
              <el-table-column prop="description" label="说明" min-width="220" />
              <el-table-column label="原文"><template #default="{ row }"><el-button link type="primary" @click.stop="select(row)">查看依据</el-button></template></el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
        <section v-if="selected" class="evidence-panel">
          <strong>{{ selected.label || (selected.source ? `${selected.source} → ${selected.target}` : selected.id) }}</strong>
          <p>{{ selected.description }}</p>
          <el-button v-for="(id, index) in selected.evidenceIds || []" :key="id" link type="primary" @click="proof(id)">原文 {{ index + 1 }}</el-button>
          <div v-loading="proofLoading">
            <el-alert v-if="proofError" :title="proofError" type="error" :closable="false" />
            <p v-if="evidence">来源：{{ evidence.fileName }}</p><pre v-if="evidence">{{ evidence.text }}</pre>
          </div>
        </section>
      </template>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { init, use, type ECharts } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { buildCompanyTemplateGraph, getCompanyTemplateGraph, getCompanyTemplateGraphEvidence,
  retryCompanyTemplateTask, type CompanyTemplateGraph, type CompanyTemplateGraphItem } from '@/api/skill'

use([GraphChart, TooltipComponent, SVGRenderer])
const props = defineProps<{ modelValue: boolean; skillId: string; name: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
const graph = ref<CompanyTemplateGraph>(), loading = ref(false), mutating = ref(false), error = ref('')
const tab = ref('chart'), canvas = ref<HTMLElement>(), selected = ref<CompanyTemplateGraphItem>()
const evidence = ref<{ text: string; fileName: string }>(), proofLoading = ref(false), proofError = ref('')
const canRetry = computed(() => ['failed', 'interrupted'].includes(graph.value?.status || ''))
let chart: ECharts | undefined, observer: ResizeObserver | undefined, timer: ReturnType<typeof setTimeout> | undefined
let version = 0, proofVersion = 0, disposed = false

function schedule() {
  clearTimeout(timer)
  if (props.modelValue && ['queued', 'running'].includes(graph.value?.status || '')) timer = setTimeout(() => void load(), 2500)
}
function clearSelection() {
  ++proofVersion; selected.value = undefined; evidence.value = undefined; proofError.value = ''; proofLoading.value = false
}
async function showGraph(value: CompanyTemplateGraph) {
  clearSelection(); graph.value = value
  if (value.status !== 'ready') disposeChart()
  await draw(); schedule()
}
async function load() {
  if (!props.modelValue || !props.skillId || disposed || mutating.value) return
  const requested = ++version; loading.value = true; error.value = ''; clearTimeout(timer)
  try {
    const res = await getCompanyTemplateGraph(props.skillId)
    if (requested !== version || disposed) return
    if (!res.success) throw new Error(res.message || '图谱加载失败')
    await showGraph(res.data)
  } catch (cause) {
    if (requested === version && !disposed) error.value = cause instanceof Error ? cause.message : '图谱加载失败，请刷新重试'
  } finally { if (requested === version) loading.value = false }
}
async function build() {
  if (mutating.value || loading.value || !props.modelValue || !props.skillId) return
  const requested = ++version; mutating.value = true; error.value = ''; clearTimeout(timer)
  try {
    const res = await buildCompanyTemplateGraph(props.skillId)
    if (requested !== version || disposed) return
    if (!res.success) throw new Error(res.message || '建图失败')
    await showGraph(res.data)
  } catch (cause) {
    if (requested === version && !disposed) error.value = cause instanceof Error ? cause.message : '建图失败，请重试'
  } finally { if (requested === version) mutating.value = false }
}
async function retry() {
  if (!graph.value?.task || mutating.value || loading.value || !props.modelValue) return
  const requested = ++version; mutating.value = true; error.value = ''; clearTimeout(timer)
  try {
    const task = graph.value.task
    const res = await retryCompanyTemplateTask(task.taskId, task.attempt)
    if (requested !== version || disposed) return
    if (!res.success) throw new Error(res.message || '重试失败')
    const refreshed = await getCompanyTemplateGraph(props.skillId)
    if (requested !== version || disposed) return
    if (!refreshed.success) throw new Error(refreshed.message || '图谱加载失败')
    await showGraph(refreshed.data)
  } catch (cause) {
    if (requested === version && !disposed) error.value = cause instanceof Error ? cause.message : '重试失败，请刷新重试'
  } finally { if (requested === version) mutating.value = false }
}
async function draw() {
  const requested = version
  await nextTick()
  if (requested !== version || disposed || !props.modelValue || graph.value?.status !== 'ready' || !canvas.value || tab.value !== 'chart') return
  if (!chart) {
    chart = init(canvas.value, undefined, { renderer: 'svg' })
    chart.on('click', event => { const data = event.data as { record?: CompanyTemplateGraphItem } | undefined; if (data?.record) select(data.record) })
    observer = new ResizeObserver(() => chart?.resize()); observer.observe(canvas.value)
  }
  chart.setOption({ animation: false, tooltip: { renderMode: 'richText' }, series: [{ type: 'graph', layout: 'force', roam: true,
    draggable: true, symbolSize: 26, label: { show: true, fontSize: 11 }, edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 6,
    lineStyle: { color: '#9caec9', curveness: .12 }, force: { repulsion: 180, edgeLength: 100, layoutAnimation: false },
    data: graph.value.nodes.map(row => ({ id: row.id, name: row.label || row.id, record: row })),
    links: graph.value.edges.map(row => ({ source: row.source, target: row.target, record: row })) }] }, true)
  chart.resize()
}
function select(row: CompanyTemplateGraphItem) {
  clearSelection(); selected.value = row
  if (row.evidenceIds?.length) void proof(row.evidenceIds[0])
}
async function proof(id: string) {
  if (!graph.value?.task || !props.modelValue) return
  const requested = ++proofVersion; proofLoading.value = true; proofError.value = ''; evidence.value = undefined
  try {
    const res = await getCompanyTemplateGraphEvidence(graph.value.task.taskId, id)
    if (requested !== proofVersion || disposed) return
    if (!res.success) throw new Error(res.message || '原文加载失败')
    evidence.value = res.data
  } catch (cause) {
    if (requested === proofVersion && !disposed) proofError.value = cause instanceof Error ? cause.message : '原文加载失败，请重试'
  } finally { if (requested === proofVersion) proofLoading.value = false }
}
function disposeChart() { observer?.disconnect(); observer = undefined; chart?.dispose(); chart = undefined }
function reset() {
  ++version; clearTimeout(timer); disposeChart(); clearSelection()
  graph.value = undefined; loading.value = false; mutating.value = false; error.value = ''; tab.value = 'chart'
}
watch(() => [props.modelValue, props.skillId], () => { reset(); if (props.modelValue) void load() }, { immediate: true })
onBeforeUnmount(() => { disposed = true; reset() })
</script>

<style scoped>
.graph-tools{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:16px 0}.graph-state{min-height:180px}
.graph-canvas{width:100%;height:440px}.evidence-panel{padding:16px;background:var(--el-fill-color-light);overflow-wrap:anywhere}
pre{white-space:pre-wrap;max-height:240px;overflow:auto;line-height:1.7}.el-alert{margin-bottom:12px}
@media(max-width:600px){.graph-canvas{height:320px}}
</style>
