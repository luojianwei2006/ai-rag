<template>
  <div class="integrations-page">
    <div class="page-header">
      <h2 class="page-title">第三方接入</h2>
      <p class="page-desc">配置微信、飞书等第三方平台的客服接入</p>
    </div>

    <!-- 飞书配置卡片 -->
    <t-card title="🚀 飞书" class="integration-card">
      <div class="integration-header">
        <div class="integration-info">
          <div class="integration-name">飞书机器人</div>
          <div class="integration-desc">用户可以在飞书私聊机器人，实现AI客服对话</div>
        </div>
        <t-switch v-model="feishuConfig.enabled" @change="handleFeishuEnableChange" />
      </div>

      <t-divider />

      <div class="config-form">
        <!-- App ID -->
        <div class="form-item">
          <label class="form-label">
            App ID
            <t-tooltip content="飞书开放平台应用的 App ID">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="feishuConfig.app_id"
            placeholder="cli_xxxxxxxxxxxxxxxx"
            style="width: 400px"
          />
        </div>

        <!-- App Secret -->
        <div class="form-item">
          <label class="form-label">
            App Secret
            <t-tooltip content="飞书开放平台应用的 App Secret，首次配置后不可查看">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="feishuConfig.app_secret"
            type="password"
            :placeholder="feishuConfig.app_secret_masked ? '已配置，留空保持不变' : '请输入 App Secret'"
            style="width: 400px"
          />
          <span v-if="feishuConfig.app_secret_masked" class="masked-hint">
            已配置: {{ feishuConfig.app_secret_masked }}
          </span>
        </div>

        <!-- Encrypt Key -->
        <div class="form-item">
          <label class="form-label">
            Encrypt Key（可选）
            <t-tooltip content="消息加密密钥，如需加密传输请配置">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="feishuConfig.encrypt_key"
            type="password"
            :placeholder="feishuConfig.encrypt_key_masked ? '已配置，留空保持不变' : '请输入 Encrypt Key'"
            style="width: 400px"
          />
          <span v-if="feishuConfig.encrypt_key_masked" class="masked-hint">
            已配置: {{ feishuConfig.encrypt_key_masked }}
          </span>
        </div>

        <!-- Webhook URL -->
        <div class="form-item" v-if="feishuConfig.webhook_url">
          <label class="form-label">
            Webhook 地址
            <t-tooltip content="将此地址配置到飞书开放平台的事件订阅中">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <div class="webhook-url">
            <code>{{ fullWebhookUrl }}</code>
            <t-button variant="text" size="small" @click="copyWebhookUrl">
              <t-icon name="copy" />
            </t-button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <t-button theme="primary" :loading="saving" @click="saveFeishuConfig">
            保存配置
          </t-button>
          <t-button variant="outline" :loading="testing" @click="testFeishuConnection">
            测试连接
          </t-button>
        </div>
      </div>

      <!-- 配置指南 -->
      <t-collapse class="guide-collapse">
        <t-collapse-panel header="📖 飞书配置指南">
          <div class="guide-content">
            <h4>1. 创建飞书应用</h4>
            <p>访问 <a href="https://open.feishu.cn/app" target="_blank">飞书开放平台</a>，点击「创建企业自建应用」</p>
            
            <h4>2. 获取凭证</h4>
            <p>进入应用详情页 →「凭证与基础信息」，复制 App ID 和 App Secret</p>
            
            <h4>3. 配置事件订阅</h4>
            <p>进入「事件订阅」页面：</p>
            <ul>
              <li>开启「加密策略」（可选）</li>
              <li>将上方 Webhook 地址填入「请求地址」</li>
              <li>添加事件：im.message.receive_v1（接收消息）</li>
            </ul>
            
            <h4>4. 配置权限</h4>
            <p>进入「权限管理」，添加以下权限：</p>
            <ul>
              <li>im:chat:readonly（获取群组信息）</li>
              <li>im:message:send（发送消息）</li>
              <li>im:message.group_msg（接收群消息）</li>
              <li>im:message.p2p_msg（接收单聊消息）</li>
            </ul>
            
            <h4>5. 发布应用</h4>
            <p>进入「版本管理与发布」，创建版本并申请发布，审核通过后即可使用</p>
          </div>
        </t-collapse-panel>
      </t-collapse>
    </t-card>

    <!-- 企业微信配置卡片 -->
    <t-card title="💼 企业微信" class="integration-card" style="margin-top: 20px">
      <div class="integration-header">
        <div class="integration-info">
          <div class="integration-name">企业微信应用</div>
          <div class="integration-desc">用户可以在企业微信内咨询，实现AI客服对话</div>
        </div>
        <t-switch v-model="wecomConfig.enabled" @change="handleWeComEnableChange" />
      </div>

      <t-divider />

      <div class="config-form">
        <!-- Corp ID -->
        <div class="form-item">
          <label class="form-label">
            CorpID
            <t-tooltip content="企业微信管理后台的 CorpID">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="wecomConfig.corp_id"
            placeholder="wwxxxxxxxxxxxxxxxx"
            style="width: 400px"
          />
        </div>

        <!-- Agent ID -->
        <div class="form-item">
          <label class="form-label">
            AgentID
            <t-tooltip content="企业微信应用的 AgentID">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="wecomConfig.agent_id"
            placeholder="1000002"
            style="width: 400px"
          />
        </div>

        <!-- Secret -->
        <div class="form-item">
          <label class="form-label">
            Secret
            <t-tooltip content="企业微信应用的 Secret，首次配置后不可查看">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="wecomConfig.secret"
            type="password"
            :placeholder="wecomConfig.secret_masked ? '已配置，留空保持不变' : '请输入 Secret'"
            style="width: 400px"
          />
          <span v-if="wecomConfig.secret_masked" class="masked-hint">
            已配置: {{ wecomConfig.secret_masked }}
          </span>
        </div>

        <!-- Token -->
        <div class="form-item">
          <label class="form-label">
            Token（可选）
            <t-tooltip content="用于验证消息签名，如需安全验证请配置">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="wecomConfig.token"
            type="password"
            :placeholder="wecomConfig.token_masked ? '已配置，留空保持不变' : '请输入 Token'"
            style="width: 400px"
          />
          <span v-if="wecomConfig.token_masked" class="masked-hint">
            已配置: {{ wecomConfig.token_masked }}
          </span>
        </div>

        <!-- Encoding AES Key -->
        <div class="form-item">
          <label class="form-label">
            EncodingAESKey（可选）
            <t-tooltip content="消息加密密钥，如需加密传输请配置">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <t-input
            v-model="wecomConfig.encoding_aes_key"
            type="password"
            :placeholder="wecomConfig.encoding_aes_key_masked ? '已配置，留空保持不变' : '请输入 EncodingAESKey'"
            style="width: 400px"
          />
          <span v-if="wecomConfig.encoding_aes_key_masked" class="masked-hint">
            已配置: {{ wecomConfig.encoding_aes_key_masked }}
          </span>
        </div>

        <!-- Webhook URL -->
        <div class="form-item" v-if="wecomConfig.webhook_url">
          <label class="form-label">
            Webhook 地址
            <t-tooltip content="将此地址配置到企业微信应用的事件接收 URL">
              <t-icon name="help-circle" class="help-icon" />
            </t-tooltip>
          </label>
          <div class="webhook-url">
            <code>{{ fullWeComWebhookUrl }}</code>
            <t-button variant="text" size="small" @click="copyWeComWebhookUrl">
              <t-icon name="copy" />
            </t-button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <t-button theme="primary" :loading="wecomSaving" @click="saveWeComConfig">
            保存配置
          </t-button>
          <t-button variant="outline" :loading="wecomTesting" @click="testWeComConnection">
            测试连接
          </t-button>
        </div>
      </div>

      <!-- 配置指南 -->
      <t-collapse class="guide-collapse">
        <t-collapse-panel header="📖 企业微信配置指南">
          <div class="guide-content">
            <h4>1. 创建企业微信应用</h4>
            <p>登录 <a href="https://work.weixin.qq.com/wework_admin" target="_blank">企业微信管理后台</a>，进入「应用管理」→「自建应用」→「创建应用」</p>
            
            <h4>2. 获取凭证</h4>
            <p>进入应用详情页，复制 AgentID 和 Secret</p>
            <p>进入「我的企业」页面，复制 CorpID</p>
            
            <h4>3. 配置接收消息</h4>
            <p>进入应用详情页 →「接收消息」：</p>
            <ul>
              <li>点击「设置API接收」</li>
              <li>将上方 Webhook 地址填入「URL」</li>
              <li>设置 Token 和 EncodingAESKey（可选）</li>
            </ul>
            
            <h4>4. 配置权限</h4>
            <p>确保应用有以下权限：</p>
            <ul>
              <li>发送应用消息</li>
              <li>接收消息</li>
            </ul>
            
            <h4>5. 发布应用</h4>
            <p>点击「应用到成员」，选择可见成员，保存即可使用</p>
          </div>
        </t-collapse-panel>
      </t-collapse>
    </t-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'

