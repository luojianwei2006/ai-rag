<template>
  <div class="settings-page">
    <t-card :bordered="false" header="系统设置">

      <!-- 头像设置 -->
      <div class="setting-section">
        <h3 class="section-title">商户头像</h3>
        <p class="section-desc">上传后，客服聊天界面将显示此头像（建议正方形图片）</p>

        <div class="avatar-setting-row">
          <div class="avatar-preview">
            <img v-if="avatarUrl" :src="avatarUrl" class="avatar-img" />
            <div v-else class="avatar-placeholder">
              {{ companyName?.[0] || '客' }}
            </div>
          </div>
          <div class="avatar-actions">
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              style="display:none"
              @change="handleFileChange"
            />
            <t-button theme="primary" variant="outline" size="small" @click="triggerUpload">
              上传头像
            </t-button>
            <t-button
              v-if="avatarUrl"
              theme="danger"
              variant="outline"
              size="small"
              @click="handleDeleteAvatar"
              :loading="deleting"
            >
              删除头像
            </t-button>
            <div class="avatar-hint">支持 JPG/PNG/GIF/WebP，最大 2MB</div>
          </div>
        </div>
      </div>

      <!-- 语言设置 -->
      <div class="setting-section">
        <h3 class="section-title">客服语言设置</h3>
        <p class="section-desc">设置后，客户端聊天界面和 AI 回复将使用对应语言</p>

        <div class="setting-row">
          <div class="setting-label">
            <span class="label-text">聊天界面语言</span>
            <span class="label-hint">影响客户端用户看到的界面语言和 AI 回复语言</span>
          </div>
          <t-select
            :value="chatLanguage"
            :options="languageOptions"
            style="width: 200px"
            @change="handleLanguageChange"
          />
        </div>

        <div class="preview-box" v-if="chatLanguage">
          <div class="preview-title">预览效果</div>
          <div class="preview-content">
            <div class="preview-msg ai">
              <span class="preview-avatar">🤖</span>
              <span class="preview-bubble">{{ previewWelcome }}</span>
            </div>
            <div class="preview-msg customer">
              <span class="preview-bubble-customer">{{ previewGreeting }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- AI 客服开关 -->
      <div class="setting-section">
        <h3 class="section-title">AI 客服</h3>
        <p class="section-desc">关闭后，所有对话将由人工客服处理，AI 不介入</p>
        <div class="setting-row">
          <div class="setting-label">
            <span class="label-text">启用 AI 客服</span>
            <span class="label-hint">关闭后用户将直接与人工客服对话</span>
          </div>
          <t-switch :value="aiEnabled" @change="handleAiToggle" />
        </div>
      </div>

      <!-- 嵌入监控 API Key -->
      <div class="setting-section">
        <h3 class="section-title">嵌入监控 API Key</h3>
        <p class="section-desc">
          将此 Key 提供给第三方平台，对方可通过 iframe 嵌入实时监控页面。<br>
          Key 同时也用于加密客服链接的 uid/nickname 参数。
        </p>

        <div class="embed-key-card">
          <div class="embed-key-header">
            <div class="embed-key-icon">🔑</div>
            <div class="embed-key-info">
              <div class="embed-key-label">当前 API Key</div>
              <div class="embed-key-value" :class="{ masked: !showKey }">
                <span v-if="showKey">{{ embedApiKey }}</span>
                <span v-else>••••••••••••••••••••••••••••••••</span>
              </div>
            </div>
          </div>

          <div class="embed-key-actions">
            <t-button variant="outline" size="small" @click="showKey = !showKey">
              <template #icon><t-icon :name="showKey ? 'browse-off' : 'browse'" /></template>
              {{ showKey ? '隐藏' : '显示' }}
            </t-button>
            <t-button variant="outline" size="small" @click="copyKey">
              <template #icon><t-icon name="file-copy" /></template>
              复制 Key
            </t-button>
            <t-button variant="outline" size="small" theme="warning" @click="regenKey">
              <template #icon><t-icon name="refresh" /></template>
              重新生成
            </t-button>
          </div>

          <div class="embed-url-box" v-if="embedMonitorUrl">
            <div class="embed-url-label">
              <t-icon name="link" style="margin-right:4px" />第三方嵌入地址
            </div>
            <div class="embed-url-row">
              <code class="embed-url-code">{{ embedMonitorUrl }}</code>
              <t-button variant="text" size="small" @click="copyEmbedUrl">
                <template #icon><t-icon name="file-copy" /></template>
                复制
              </t-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 客服链接生成示例 -->
      <div class="setting-section">
        <h3 class="section-title">客服链接生成示例</h3>
        <p class="section-desc">
          使用下方的加密函数对 <code>uid</code> 和 <code>nickname</code> 参数加密后生成客服链接。<br>
          <strong>加密密钥即上方 API Key</strong>，请妥善保管，不要暴露在前端代码中。
        </p>

        <!-- 链接生成区 -->
        <div class="link-gen-section">
          <div class="link-gen-row">
            <t-input v-model="linkUid" placeholder="uid，如：1000" style="width:150px" />
            <t-input v-model="linkNickname" placeholder="昵称，如：guest" style="width:170px" />
          </div>
          <div v-if="generatedLink" class="link-result-row">
            <t-input :value="generatedLink" readonly class="link-result-input" />
            <t-button theme="primary" variant="outline" size="small" @click="copyLink">复制</t-button>
          </div>
          <div v-else class="link-hint">请输入 uid 和昵称，链接将自动生成</div>
        </div>

        <t-divider style="margin: 16px 0 12px" />

        <!-- Tab 切换 -->
        <t-tabs v-model="codeTab" @change="handleCodeTabChange">
          <t-tab-panel value="javascript" label="JavaScript" />
          <t-tab-panel value="python" label="Python" />
          <t-tab-panel value="java" label="Java" />
          <t-tab-panel value="php" label="PHP" />
        </t-tabs>

        <div class="code-block">
          <div class="code-header">
            <span class="code-lang">{{ codeTab }}</span>
            <t-button variant="text" size="small" @click="copyCode">
              <template #icon><t-icon name="file-copy" /></template>
              复制代码
            </t-button>
          </div>
          <pre class="code-content"><code>{{ currentCode }}</code></pre>
        </div>

        <div class="chat-link-preview" v-if="embedApiKey">
          <div class="preview-label">
            <t-icon name="link" style="margin-right:4px" />生成的链接示例
          </div>
          <code class="preview-link">{{ chatLinkExample }}</code>
        </div>
      </div>
    </t-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'

const chatLanguage = ref('zh')
const avatarUrl = ref('')
const companyName = ref('')
const deleting = ref(false)
const fileInput = ref(null)
const aiEnabled = ref(true)
const embedApiKey = ref('')
const showKey = ref(false)
const chatToken = ref('')
const linkUid = ref('1000')
const linkNickname = ref('guest')

const languageOptions = [
  { label: '中文', value: 'zh' },
  { label: 'English', value: 'en' }
]

const previewTexts = {
  zh: {
    welcome: '您好！我是AI客服助手，请问有什么可以帮助您的？',
    greeting: '你好，我需要咨询一下'
  },
  en: {
    welcome: 'Hello! I\'m an AI customer service assistant. How can I help you?',
    greeting: 'Hi, I need some help'
  }
}

const previewWelcome = computed(() => {
  const t = previewTexts[chatLanguage.value]
  return t ? t.welcome : ''
})
const previewGreeting = computed(() => {
  const t = previewTexts[chatLanguage.value]
  return t ? t.greeting : ''
})

const embedMonitorUrl = computed(() => {
  if (!embedApiKey.value) return ''
  return `${window.location.origin}/embed/monitor?api_key=${embedApiKey.value}`
})

// ─── 客服链接生成示例代码 ───
const codeTab = ref('javascript')

const codeExamples = {
  javascript: [
    '// 客服链接生成（JavaScript）',
    '// 加密密钥 = 商户的 embed_api_key',
    'const CRYPTO_KEY = "{{API_KEY}}";',
    '',
    'function xorEncrypt(text, key) {',
    '  const textBytes = new TextEncoder().encode(text);',
    '  const keyBytes = new TextEncoder().encode(key);',
    '  const result = new Uint8Array(textBytes.length);',
    '  for (let i = 0; i < textBytes.length; i++) {',
    '    result[i] = textBytes[i] ^ keyBytes[i % keyBytes.length];',
    '  }',
    '  return result;',
    '}',
    '',
    'function base64UrlEncode(bytes) {',
    '  let binary = "";',
    '  bytes.forEach(b => binary += String.fromCharCode(b));',
    '  const base64 = btoa(binary);',
    '  return base64.replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");',
    '}',
    '',
    'function generateChatLink(uid, nickname, chatToken, origin) {',
    '  const raw = "uid=" + uid + "&nickname=" + nickname;',
    '  const encrypted = xorEncrypt(raw, CRYPTO_KEY);',
    '  const p = base64UrlEncode(encrypted);',
    '  return origin + "/chat/" + chatToken + "?p=" + encodeURIComponent(p);',
    '}',
    '',
    '// 使用示例',
    'const chatLink = generateChatLink("1000", "guest", "YOUR_TOKEN", location.origin);',
    'console.log(chatLink);',
  ].join('\n'),

  python: [
    '# 客服链接生成（Python）',
    'import base64',
    '',
    '# 加密密钥 = 商户的 embed_api_key',
    'CRYPTO_KEY = "{{API_KEY}}"',
    '',
    'def xor_process(data_bytes, key):',
    '    key_bytes = key.encode("utf-8")',
    '    return bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes)])',
    '',
    'def xor_encrypt(text, key):',
    '    text_bytes = text.encode("utf-8")',
    '    encrypted = xor_process(text_bytes, key)',
    '    return base64.urlsafe_b64encode(encrypted).rstrip(b"=").decode("ascii")',
    '',
    'def generate_chat_link(chat_token, uid, nickname, base_url):',
    '    raw = "uid=" + uid + "&nickname=" + nickname',
    '    p = xor_encrypt(raw, CRYPTO_KEY)',
    '    return base_url + "/chat/" + chat_token + "?p=" + p',
    '',
    '# 使用示例',
    'chat_link = generate_chat_link(',
    '    chat_token="YOUR_CHAT_TOKEN",',
    '    uid="1000",',
    '    nickname="guest",',
    '    base_url="https://your-domain.com"',
    ')',
    'print(chat_link)',
  ].join('\n'),

  java: [
    '// 客服链接生成（Java）',
    'import java.util.Base64;',
    'import java.net.URLEncoder;',
    'import java.nio.charset.StandardCharsets;',
    '',
    'public class ChatLinkGenerator {',
    '    // 加密密钥 = 商户的 embed_api_key',
    '    private static final String CRYPTO_KEY = "{{API_KEY}}";',
    '',
    '    private static byte[] xorProcess(byte[] data, String key) {',
    '        byte[] keyBytes = key.getBytes(StandardCharsets.UTF_8);',
    '        byte[] result = new byte[data.length];',
    '        for (int i = 0; i < data.length; i++) {',
    '            result[i] = (byte)(data[i] ^ keyBytes[i % keyBytes.length]);',
    '        }',
    '        return result;',
    '    }',
    '',
    '    private static String base64UrlEncode(byte[] bytes) {',
    '        String base64 = Base64.getEncoder().encodeToString(bytes);',
    '        return base64.replace("+", "-").replace("/", "_").replace("=", "");',
    '    }',
    '',
    '    public static String generateChatLink(String chatToken, String uid, String nickname, String baseUrl) throws Exception {',
    '        String raw = "uid=" + uid + "&nickname=" + nickname;',
    '        byte[] encrypted = xorProcess(raw.getBytes(StandardCharsets.UTF_8), CRYPTO_KEY);',
    '        String p = base64UrlEncode(encrypted);',
    '        return baseUrl + "/chat/" + chatToken + "?p=" + URLEncoder.encode(p, "UTF-8");',
    '    }',
    '',
    '    // 使用示例',
    '    public static void main(String[] args) throws Exception {',
    '        String link = generateChatLink("YOUR_CHAT_TOKEN", "1000", "guest", "https://your-domain.com");',
    '        System.out.println(link);',
    '    }',
    '}',
  ].join('\n'),

  php: [
    '<?php',
    '// 客服链接生成（PHP）',
    '// 加密密钥 = 商户的 embed_api_key',
    "define('CRYPTO_KEY', '{{API_KEY}}');",
    '',
    'function xorProcess($dataBytes, $key) {',
    '    $keyBytes = utf8_encode($key);',
    '    $result = array();',
    '    for ($i = 0; $i < strlen($dataBytes); $i++) {',
    '        $result[] = ord($dataBytes[$i]) ^ ord($keyBytes[$i % strlen($keyBytes)]);',
    '    }',
    '    return $result;',
    '}',
    '',
    'function xorEncrypt($text, $key) {',
    '    $textBytes = utf8_encode($text);',
    '    $encrypted = xorProcess($textBytes, $key);',
    '    $encryptedBytes = array_map("chr", $encrypted);',
    '    $base64 = base64_encode(implode("", $encryptedBytes));',
    "    return rtrim(strtr($base64, '+/', '-_'), '=');",
    '}',
    '',
    'function generateChatLink($chatToken, $uid, $nickname, $baseUrl) {',
    "    $raw = 'uid=' . $uid . '&nickname=' . $nickname;",
    '    $p = xorEncrypt($raw, CRYPTO_KEY);',
    "    return $baseUrl . '/chat/' . $chatToken . '?p=' . urlencode($p);",
    '}',
    '',
    '// 使用示例',
    '$chatLink = generateChatLink("YOUR_CHAT_TOKEN", "1000", "guest", "https://your-domain.com");',
    'echo $chatLink;',
    '?>',
  ].join('\n'),
}

// ─── 客户端加密 & 链接生成 ───
function xorEncrypt(text, key) {
  const encoder = new TextEncoder()
  const textBytes = encoder.encode(text)
  const keyBytes = encoder.encode(key)
  const encrypted = new Uint8Array(textBytes.length)
  for (let i = 0; i < textBytes.length; i++) {
    encrypted[i] = textBytes[i] ^ keyBytes[i % keyBytes.length]
  }
  let binary = ''
  for (let i = 0; i < encrypted.length; i++) {
    binary += String.fromCharCode(encrypted[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

const generatedLink = computed(() => {
  if (!linkUid.value || !linkNickname.value || !chatToken.value || !embedApiKey.value) return ''
  const raw = 'uid=' + linkUid.value + '&nickname=' + linkNickname.value
  const encrypted = xorEncrypt(raw, embedApiKey.value)
  return window.location.origin + '/chat/' + chatToken.value + '?p=' + encodeURIComponent(encrypted)
})

async function copyLink() {
  if (!generatedLink.value) return
  await navigator.clipboard.writeText(generatedLink.value)
  MessagePlugin.success('链接已复制')
}

const currentCode = computed(() => {
  const code = codeExamples[codeTab.value] || codeExamples.javascript
  // 替换 API_KEY 占位符为实际的 embed_api_key
  return embedApiKey.value
    ? code.replace(/\{\{API_KEY\}\}/g, embedApiKey.value)
    : code.replace(/\{\{API_KEY\}\}/g, '(请先生成 API Key)')
})

function handleCodeTabChange(val) {
  codeTab.value = val
}

async function copyCode() {
  if (!currentCode.value) return
  await navigator.clipboard.writeText(currentCode.value)
  MessagePlugin.success('代码已复制')
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleFileChange(e) {
  const file = e.target.files[0]
  if (!file) return

  // 前端校验
  const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) {
    MessagePlugin.error('仅支持 JPG/PNG/GIF/WebP 格式')
    e.target.value = ''
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    MessagePlugin.error('文件大小不能超过 2MB')
    e.target.value = ''
    return
  }

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await tenantApi.uploadAvatar(formData)
    avatarUrl.value = `${import.meta.env.VITE_API_BASE_URL || ''}${res.avatar_url}?t=${Date.now()}`
    MessagePlugin.success('头像上传成功')
  } catch (err) {
    MessagePlugin.error(err.response?.data?.detail || '上传失败')
  }
  e.target.value = ''
}

async function handleDeleteAvatar() {
  deleting.value = true
  try {
    await tenantApi.deleteAvatar()
    avatarUrl.value = ''
    MessagePlugin.success('头像已删除')
  } catch (e) {
    MessagePlugin.error('删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  try {
    const profile = await tenantApi.getProfile()
    if (profile) {
      if (profile.chat_language) {
        chatLanguage.value = profile.chat_language
      }
      if (profile.avatar_url) {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
        avatarUrl.value = `${baseUrl}${profile.avatar_url}?t=${Date.now()}`
      }
      if (profile.ai_enabled !== undefined) {
        aiEnabled.value = profile.ai_enabled
      }
      companyName.value = profile.company_name || ''
      embedApiKey.value = profile.embed_api_key || ''
      chatToken.value = profile.chat_token || ''
    }
  } catch (e) {
    console.error('Failed to load profile:', e)
  }
})

async function copyKey() {
  if (!embedApiKey.value) return
  await navigator.clipboard.writeText(embedApiKey.value)
  MessagePlugin.success('API Key 已复制')
}

async function copyEmbedUrl() {
  if (!embedMonitorUrl.value) return
  await navigator.clipboard.writeText(embedMonitorUrl.value)
  MessagePlugin.success('嵌入地址已复制')
}

function regenKey() {
  const dialog = DialogPlugin.confirm({
    header: '重新生成 API Key',
    body: '重新生成后，旧的 Key 将立即失效，第三方嵌入页面将无法访问。确认继续？',
    confirmBtn: '确认重新生成',
    theme: 'warning',
    onConfirm: async (context) => {
      try {
        const res = await tenantApi.regenerateEmbedKey()
        embedApiKey.value = res.embed_api_key
        MessagePlugin.success('API Key 已重新生成')
        dialog.hide()  // 关闭对话框
        setTimeout(() => window.location.reload(), 500)  // 0.5秒后刷新页面
      } catch (e) {
        MessagePlugin.error('操作失败')
      }
    },
    onClose: (context) => {
      // 用户取消，关闭对话框
      dialog.hide()
    }
  })
}

async function handleLanguageChange(val) {
  try {
    await tenantApi.updateSettings({ chat_language: val })
    chatLanguage.value = val
    MessagePlugin.success(val === 'zh' ? '语言已设置为中文' : 'Language set to English')
  } catch (e) {
    MessagePlugin.error('设置保存失败')
  }
}

async function handleAiToggle(val) {
  try {
    await tenantApi.updateSettings({ ai_enabled: val })
    aiEnabled.value = val
    MessagePlugin.success(val ? 'AI 客服已启用' : 'AI 客服已关闭')
  } catch (e) {
    MessagePlugin.error('设置保存失败')
  }
}
</script>

<style scoped>
.settings-page { max-width: 800px; }

.setting-section { padding: 8px 0; }
.setting-section + .setting-section { border-top: 1px solid #f0f0f0; }
.section-title { font-size: 16px; font-weight: 600; color: #333; margin: 0 0 8px; }
.section-desc { font-size: 13px; color: #999; margin: 0 0 20px; }

/* 头像设置 */
.avatar-setting-row {
  display: flex; align-items: center; gap: 24px; padding: 16px 0;
}
.avatar-preview {
  width: 80px; height: 80px; border-radius: 50%; overflow: hidden;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.avatar-placeholder {
  color: white; font-size: 32px; font-weight: bold;
}
.avatar-actions { display: flex; flex-direction: column; gap: 8px; }
.avatar-hint { font-size: 12px; color: #999; }

/* 语言设置 */
.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 0; border-top: 1px solid #f0f0f0;
}
.setting-label { display: flex; flex-direction: column; gap: 4px; }
.label-text { font-size: 14px; color: #333; font-weight: 500; }
.label-hint { font-size: 12px; color: #999; }

.preview-box {
  margin-top: 20px; background: #f5f7fa; border-radius: 8px;
  padding: 16px; max-width: 400px;
}
.preview-title { font-size: 12px; color: #999; margin-bottom: 12px; }
.preview-content { display: flex; flex-direction: column; gap: 10px; }
.preview-msg { display: flex; align-items: flex-end; gap: 8px; }
.preview-msg.customer { flex-direction: row-reverse; }
.preview-avatar { font-size: 24px; flex-shrink: 0; }
.preview-bubble {
  background: white; padding: 8px 12px; border-radius: 4px 12px 12px 12px;
  font-size: 13px; color: #333; box-shadow: 0 1px 2px rgba(0,0,0,0.06);
  max-width: 280px;
}
.preview-bubble-customer {
  background: linear-gradient(135deg, #667eea, #764ba2); color: white;
  padding: 8px 12px; border-radius: 12px 4px 12px 12px;
  font-size: 13px; max-width: 200px;
}
.embed-url-hint { font-size: 12px; color: #888; margin-top: 8px; }
.embed-url-hint code { background: #f5f7fa; padding: 2px 6px; border-radius: 4px; font-size: 12px; }

/* 嵌入监控 API Key 卡片 */
.embed-key-card {
  background: linear-gradient(135deg, #667eea0d, #764ba20d);
  border: 1px solid #667eea33;
  border-radius: 12px;
  padding: 20px;
}
.embed-key-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.embed-key-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}
.embed-key-info {
  flex: 1;
  min-width: 0;
}
.embed-key-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}
.embed-key-value {
  font-size: 14px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  color: #333;
  background: white;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  word-break: break-all;
  transition: all 0.3s;
}
.embed-key-value.masked {
  color: #999;
  letter-spacing: 2px;
  user-select: none;
}
.embed-key-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.embed-url-box {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px 16px;
}
.embed-url-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
}
.embed-url-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.embed-url-code {
  flex: 1;
  background: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #555;
  word-break: break-all;
  border: 1px solid #e5e7eb;
}

/* 客服链接生成示例代码块 */
.code-block {
  margin-top: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e1e;
}
.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #2d2d2d;
  border-bottom: 1px solid #3d3d3d;
}
.code-lang {
  font-size: 12px;
  color: #89d4cf;
  font-weight: 600;
  text-transform: uppercase;
}
.code-content {
  padding: 12px 16px;
  margin: 0;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.6;
  color: #d4d4d4;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  white-space: pre;
  max-height: 400px;
  overflow-y: auto;
}
.chat-link-preview {
  margin-top: 12px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
}
.preview-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
}
.preview-link {
  display: block;
  font-size: 12px;
  color: #555;
  word-break: break-all;
  background: white;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
}

/* 链接生成区 */
.link-gen-section {
  margin: 16px 0;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}
.link-gen-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.link-gen-row .t-input {
  flex: 1;
}
.link-result-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.link-result-input {
  flex: 1;
}
.link-hint {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}
</style>
