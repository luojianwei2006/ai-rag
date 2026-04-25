<template>
  <t-layout class="tenant-layout">
    <t-aside width="220px" class="sidebar">
      <div class="logo-area">
        <span class="logo-icon">💬</span>
        <div class="logo-text">
          <div class="company">{{ auth.userInfo?.company_name || '商户后台' }}</div>
          <div class="email">{{ auth.userInfo?.email }}</div>
        </div>
      </div>
      <t-menu theme="dark" :value="activeMenu" @change="handleMenuChange">
        <t-menu-item value="/tenant/knowledge">
          <template #icon><t-icon name="file" /></template>
          知识库管理
        </t-menu-item>
        <t-menu-item value="/tenant/qa-test">
          <template #icon><t-icon name="chat" /></template>
          问答测试
        </t-menu-item>
        <t-menu-item value="/tenant/api-keys">
          <template #icon><t-icon name="key" /></template>
          API Key配置
        </t-menu-item>
        <t-menu-item value="/tenant/chat-monitor">
          <template #icon><t-icon name="desktop" /></template>
          实时客服监控
        </t-menu-item>
        <t-menu-item value="/tenant/chat-history">
          <template #icon><t-icon name="history" /></template>
          聊天记录
        </t-menu-item>
        <t-menu-item value="/tenant/change-password">
          <template #icon><t-icon name="lock-on" /></template>
          修改密码
        </t-menu-item>
        <t-menu-item value="/tenant/integrations">
          <template #icon><t-icon name="link" /></template>
          第三方接入
        </t-menu-item>
        <t-submenu value="/tenant/xhs" title="小红书发布">
          <template #icon><span style="font-size:16px">📕</span></template>
          <t-menu-item value="/tenant/xhs-accounts">账号矩阵</t-menu-item>
          <t-menu-item value="/tenant/xhs-materials">素材库</t-menu-item>
          <t-menu-item value="/tenant/xhs-tasks">发布任务</t-menu-item>
        </t-submenu>
      </t-menu>
      <div class="bottom-actions">
        <div class="points-info" v-if="auth.userInfo">
          <div class="points-label">💰 积分余额</div>
          <div class="points-value" :class="{ 'points-low': auth.userInfo.points_balance < 50 }">
            {{ auth.userInfo.points_balance || 0 }} 点
          </div>
        </div>
        <div class="chat-link-info" v-if="auth.userInfo?.chat_token">
          <div class="link-label">🔗 客服链接</div>
          <div class="link-url" @click="copyLink">
            点击复制链接
          </div>
        </div>
        <div class="logout-btn" @click="handleLogout">
          <t-icon name="poweroff" /> 退出登录
        </div>
      </div>
    </t-aside>
    <t-layout>
      <t-content class="content">
        <router-view />
      </t-content>
    </t-layout>
  </t-layout>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)

function handleMenuChange(path) { router.push(path) }
function handleLogout() { auth.logout(); router.push('/login') }
function copyLink() {
  const url = `${window.location.origin}/chat/${auth.userInfo?.chat_token}`
  navigator.clipboard.writeText(url)
  MessagePlugin.success('客服链接已复制')
}
</script>

<style scoped>
.tenant-layout { min-height: 100vh; }
.sidebar { background: #1a1a2e !important; display: flex; flex-direction: column; }
.logo-area {
  padding: 16px;
  display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo-icon { font-size: 28px; flex-shrink: 0; }
.logo-text { overflow: hidden; }
.company { color: white; font-size: 14px; font-weight: bold; truncate: ellipsis; overflow: hidden; white-space: nowrap; }
.email { color: rgba(255,255,255,0.5); font-size: 11px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.bottom-actions { margin-top: auto; border-top: 1px solid rgba(255,255,255,0.1); }
.points-info { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.points-label { color: rgba(255,255,255,0.5); font-size: 11px; margin-bottom: 4px; }
.points-value {
  color: #00a870; font-size: 16px; font-weight: bold;
  background: rgba(0,168,112,0.1); padding: 6px 10px; border-radius: 6px;
  text-align: center;
}
.points-value.points-low { color: #e34d59; background: rgba(227,77,89,0.1); }
.chat-link-info { padding: 12px 16px; }
.link-label { color: rgba(255,255,255,0.5); font-size: 11px; margin-bottom: 4px; }
.link-url {
  color: #4facfe; font-size: 12px; cursor: pointer;
  background: rgba(79,172,254,0.1); padding: 6px 10px; border-radius: 6px;
  text-align: center;
}
.link-url:hover { background: rgba(79,172,254,0.2); }
.logout-btn {
  padding: 14px 24px; color: rgba(255,255,255,0.6); cursor: pointer;
  display: flex; align-items: center; gap: 8px; font-size: 14px; transition: color 0.2s;
}
.logout-btn:hover { color: white; }
.content { padding: 24px; background: #f5f7fa; min-height: 100vh; }
</style>
