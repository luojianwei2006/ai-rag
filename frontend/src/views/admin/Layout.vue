<template>
  <t-layout class="admin-layout">
    <t-aside width="220px" class="sidebar">
      <div class="logo-area">
        <span class="logo-icon">💬</span>
        <span class="logo-text">管理后台</span>
      </div>
      <t-menu theme="dark" :value="activeMenu" @change="handleMenuChange">
        <t-menu-item value="/admin/dashboard">
          <template #icon><t-icon name="dashboard" /></template>
          仪表盘
        </t-menu-item>
        <t-menu-item value="/admin/tenants">
          <template #icon><t-icon name="usergroup" /></template>
          商户管理
        </t-menu-item>
        <t-menu-item value="/admin/points">
          <template #icon><t-icon name="money" /></template>
          积分管理
        </t-menu-item>
        <t-menu-item value="/admin/api-keys">
          <template #icon><t-icon name="key" /></template>
          API Key配置
        </t-menu-item>
        <t-menu-item value="/admin/smtp">
          <template #icon><t-icon name="mail" /></template>
          SMTP配置
        </t-menu-item>
        <t-menu-item value="/admin/change-password">
          <template #icon><t-icon name="lock-on" /></template>
          修改密码
        </t-menu-item>
      </t-menu>
      <div class="logout-btn" @click="handleLogout">
        <t-icon name="poweroff" /> 退出登录
      </div>
    </t-aside>
    <t-layout>
      <t-header class="header">
        <div class="header-right">
          <span>👤 {{ auth.userInfo?.username }}</span>
        </div>
      </t-header>
      <t-content class="content">
        <router-view />
      </t-content>
    </t-layout>
  </t-layout>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)

function handleMenuChange(path) {
  router.push(path)
}

function handleLogout() {
  auth.logout()
  router.push('/admin/login')
}
</script>

<style scoped>
.admin-layout { min-height: 100vh; }
.sidebar { background: #1a1a2e !important; display: flex; flex-direction: column; }
.logo-area {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo-icon { font-size: 28px; }
.logo-text { color: white; font-size: 16px; font-weight: bold; }
.logout-btn {
  margin-top: auto;
  padding: 16px 24px;
  color: rgba(255,255,255,0.6);
  cursor: pointer;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  transition: color 0.2s;
}
.logout-btn:hover { color: white; }
.header {
  background: white !important;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 24px;
}
.header-right { color: #666; font-size: 14px; }
.content { padding: 24px; background: #f5f7fa; min-height: calc(100vh - 64px); }
</style>
