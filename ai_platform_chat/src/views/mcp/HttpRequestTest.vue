<template>
  <el-dialog :model-value="modelValue" :title="`测试请求 · ${config?.name || ''}`" width="min(760px, 94vw)" :close-on-click-modal="!sending" :close-on-press-escape="!sending" :show-close="!sending" @update:model-value="emit('update:modelValue', $event)">
    <template v-if="config">
      <el-alert :title="`${config.httpRequest?.method || 'MCP'} · ${config.url}`" type="info" :closable="false" />
      <p v-if="config.httpRequest?.method === 'POST'">点击发送会实际执行 POST 请求，请先确认参数和接口用途。</p>
      <el-form label-position="top"><el-form-item v-if="config.httpRequest?.variables.length" label="测试参数（JSON）"><el-input v-model="argumentsText" type="textarea" :rows="5" :disabled="sending" aria-label="测试动态参数" /><div v-for="item in config.httpRequest.variables" :key="item.name" class="parameter-note"><code>{{ item.name }}</code>：{{ item.description }}</div></el-form-item></el-form>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <div v-if="result" class="response"><el-tag :type="result.isError ? 'danger' : 'success'">HTTP {{ result.statusCode }}</el-tag><span>{{ result.durationMs }} ms</span><h4>响应内容</h4><pre>{{ typeof result.data === 'string' ? result.data : JSON.stringify(result.data, null, 2) }}</pre></div>
    </template>
    <template #footer><el-button :disabled="sending" @click="emit('update:modelValue', false)">关闭</el-button><el-button type="primary" :loading="sending" @click="sendRequest">发送请求</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { HttpRequestConfig, HttpTestResult, McpTestResponse } from '@/api/mcp'
const props = defineProps<{ modelValue: boolean; config?: { id: number; name: string; url: string; httpRequest?: HttpRequestConfig | null }; send: (id: number, args: Record<string, unknown>) => Promise<McpTestResponse> }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; tested: [] }>()
const argumentsText = ref('{}'), sending = ref(false), error = ref(''), result = ref<HttpTestResult>()
watch(() => props.modelValue, open => {
  if (!open) return
  error.value = ''; result.value = undefined
  argumentsText.value = JSON.stringify(Object.fromEntries((props.config?.httpRequest?.variables || []).map(item => [item.name,
    Object.hasOwn(props.config?.httpRequest?.testValues || {}, item.name) ? props.config!.httpRequest!.testValues![item.name] : item.example ?? (item.type === 'null' ? null : item.type === 'string' ? '' : item.type === 'boolean' ? false : item.type === 'array' ? [] : item.type === 'object' ? {} : 0)])), null, 2)
})
async function sendRequest() {
  if (sending.value || !props.config) return
  error.value = ''; result.value = undefined
  let args: Record<string, unknown>
  try { args = JSON.parse(argumentsText.value); if (!args || Array.isArray(args) || typeof args !== 'object') throw new Error() }
  catch { error.value = '动态参数必须是合法的 JSON 对象'; return }
  sending.value = true
  try {
    if (props.config.httpRequest?.method === 'POST') {
      try { await ElMessageBox.confirm('将向该接口实际发送 POST 请求，可能产生业务操作。是否发送？', '发送请求确认', { type: 'warning', confirmButtonText: '确认发送', cancelButtonText: '取消' }) } catch { return }
    }
    const response = await props.send(props.config.id, args)
    if (!response.success) throw new Error(response.message || '请求失败')
    result.value = response.data.result; emit('tested')
    if (!result.value) ElMessage.success('连接成功，工具列表已更新')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '请求失败或超时，请检查地址与后端网络' }
  finally { sending.value = false }
}
</script>

<style scoped lang="scss">
.response { margin-top: 16px; span { margin-left: 12px; } pre { max-height: 340px; overflow: auto; background: #f5f7fa; padding: 12px; white-space: pre-wrap; overflow-wrap: anywhere; } }:deep(.el-alert__title) { overflow-wrap: anywhere; }:deep(textarea) { font-family: Consolas, monospace; }
</style>