// 飞书配置
const feishuConfig = ref({
  enabled: false,
  app_id: '',
  app_secret: '',
  app_secret_masked: '',
  encrypt_key: '',
  encrypt_key_masked: '',
  webhook_url: ''
})

// 企业微信配置
const wecomConfig = ref({
  enabled: false,
  corp_id: '',
  agent_id: '',
  secret: '',
  secret_masked: '',
  token: '',
  token_masked: '',
  encoding_aes_key: '',
  encoding_aes_key_masked: '',
  webhook_url: ''
})

const saving = ref(false)
const testing = ref(false)
const wecomSaving = ref(false)
const wecomTesting = ref(false)

const fullWebhookUrl = computed(() => {
  if (!feishuConfig.value.webhook_url) return ''
  return `${window.location.origin}${feishuConfig.value.webhook_url}`
})

const fullWeComWebhookUrl = computed(() => {
  if (!wecomConfig.value.webhook_url) return ''
  return `${window.location.origin}${wecomConfig.value.webhook_url}`
})

// 加载配置
async function loadConfig() {
  try {
    const res = await tenantApi.getFeishuConfig()
    feishuConfig.value = { ...feishuConfig.value, ...res }
  } catch (e) {
    console.error('加载飞书配置失败:', e)
  }
}

// 保存配置
async function saveFeishuConfig() {
  if (!feishuConfig.value.app_id) {
    MessagePlugin.warning('请输入 App ID')
    return
  }
  
  saving.value = true
  try {
    await tenantApi.updateFeishuConfig({
      enabled: feishuConfig.value.enabled,
      app_id: feishuConfig.value.app_id,
      app_secret: feishuConfig.value.app_secret,
      encrypt_key: feishuConfig.value.encrypt_key
    })
    MessagePlugin.success('配置已保存')
    await loadConfig()
  } catch (e) {
    MessagePlugin.error('保存失败')
  } finally {
    saving.value = false
  }
}

