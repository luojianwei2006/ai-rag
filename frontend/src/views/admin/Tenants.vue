<template>
  <t-card title="商户管理" :bordered="false">
    <template #actions>
      <t-button theme="primary" @click="showRegisterDialog = true">➕ 新增商户</t-button>
    </template>
    <t-table
      :data="tenants"
      :columns="columns"
      row-key="id"
      :loading="loading"
      stripe
    >
      <template #is_active="{ row }">
        <t-tag :theme="row.is_active ? 'success' : 'danger'">
          {{ row.is_active ? '正常' : '已禁用' }}
        </t-tag>
      </template>
      <template #chat_url="{ row }">
        <t-link :href="`/chat/${row.chat_token}`" target="_blank" theme="primary">
          访问链接
        </t-link>
        <t-button size="small" variant="text" @click="copyLink(row.chat_token)" style="margin-left:4px">复制</t-button>
      </template>
      <template #actions="{ row }">
        <t-button
          size="small"
          :theme="row.is_active ? 'danger' : 'success'"
          variant="outline"
          @click="toggleTenant(row)"
        >
          {{ row.is_active ? '禁用' : '启用' }}
        </t-button>
      </template>
    </t-table>

    <!-- 新增商户对话框 -->
    <t-dialog v-model:visible="showRegisterDialog" header="新增商户" :on-confirm="handleRegister">
      <t-form :data="newTenant" label-width="100px">
        <t-form-item label="邮箱" required>
          <t-input v-model="newTenant.email" placeholder="商户登录邮箱" />
        </t-form-item>
        <t-form-item label="公司名称">
          <t-input v-model="newTenant.company_name" placeholder="选填" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </t-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { adminApi, tenantApi } from '@/api'

const loading = ref(false)
const tenants = ref([])
const showRegisterDialog = ref(false)
const newTenant = ref({ email: '', company_name: '' })

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'email', title: '邮箱' },
  { colKey: 'company_name', title: '公司名称' },
  { colKey: 'is_active', title: '状态', cell: 'is_active' },
  { colKey: 'chat_url', title: '客服链接', cell: 'chat_url' },
  { colKey: 'created_at', title: '注册时间', width: 160 },
  { colKey: 'actions', title: '操作', cell: 'actions', width: 80 }
]

async function loadTenants() {
  loading.value = true
  try {
    tenants.value = await adminApi.getTenants()
  } finally {
    loading.value = false
  }
}

async function toggleTenant(row) {
  try {
    const res = await adminApi.toggleTenant(row.id)
    row.is_active = res.is_active
    MessagePlugin.success(res.is_active ? '已启用' : '已禁用')
  } catch (e) {}
}

async function handleRegister() {
  if (!newTenant.value.email) {
    MessagePlugin.warning('请填写邮箱')
    return
  }
  try {
    const res = await tenantApi.register(newTenant.value)
    MessagePlugin.success(res.message)
    showRegisterDialog.value = false
    newTenant.value = { email: '', company_name: '' }
    loadTenants()
  } catch (e) {}
}

function copyLink(token) {
  const url = `${window.location.origin}/chat/${token}`
  navigator.clipboard.writeText(url)
  MessagePlugin.success('链接已复制')
}

onMounted(loadTenants)
</script>
