import request from '@/util/request';

// 基础路径，由于 request 工具中已经配置了 baseURL，这里可以为空
const baseUrl = 'info/sum_table';

// 获取汇总表数据
export function getSumTableData(data: any) {
  return request({
    url: `${baseUrl}/get_data_json`,
    method: 'POST',
    data
  })
}

// 更新检测项目汇总表中的单项
export function updateInspectionItem(data: any) {
  return request({
    url: `${baseUrl}/update_inspection_item`,
    method: 'POST',
    data
  })
}

// 生成基础汇总表
export function generateBasicSummary(data: { template_url: string, extractfile_url?: string, dataFileUrls?: Array<any>, contractNo?: string }) {
  return request({
    url: `${baseUrl}/generate_basic_summary`,
    method: 'POST',
    data,
    timeout: 600000 // 将超时时间增加到 600s (10分钟)，因为大模型解析可能较慢
  })
}

// 删除企业诉求申请 (现改为删除合同)
export function logicDeleteById(data: { id: number }) {
  return request({
    url: `${baseUrl}/delete_contract`,
    method: 'POST',
    data
  })
}

// AI Excel 核验
export function verifyExcel(data: any) {
  return request({
    url: `ai-excel/check/verify`,
    method: 'POST',
    data,
    timeout: 600000 // 将超时时间增加到 600s (10分钟)，因为大模型解析可能较慢
  })
}

// 生成自动填写报告并返回文件流
export function generateAutoReport(data: { contractNo: string }) {
  return request({
    url: `ai-excel/generate_report/generate_report`,
    method: 'POST',
    data,
    responseType: 'blob',
    timeout: 600000 // 将超时时间增加到 600s (10分钟)，因为大模型解析和生成可能较慢
  })
}

// 生成带有表格的原始记录，后端上传后返回 fileUrl
export function generateRawRecord(data: { contractNo: string, inspectionId: number }) {
  return request({
    url: `ai-excel/generate_report/generate_raw_record`,
    method: 'POST',
    data,
    timeout: 600000
  })
}

// 批量删除合同
export function batchDeleteContract(data: { ids: number[] }) {
  return request({
    url: `${baseUrl}/batch_delete_contract`,
    method: 'POST',
    data
  })
}

// 试验条件 OCR 识别回填
export function fillinOCRData(data: { image_url: string[], data: any[] }) {
  return request({
    url: `info/glmocr/fillin`,
    method: 'POST',
    data,
    timeout: 600000
  })
}


// 流式ai对话
export function chatBotStream(data: { session_id?: string | null, query: string, file_urls?: string, type: 'chat' | 'image' }) {
  const baseUrl = import.meta.env.VITE_APP_BASE_URL || '';
  // Ensure we don't double the 'api' prefix and include a slash
  const url = `${baseUrl}/chatbot/chat/stream`;
  return fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data)
  });
}