// 测试连接
async function testFeishuConnection() {
  // 检查 App ID
  if (!feishuConfig.value.app_id) {
    MessagePlugin.warning('请输入 App ID')
    return
  }
  
  // 检查 App Secret：如果输入框为空但已配置，提示用户重新输入
  let appSecret = feishuConfig.value.app_secret
  if (!appSecret && !feishuConfig.value.app_secret_masked) {
    MessagePlugin.warning('请输入 App Secret')
    return
  }
  
  testing.value = true
  try {
    await tenantApi.testFeishuConnection({
      app_id: feishuConfig.value.app_id,
      app_secret: appSecret // 如果为空，后端会使用已保存的 Secret
    })
    MessagePlugin.success('连接测试成功')
  } catch (e) {
    MessagePlugin.error(e.response?.data?.detail || '连接测试失败')
  } finally {
    testing.value = false
  }
}

// 复制 Webhook 地址
function copyWebhookUrl() {
  navigator.clipboard.writeText(fullWebhookUrl.value)
  MessagePlugin.success('Webhook 地址已复制')
}

// 启用状态变更
function handleFeishuEnableChange(val) {
  if (val && !feishuConfig.value.app_id) {
    MessagePlugin.warning('请先配置 App ID 和 App Secret')
    feishuConfig.value.enabled = false
  }
}

