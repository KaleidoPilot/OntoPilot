import axios from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosRequestConfig } from 'axios';
import { ElMessage } from 'element-plus';

// 定义后端返回的通用数据结构
export interface ResponseData<T = any> {
  code: number;
  msg: string;
  message?: string;
  data: T;
  success: boolean;
}

// 定义自定义的请求实例接口，直接返回 data
interface CustomAxiosInstance extends AxiosInstance {
  <T = any, R = ResponseData<T>>(config: AxiosRequestConfig): Promise<R>;
  request<T = any, R = ResponseData<T>>(config: AxiosRequestConfig): Promise<R>;
  get<T = any, R = ResponseData<T>>(url: string, config?: AxiosRequestConfig): Promise<R>;
  delete<T = any, R = ResponseData<T>>(url: string, config?: AxiosRequestConfig): Promise<R>;
  head<T = any, R = ResponseData<T>>(url: string, config?: AxiosRequestConfig): Promise<R>;
  options<T = any, R = ResponseData<T>>(url: string, config?: AxiosRequestConfig): Promise<R>;
  post<T = any, R = ResponseData<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R>;
  put<T = any, R = ResponseData<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R>;
  patch<T = any, R = ResponseData<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R>;
}

// 创建 axios 实例
const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_URL, // 从环境变量获取基础域名
  timeout: 10000, // 请求超时时间
  headers: {
    'Content-Type': 'application/json;charset=utf-8'
  }
}) as CustomAxiosInstance;

const loginExpiredText = /请重新登录|登录已失效|登录状态已失效|未登录|用户身份不一致/

export function isLoginExpired(status?: number, body?: unknown): boolean {
  if (status === 401) return true
  if (!body || typeof body !== 'object') return false
  const record = body as { code?: unknown; detail?: unknown; message?: unknown; msg?: unknown }
  if (record.code === 401) return true
  const text = [record.detail, record.message, record.msg].filter((item): item is string => typeof item === 'string').join('\n')
  return loginExpiredText.test(text)
}

let leavingForLogin = false
export function leaveForLogin() {
  if (leavingForLogin || window.location.hash.startsWith('#/login')) return
  leavingForLogin = true
  localStorage.removeItem('token')
  localStorage.removeItem('userInfo')
  localStorage.removeItem('currentOrganization')
  window.location.hash = '/login'
}

function stopForLogin(status?: number, body?: unknown) {
  if (!isLoginExpired(status, body)) return null
  leaveForLogin()
  return new Promise(() => undefined)
}

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const userInfoStr = localStorage.getItem('userInfo');
    let fixedOrganization = false;
    if (userInfoStr) {
      try {
        const userInfo = JSON.parse(userInfoStr);
        if (userInfo.id) config.headers['x-user-id'] = userInfo.id;
        if (userInfo.account) config.headers['x-user-name'] = userInfo.account;
        if (userInfo.userType) config.headers['x-user-type'] = userInfo.userType;
        if (userInfo.groupId) config.headers['x-group-id'] = userInfo.groupId;
        if (userInfo.mcpToken) config.headers['x-mcp-token'] = userInfo.mcpToken;
        fixedOrganization = userInfo.userType === 'external' || userInfo.deptLevel === 1;
        if (fixedOrganization && userInfo.orgId) {
          config.headers['x-org-id'] = userInfo.orgId;
        }
      } catch (e) {}
    }
    const currentOrganization = localStorage.getItem('currentOrganization');
    if (currentOrganization && !fixedOrganization) {
      try {
        const organization = JSON.parse(currentOrganization);
        if (organization.id) config.headers['x-org-id'] = organization.id;
      } catch (e) {}
    }
    return config;
  },
  (error: any) => {
    return stopForLogin(error.response?.status, error.response?.data) || Promise.reject(error);
  }
);

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const responseType = response.config.responseType;
    if (responseType === 'blob' || responseType === 'arraybuffer') {
      return response;
    }
    const res = response.data;
    const expired = stopForLogin(response.status, res)
    if (expired) return expired
    // 根据后端返回的状态码处理
    // 200成功 和 400业务报错 正常返回给业务层
    if (res.code && res.code !== 200 && res.code !== 400) {
      ElMessage.error(res.message || res.msg || 'Error');
      return Promise.reject(new Error(res.message || res.msg || 'Error'));
    }
    return res;
  },
  (error: any) => {
    const expired = stopForLogin(error.response?.status, error.response?.data)
    if (expired) return expired
    if (error.response && error.response.data) {
      const data = error.response.data;
      if (typeof data.detail === 'string') {
        ElMessage.error(data.detail);
        return Promise.reject(new Error(data.detail));
      }
      if (data.success === false) {
        // 对于 400 正常业务报错，直接 resolve 给调用方自行处理（如 login 页面的 res.success 判断）
        if (data.code === 400) {
          return Promise.resolve(data);
        }
        // 对于 500 等其他错误，全局提示并 reject
        ElMessage.error(data.message || data.msg || '服务器错误');
        return Promise.reject(new Error(data.message || data.msg || '服务器错误'));
      }
    }
    
    console.error('err' + error);
    ElMessage.error(error.message || '网络错误');
    return Promise.reject(error);
  }
);

export default service;
