<template>
  <div>
    <t-row :gutter="16" style="margin-bottom: 24px;">
      <t-col :span="6">
        <t-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: linear-gradient(135deg,#667eea,#764ba2)">🏢</div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.tenants }}</div>
            <div class="stat-label">商户总数</div>
          </div>
        </t-card>
      </t-col>
      <t-col :span="6">
        <t-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: linear-gradient(135deg,#f093fb,#f5576c)">💬</div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.activeTenants }}</div>
            <div class="stat-label">活跃商户</div>
          </div>
        </t-card>
      </t-col>
      <t-col :span="6">
        <t-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: linear-gradient(135deg,#4facfe,#00f2fe)">🔑</div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.apiKeys }}</div>
            <div class="stat-label">已配置API Key</div>
          </div>
        </t-card>
      </t-col>
      <t-col :span="6">
        <t-card class="stat-card" :bordered="false">
          <div class="stat-icon" style="background: linear-gradient(135deg,#43e97b,#38f9d7)">📧</div>
          <div class="stat-info">
            <div class="stat-num">{{ stats.smtp ? '已配置' : '未配置' }}</div>
            <div class="stat-label">SMTP状态</div>
          </div>
        </t-card>
      </t-col>
    </t-row>

    <t-card title="快速导航" :bordered="false">
      <t-row :gutter="16">
        <t-col :span="6" v-for="item in quickLinks" :key="item.path">
          <div class="quick-link" @click="$router.push(item.path)">
            <span class="ql-icon">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </div>
        </t-col>
      </t-row>
    </t-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api'

const stats = ref({ tenants: 0, activeTenants: 0, apiKeys: 0, smtp: false })
const quickLinks = [
  { path: '/admin/tenants', icon: '🏢', label: '商户管理' },
  { path: '/admin/api-keys', icon: '🔑', label: 'API Key配置' },
  { path: '/admin/smtp', icon: '📧', label: 'SMTP配置' },
  { path: '/admin/change-password', icon: '🔐', label: '修改密码' }
]

onMounted(async () => {
  try {
    const [tenants, keys, smtp] = await Promise.all([
      adminApi.getTenants(),
      adminApi.getApiKeys(),
      adminApi.getSmtpConfig()
    ])
    stats.value.tenants = tenants.length
    stats.value.activeTenants = tenants.filter(t => t.is_active).length
    stats.value.apiKeys = Object.values(keys).filter(v => v && v !== '').length
    stats.value.smtp = !!smtp.smtp_host
  } catch (e) {}
})
</script>

<style scoped>
.stat-card { border-radius: 12px !important; }
:deep(.t-card__body) { display: flex; align-items: center; gap: 16px; }
.stat-icon { width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; }
.stat-num { font-size: 28px; font-weight: bold; color: #333; }
.stat-label { color: #888; font-size: 14px; }
.quick-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 15px;
  color: #333;
}
.quick-link:hover { background: #e8f0fe; color: #4a6cf7; transform: translateY(-2px); }
.ql-icon { font-size: 20px; }
</style>