// 加载企业微信配置
async function loadWeComConfig() {
  try {
    const res = await tenantApi.getWeComConfig()
    wecomConfig.value = { ...wecomConfig.value, ...res }
  } catch (e) {
    console.error('加载企业微信配置失败:', e)
  }
}

// 保存企业微信配置
async function saveWeComConfig() {
  if (!wecomConfig.value.corp_id) {
    MessagePlugin.warning('请输入 CorpID')
    return
  }
  if (!wecomConfig.value.agent_id) {
    MessagePlugin.warning('请输入 AgentID')
    return
  }
  
  wecomSaving.value = true
  try {
    await tenantApi.updateWeComConfig({
      enabled: wecomConfig.value.enabled,
      corp_id: wecomConfig.value.corp_id,
      agent_id: wecomConfig.value.agent_id,
      secret: wecomConfig.value.secret,
      token: wecomConfig.value.token,
      encoding_aes_key: wecomConfig.value.encoding_aes_key
    })
    MessagePlugin.success('配置已保存')
    await loadWeComConfig()
  } catch (e) {
    MessagePlugin.error('保存失败')
  } finally {
    wecomSaving.value = false
  }
}

// 测试企业微信连接
async function testWeComConnection() {
  if (!wecomConfig.value.corp_id) {
    MessagePlugin.warning('请输入 CorpID')
    return
  }
  if (!wecomConfig.value.agent_id) {
    MessagePlugin.warning('请输入 AgentID')
    return
  }
  
  let secret = wecomConfig.value.secret
  if (!secret && !wecomConfig.value.secret_masked) {
    MessagePlugin.warning('请输入 Secret')
    return
  }
  
  wecomTesting.value = true
  try {
    await tenantApi.testWeComConnection({
      corp_id: wecomConfig.value.corp_id,
      agent_id: wecomConfig.value.agent_id,
      secret: secret
    })
    MessagePlugin.success('连接测试成功')
  } catch (e) {
    MessagePlugin.error(e.response?.data?.detail || '连接测试失败')
  } finally {
    wecomTesting.value = false
  }
}

// 复制企业微信 Webhook 地址
function copyWeComWebhookUrl() {
  navigator.clipboard.writeText(fullWeComWebhookUrl.value)
  MessagePlugin.success('Webhook 地址已复制')
}

// 企业微信启用状态变更
function handleWeComEnableChange(val) {
  if (val && (!wecomConfig.value.corp_id || !wecomConfig.value.agent_id)) {
    MessagePlugin.warning('请先配置 CorpID 和 AgentID')
    wecomConfig.value.enabled = false
  }
}

onMounted(() => {
  loadConfig()
  loadWeComConfig()
})
</script>

<style scoped>
.integrations-page {
  max-width: 900px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 4px;
}

.page-desc {
  color: #888;
  font-size: 13px;
  margin: 0;
}

.integration-card {
  margin-bottom: 20px;
}

.integration-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.integration-info {
  flex: 1;
}

.integration-name {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.integration-desc {
  color: #888;
  font-size: 13px;
}

.config-form {
  padding: 16px 0;
}

.form-item {
  margin-bottom: 20px;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  color: #333;
}

.help-icon {
  color: #999;
  cursor: help;
}

.masked-hint {
  font-size: 12px;
  color: #888;
  margin-left: 12px;
}

.webhook-url {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  width: fit-content;
}

.webhook-url code {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #0052d9;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.guide-collapse {
  margin-top: 24px;
}

.guide-content {
  font-size: 14px;
  line-height: 1.8;
}

.guide-content h4 {
  margin: 16px 0 8px;
  color: #333;
}

.guide-content p {
  margin: 8px 0;
  color: #666;
}

.guide-content ul {
  margin: 8px 0;
  padding-left: 20px;
  color: #666;
}

.guide-content a {
  color: #0052d9;
  text-decoration: none;
}

.guide-content a:hover {
  text-decoration: underline;
}
</style>
