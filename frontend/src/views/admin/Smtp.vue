<template>
  <t-card title="SMTP 邮件服务配置" :bordered="false">
    <t-alert theme="info" message="配置SMTP后，系统可自动向新注册商户发送密码邮件和重置密码邮件。" style="margin-bottom: 20px;" />
    <t-form :data="form" label-width="140px">
      <t-row :gutter="16">
        <t-col :span="12">
          <t-form-item label="SMTP 服务器">
            <t-input v-model="form.smtp_host" placeholder="如: smtp.qq.com" />
          </t-form-item>
        </t-col>
        <t-col :span="12">
          <t-form-item label="SMTP 端口">
            <t-input v-model="form.smtp_port" placeholder="如: 465 或 587" />
          </t-form-item>
        </t-col>
      </t-row>
      <t-row :gutter="16">
        <t-col :span="12">
          <t-form-item label="用户名">
            <t-input v-model="form.smtp_user" placeholder="SMTP登录账号" />
          </t-form-item>
        </t-col>
        <t-col :span="12">
          <t-form-item label="密码/授权码">
            <t-input v-model="form.smtp_password" type="password" placeholder="SMTP密码或授权码" />
          </t-form-item>
        </t-col>
      </t-row>
      <t-row :gutter="16">
        <t-col :span="12">
          <t-form-item label="发件人地址">
            <t-input v-model="form.smtp_from" placeholder="如: noreply@example.com" />
          </t-form-item>
        </t-col>
        <t-col :span="12">
          <t-form-item label="启用TLS/SSL">
            <t-switch v-model="smtpTls" />
          </t-form-item>
        </t-col>
      </t-row>

      <t-form-item>
        <t-space>
          <t-button theme="primary" :loading="saving" @click="handleSave">保存配置</t-button>
          <t-button variant="outline" @click="showTestDialog = true">发送测试邮件</t-button>
        </t-space>
      </t-form-item>
    </t-form>

    <!-- 测试邮件对话框 -->
    <t-dialog v-model:visible="showTestDialog" header="发送测试邮件" :on-confirm="handleTestSend" confirm-btn="发送">
      <t-form-item label="收件人邮箱">
        <t-input v-model="testEmail" placeholder="请输入测试邮箱地址" />
      </t-form-item>
    </t-dialog>
  </t-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { adminApi } from '@/api'

const form = ref({
  smtp_host: '', smtp_port: '465', smtp_user: '',
  smtp_password: '', smtp_from: '', smtp_tls: 'true'
})
const smtpTls = computed({
  get: () => form.value.smtp_tls === 'true',
  set: (v) => { form.value.smtp_tls = v ? 'true' : 'false' }
})
const saving = ref(false)
const showTestDialog = ref(false)
const testEmail = ref('')

onMounted(async () => {
  try {
    const config = await adminApi.getSmtpConfig()
    Object.assign(form.value, config)
  } catch (e) {}
})

async function handleSave() {
  saving.value = true
  try {
    await adminApi.saveSmtpConfig(form.value)
    MessagePlugin.success('SMTP配置保存成功')
  } catch (e) {} finally {
    saving.value = false
  }
}

async function handleTestSend() {
  if (!testEmail.value) {
    MessagePlugin.warning('请输入测试邮箱')
    return
  }
  try {
    await adminApi.testSmtp({ to_email: testEmail.value })
    MessagePlugin.success('测试邮件发送成功！请查收')
    showTestDialog.value = false
  } catch (e) {}
}
</script>
