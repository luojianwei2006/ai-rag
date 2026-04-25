import axios from 'axios'
import { MessagePlugin } from 'tdesign-vue-next'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.detail || '请求失败'
    const url = err.config?.url || ''
    const isLoginUrl = url.includes('/login')

    if (err.response?.status === 401 && !isLoginUrl) {
      // 非登录接口的 401：token 失效，跳回登录页
      const userType = localStorage.getItem('userType')
      localStorage.removeItem('token')
      localStorage.removeItem('userType')
      window.location.href = userType === 'admin' ? '/admin/login' : '/login'
    } else {
      // 登录接口报错 或 其他错误：直接弹提示
      MessagePlugin.error(msg)
    }
    return Promise.reject(err)
  }
)

// 管理员接口
export const adminApi = {
  login: (data) => api.post('/admin/login', data),
  changePassword: (data) => api.post('/admin/change-password', data),
  getSmtpConfig: () => api.get('/admin/smtp-config'),
  saveSmtpConfig: (data) => api.post('/admin/smtp-config', data),
  testSmtp: (data) => api.post('/admin/smtp-test', data),
  getApiKeys: () => api.get('/admin/api-keys'),
  saveApiKeys: (data) => api.post('/admin/api-keys', data),
  testApiKey: (data) => api.post('/admin/api-keys/test', data),
  getTenants: () => api.get('/admin/tenants'),
  toggleTenant: (id) => api.patch(`/admin/tenants/${id}/toggle`),
  // 积分管理
  getPointsConfig: () => api.get('/admin/points/config'),
  savePointsConfig: (data) => api.post('/admin/points/config', data),
  getTenantsPoints: () => api.get('/admin/points/tenants'),
  getTenantPoints: (id) => api.get(`/admin/points/tenants/${id}`),
  rechargeTenantPoints: (id, data) => api.post(`/admin/points/tenants/${id}/recharge`, data),
  getPointsTransactions: () => api.get('/admin/points/transactions')
}

// 商户接口
export const tenantApi = {
  register: (data) => api.post('/tenant/register', data),
  login: (data) => api.post('/tenant/login', data),
  resetPassword: (data) => api.post('/tenant/reset-password', data),
  changePassword: (data) => api.post('/tenant/change-password', data),
  getProfile: () => api.get('/tenant/profile'),
  updateApiKeys: (data) => api.put('/tenant/api-keys', data),
  testApiKey: (data) => api.post('/tenant/api-keys/test', data),
  // 飞书配置
  getFeishuConfig: () => api.get('/feishu/config'),
  updateFeishuConfig: (data) => api.post('/feishu/config', data),
  testFeishuConnection: (data) => api.post('/feishu/test', data),
  // 企业微信配置
  getWeComConfig: () => api.get('/wecom/config'),
  updateWeComConfig: (data) => api.post('/wecom/config', data),
  testWeComConnection: (data) => api.post('/wecom/test', data)
}

// 知识库接口
export const knowledgeApi = {
  upload: (formData) => api.post('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000  // 上传文件超时 2 分钟
  }),
  list: () => api.get('/knowledge/list'),
  delete: (id) => api.delete(`/knowledge/${id}`),
  qaTest: (data) => api.post('/knowledge/qa-test', data),
  // 网页爬取
  startCrawl: (data) => api.post('/knowledge/crawl', data),
  getCrawlStatus: (taskId) => api.get(`/knowledge/crawl/${taskId}`),
  importFromCrawl: (data) => api.post('/knowledge/crawl-import', data)
}

// 聊天接口
export const chatApi = {
  getSessions: () => api.get('/chat/sessions'),
  getMessages: (sessionId) => api.get(`/chat/sessions/${sessionId}/messages`),
  humanReply: (data) => api.post('/chat/human-reply', data),
  getChatInfo: (chatToken) => axios.get(`/api/public/chat/${chatToken}/info`)
}

// 小红书矩阵发布接口
export const xhsApi = {
  // 账号管理
  getAccounts: () => api.get('/xhs/accounts'),
  createAccount: (data) => api.post('/xhs/accounts', data),
  updateAccount: (id, data) => api.put(`/xhs/accounts/${id}`, data),
  deleteAccount: (id) => api.delete(`/xhs/accounts/${id}`),

  // 素材库
  getMaterials: (type) => api.get('/xhs/materials', { params: type ? { material_type: type } : {} }),
  getApiKeys: () => api.get('/xhs/api-keys'),
  createMaterial: (data) => api.post('/xhs/materials', data),
  uploadImage: (formData) => api.post('/xhs/materials/upload-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000
  }),
  updateMaterial: (id, data) => api.put(`/xhs/materials/${id}`, data),
  batchDeleteMaterials: (ids) => api.post('/xhs/materials/batch-delete', { ids }),
  deleteMaterial: (id) => api.delete(`/xhs/materials/${id}`),

  // 任务管理
  getTasks: () => api.get('/xhs/tasks'),
  createTask: (data) => api.post('/xhs/tasks', data),
  updateTask: (id, data) => api.put(`/xhs/tasks/${id}`, data),
  deleteTask: (id) => api.delete(`/xhs/tasks/${id}`),
  generateArticle: (taskId) => api.post(`/xhs/tasks/${taskId}/generate`, {}, { timeout: 120000 }),
  publishTask: (taskId) => api.post(`/xhs/tasks/${taskId}/publish`),
}

export default api
