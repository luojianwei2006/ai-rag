<template>
  <t-card title="修改密码" :bordered="false" style="max-width: 480px;">
    <t-form :data="form" label-width="100px">
      <t-form-item label="原密码">
        <t-input v-model="form.old_password" type="password" placeholder="请输入原密码" />
      </t-form-item>
      <t-form-item label="新密码">
        <t-input v-model="form.new_password" type="password" placeholder="至少6位" />
      </t-form-item>
      <t-form-item label="确认密码">
        <t-input v-model="form.confirm_password" type="password" placeholder="再次输入新密码" />
      </t-form-item>
      <t-form-item>
        <t-button theme="primary" :loading="loading" @click="handleSubmit">修改密码</t-button>
      </t-form-item>
    </t-form>
  </t-card>
</template>

<script setup>
import { ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'

const loading = ref(false)
const form = ref({ old_password: '', new_password: '', confirm_password: '' })

async function handleSubmit() {
  if (!form.value.old_password || !form.value.new_password) return MessagePlugin.warning('请填写完整')
  if (form.value.new_password !== form.value.confirm_password) return MessagePlugin.error('两次密码不一致')
  if (form.value.new_password.length < 6) return MessagePlugin.warning('密码至少6位')
  loading.value = true
  try {
    await tenantApi.changePassword({ old_password: form.value.old_password, new_password: form.value.new_password })
    MessagePlugin.success('密码修改成功')
    form.value = { old_password: '', new_password: '', confirm_password: '' }
  } finally {
    loading.value = false
  }
}
</script>
