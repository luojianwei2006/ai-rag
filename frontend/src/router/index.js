import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  // 公共路由
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/admin/Login.vue')
  },
  {
    path: '/login',
    name: 'TenantLogin',
    component: () => import('@/views/tenant/Login.vue')
  },
  {
    path: '/register',
    name: 'TenantRegister',
    component: () => import('@/views/tenant/Register.vue')
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/tenant/ResetPassword.vue')
  },

  // 管理员后台
  {
    path: '/admin',
    component: () => import('@/views/admin/Layout.vue'),
    meta: { requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'AdminDashboard', component: () => import('@/views/admin/Dashboard.vue') },
      { path: 'api-keys', name: 'AdminApiKeys', component: () => import('@/views/admin/ApiKeys.vue') },
      { path: 'smtp', name: 'AdminSmtp', component: () => import('@/views/admin/Smtp.vue') },
      { path: 'tenants', name: 'AdminTenants', component: () => import('@/views/admin/Tenants.vue') },
      { path: 'points', name: 'AdminPoints', component: () => import('@/views/admin/PointsManage.vue') },
      { path: 'change-password', name: 'AdminChangePassword', component: () => import('@/views/admin/ChangePassword.vue') }
    ]
  },

  // 商户后台
  {
    path: '/tenant',
    component: () => import('@/views/tenant/Layout.vue'),
    meta: { requiresTenant: true },
    children: [
      { path: '', redirect: '/tenant/knowledge' },
      { path: 'knowledge', name: 'TenantKnowledge', component: () => import('@/views/tenant/Knowledge.vue') },
      { path: 'knowledge-import', name: 'TenantKnowledgeImport', component: () => import('@/views/tenant/KnowledgeImport.vue') },
      { path: 'qa-test', name: 'TenantQaTest', component: () => import('@/views/tenant/QaTest.vue') },
      { path: 'api-keys', name: 'TenantApiKeys', component: () => import('@/views/tenant/ApiKeys.vue') },
      { path: 'chat-monitor', name: 'TenantChatMonitor', component: () => import('@/views/tenant/ChatMonitor.vue') },
      { path: 'chat-history', name: 'TenantChatHistory', component: () => import('@/views/tenant/ChatHistory.vue') },
      { path: 'change-password', name: 'TenantChangePassword', component: () => import('@/views/tenant/ChangePassword.vue') },
      { path: 'integrations', name: 'TenantIntegrations', component: () => import('@/views/tenant/Integrations.vue') }
    ]
  },

  // 客户聊天页面（公开）
  {
    path: '/chat/:chatToken',
    name: 'CustomerChat',
    component: () => import('@/views/chat/CustomerChat.vue')
  },

  // 默认重定向
  { path: '/', redirect: '/login' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const userType = localStorage.getItem('userType')

  if (to.meta.requiresAdmin) {
    if (!token || userType !== 'admin') {
      return next('/admin/login')
    }
  }
  if (to.meta.requiresTenant) {
    if (!token || userType !== 'tenant') {
      return next('/login')
    }
  }
  next()
})

export default router
