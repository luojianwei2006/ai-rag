<template>
  <div class="chat-page">
    <!-- 加载中 -->
    <div v-if="loading" class="loading-screen">
      <t-loading size="large" />
      <p>{{ t('loading') }}</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-screen">
      <div style="font-size:60px">😞</div>
      <h3>{{ t('serviceUnavailable') }}</h3>
      <p>{{ error }}</p>
    </div>

    <!-- 聊天界面 -->
    <div v-else class="chat-wrapper">
      <!-- 顶栏 -->
      <div class="chat-top">
        <div class="company-info">
          <div class="company-avatar">
            <img v-if="avatarUrl" :src="avatarUrl" class="avatar-img" />
            <template v-else>{{ companyName?.[0] || '客' }}</template>
          </div>
          <div>
            <div class="company-name">{{ companyName }}</div>
            <div class="company-status">
              <span class="status-dot"></span>
              {{ isHuman ? t('statusHuman') : t('statusAI') }}
            </div>
          </div>
        </div>
      </div>

      <!-- 消息区 -->
      <div class="messages-area" ref="messagesArea">
        <div v-for="(msg, i) in messages" :key="i" class="msg-row" :class="msg.role">
          <div v-if="msg.role !== 'customer'" class="bot-avatar">
            {{ msg.role === 'human_agent' ? '👤' : '🤖' }}
          </div>
          <div class="msg-bubble">
            <img v-if="msg.msg_type === 'image'" :src="imgUrl(msg.content)" class="msg-image" @click="previewImage(imgUrl(msg.content))" />
            <div v-else class="msg-text">{{ msg.content }}</div>
            <div class="msg-time">{{ msg.time }}</div>
          </div>
          <div v-if="msg.role === 'customer'" class="user-avatar">{{ t('userAvatar') }}</div>
        </div>

        <!-- 打字中 -->
        <div v-if="isTyping" class="msg-row ai">
          <div class="bot-avatar">🤖</div>
          <div class="msg-bubble typing">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="quick-actions">
          <span class="quick-btn" @click="sendQuick(t('quickGreeting'))">{{ t('quickGreetingBtn') }}</span>
          <span class="quick-btn" @click="sendQuick(t('quickTransferHuman'))">{{ t('quickTransferHumanBtn') }}</span>
          <label class="quick-btn upload-btn">
            🖼️ 发截图
            <input type="file" accept="image/*" style="display:none" @change="handleImageUpload" />
          </label>
        </div>
        <div class="input-row">
          <textarea
            v-model="inputText"
            :placeholder="t('inputPlaceholder')"
            @keydown.enter.prevent="handleSend"
            @paste="handlePaste"
            ref="inputRef"
          ></textarea>
          <button class="send-btn" @click="handleSend" :disabled="(!inputText.trim() && !pendingImage) || !connected">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
        <div v-if="pendingImage" class="pending-image">
          <div class="img-wrapper">
            <img :src="pendingImage" />
            <!-- 上传中蒙版 -->
            <div v-if="uploading" class="upload-overlay">
              <t-loading size="small" />
              <span>上传中...</span>
            </div>
            <!-- 上传失败 -->
            <div v-if="uploadError" class="upload-overlay error">
              <span class="error-icon">⚠️</span>
              <span class="error-text">上传失败</span>
              <span class="retry-btn" @click="retryUpload">重试</span>
            </div>
          </div>
          <span class="remove-img" @click="clearPendingImage">✕</span>
        </div>
        <div class="input-hint">{{ t('inputHint') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const chatToken = route.params.chatToken
const chatUid = route.query.uid || ''
const chatNickname = route.query.nickname || ''
const chatParam = route.query.p || ''  // 加密参数 p

// ─── 多语言翻译字典 ───
const i18nMessages = {
  zh: {
    loading: '正在连接客服...',
    serviceUnavailable: '客服服务暂时不可用',
    invalidLink: '该客服链接无效或已失效',
    statusAI: 'AI智能客服在线',
    statusHuman: '人工客服为您服务',
    inputPlaceholder: '输入您的问题...',
    inputHint: 'Enter 发送 · Shift+Enter 换行',
    quickGreetingBtn: '👋 打招呼',
    quickTransferHumanBtn: '👤 转人工',
    quickGreeting: '你好，我需要咨询一下',
    quickTransferHuman: '我需要人工客服',
    reconnecting: '连接已断开，正在重连...',
    userAvatar: '我',
    companyFallback: '在线客服',
  },
  en: {
    loading: 'Connecting to customer service...',
    serviceUnavailable: 'Customer service is temporarily unavailable',
    invalidLink: 'This customer service link is invalid or expired',
    statusAI: 'AI Assistant Online',
    statusHuman: 'Human Agent Serving',
    inputPlaceholder: 'Type your question...',
    inputHint: 'Enter to send · Shift+Enter for new line',
    quickGreetingBtn: '👋 Greet',
    quickTransferHumanBtn: '👤 Human Agent',
    quickGreeting: 'Hi, I need some help',
    quickTransferHuman: 'I need to speak to a human agent',
    reconnecting: 'Connection lost, reconnecting...',
    userAvatar: 'Me',
    companyFallback: 'Customer Service',
  }
}

const loading = ref(true)
const error = ref('')
const companyName = ref('')
const avatarUrl = ref('')
const messages = ref([])
const inputText = ref('')
const isTyping = ref(false)
const isHuman = ref(false)
const connected = ref(false)
const messagesArea = ref(null)
const inputRef = ref(null)
const currentLang = ref('zh')
const pendingImage = ref('')       // 本地预览 base64
const pendingImageUrl = ref('')    // 服务器返回的 URL（发送用）
const uploading = ref(false)       // 上传中
const uploadError = ref(false)     // 上传失败
let lastFile = null                // 最近一次上传的文件（用于重试）
let ws = null

function t(key) {
  return i18nMessages[currentLang.value]?.[key] || i18nMessages.zh[key] || key
}

function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function addMessage(role, content, msgType = 'text') {
  messages.value.push({ role, content, msg_type: msgType, time: now() })
  nextTick(() => {
    messagesArea.value?.scrollTo({ top: messagesArea.value.scrollHeight, behavior: 'smooth' })
  })
}

function handleSend() {
  const hasText = inputText.value.trim()
  const hasImage = !!pendingImage.value && !!pendingImageUrl.value && !uploading.value && !uploadError.value

  if (!connected.value || (!hasText && !hasImage)) return

  if (hasImage) {
    const imgUrl = pendingImageUrl.value
    addMessage('customer', imgUrl, 'image')
    ws.send(JSON.stringify({ content: imgUrl, msg_type: 'image' }))
    clearPendingImage()
    if (!hasText) return
  }

  const text = inputText.value.trim()
  inputText.value = ''
  addMessage('customer', text)
  ws.send(JSON.stringify({ content: text, msg_type: 'text' }))
  isTyping.value = true
}

function sendQuick(text) {
  inputText.value = text
  handleSend()
}

function connectWs() {
  const isDev = import.meta.env.DEV
  const host = isDev ? 'localhost:8000' : location.host
  let wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${host}/ws/chat/${chatToken}`
  // 附加查询参数：优先使用加密参数 p，兼容明文 uid/nickname
  const qs = []
  if (chatParam) {
    qs.push(`p=${encodeURIComponent(chatParam)}`)
  } else {
    if (chatUid) qs.push(`uid=${encodeURIComponent(chatUid)}`)
    if (chatNickname) qs.push(`nickname=${encodeURIComponent(chatNickname)}`)
  }
  if (qs.length) wsUrl += `?${qs.join('&')}`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    connected.value = true
  }

  ws.onmessage = (e) => {
    if (e.data === 'ping' || e.data === 'pong') {
      return
    }
    const data = JSON.parse(e.data)
    isTyping.value = false

    if (data.type === 'message') {
      if (data.role === 'ai' || data.role === 'human_agent' || data.role === 'system') {
        addMessage(data.role, data.content, data.msg_type || 'text')
        if (data.role === 'human_agent') isHuman.value = true
      }
    }
  }

  ws.onclose = () => {
    connected.value = false
    addMessage('system', t('reconnecting'))
    setTimeout(connectWs, 3000)
  }

  ws.onerror = () => {
    connected.value = false
  }
}

async function handleImageUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  await fileToBase64(file)   // 本地预览
  uploadImage(file)          // 上传服务器拿到 URL
  e.target.value = ''
}

async function handlePaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      await fileToBase64(file)
      uploadImage(file)
      return
    }
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    if (file.size > 5 * 1024 * 1024) {
      addMessage('system', '图片不能超过5MB')
      reject(new Error('too large'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      pendingImage.value = reader.result
      resolve()
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function imgUrl(path) {
  if (path.startsWith('http')) return path
  const base = import.meta.env.DEV ? 'http://localhost:8000' : location.origin
  return `${base}${path}`
}

async function uploadImage(file) {
  uploading.value = true
  uploadError.value = false
  lastFile = file
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post(`/api/public/chat/upload-image?chat_token=${chatToken}`, formData)
    pendingImageUrl.value = imgUrl(res.data.url)
  } catch (e) {
    uploadError.value = true
  } finally {
    uploading.value = false
  }
}

async function retryUpload() {
  if (!lastFile) return
  uploadImage(lastFile)
}

function clearPendingImage() {
  pendingImage.value = ''
  pendingImageUrl.value = ''
  uploading.value = false
  uploadError.value = false
  lastFile = null
}

function previewImage(url) {
  window.open(url, '_blank')
}

onMounted(async () => {
  try {
    const res = await axios.get(`/api/public/chat/${chatToken}/info`)
    companyName.value = res.data.company_name || t('companyFallback')
    avatarUrl.value = res.data.avatar_url ? `${location.origin}${res.data.avatar_url}` : ''
    currentLang.value = res.data.language || 'zh'
    loading.value = false
    connectWs()
  } catch (e) {
    error.value = t('invalidLink')
    loading.value = false
  }
})

onUnmounted(() => {
  ws?.close()
})
</script>

<style scoped>
* { box-sizing: border-box; }
.chat-page {
  height: 100vh; display: flex; flex-direction: column;
  background: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.loading-screen, .error-screen {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; color: #666;
}
.chat-wrapper { display: flex; flex-direction: column; height: 100%; max-width: 600px; margin: 0 auto; width: 100%; }

/* 顶栏 */
.chat-top {
  background: linear-gradient(135deg, #667eea, #764ba2);
  padding: 14px 16px; display: flex; align-items: center;
}
.company-info { display: flex; align-items: center; gap: 12px; }
.company-avatar {
  width: 42px; height: 42px; border-radius: 50%; background: rgba(255,255,255,0.25);
  color: white; font-size: 18px; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.company-avatar .avatar-img { width: 100%; height: 100%; object-fit: cover; }
.company-name { color: white; font-size: 16px; font-weight: 600; }
.company-status { color: rgba(255,255,255,0.85); font-size: 12px; display: flex; align-items: center; gap: 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #52c41a; }

/* 消息区 */
.messages-area { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.msg-row { display: flex; align-items: flex-end; gap: 8px; }
.msg-row.customer { flex-direction: row-reverse; }
.bot-avatar, .user-avatar {
  width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.bot-avatar { background: #e8f0fe; }
.user-avatar { background: linear-gradient(135deg, #667eea, #764ba2); color: white; font-size: 12px; font-weight: bold; }
.msg-bubble { max-width: 70%; }
.msg-text {
  padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.5;
  word-break: break-word; white-space: pre-wrap;
}
.ai .msg-text, .system .msg-text { background: white; color: #333; border-radius: 4px 16px 16px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.human_agent .msg-text { background: #f0f9ff; color: #333; border-radius: 4px 16px 16px 16px; border: 1px solid #bae6fd; }
.customer .msg-text { background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 16px 4px 16px 16px; }
.msg-time { font-size: 11px; color: #aaa; margin-top: 4px; padding: 0 4px; }
.customer .msg-time { text-align: right; }

/* 打字动画 */
.typing { background: white; padding: 14px 18px; border-radius: 4px 16px 16px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.typing span {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: #aaa; margin: 0 2px; animation: bounce 1.4s infinite ease-in-out;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%, 80%, 100% { transform: translateY(0); } 40% { transform: translateY(-8px); } }

/* 输入区 */
.input-area { background: white; border-top: 1px solid #f0f0f0; padding: 10px 12px; }
.quick-actions { display: flex; gap: 8px; margin-bottom: 8px; }
.quick-btn {
  padding: 4px 12px; background: #f5f7fa; border-radius: 20px; font-size: 12px;
  cursor: pointer; color: #555; transition: background 0.15s;
}
.quick-btn:hover { background: #e8f0fe; color: #667eea; }
.input-row { display: flex; gap: 8px; align-items: flex-end; }
textarea {
  flex: 1; border: 1px solid #e5e7eb; border-radius: 20px; padding: 10px 16px;
  font-size: 14px; resize: none; outline: none; max-height: 100px; line-height: 1.5;
  font-family: inherit; transition: border-color 0.2s;
}
textarea:focus { border-color: #667eea; }
.send-btn {
  width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #667eea, #764ba2);
  border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: white; flex-shrink: 0; transition: opacity 0.2s;
}
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn svg { width: 18px; height: 18px; }
.input-hint { font-size: 11px; color: #ccc; text-align: center; margin-top: 4px; }

/* 图片消息 */
.msg-image {
  max-width: 240px; max-height: 300px; border-radius: 12px; cursor: pointer;
  display: block; object-fit: cover; transition: opacity 0.2s;
}
.msg-image:hover { opacity: 0.85; }
.customer .msg-image { border: 2px solid rgba(255,255,255,0.3); }

/* 待发送图片预览 */
.pending-image {
  display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px;
}
.img-wrapper {
  position: relative; display: inline-block;
}
.pending-image .img-wrapper img {
  max-width: 120px; max-height: 80px; border-radius: 8px; object-fit: cover;
  border: 1px solid #e5e7eb; display: block;
}
/* 上传蒙版 */
.upload-overlay {
  position: absolute; inset: 0; background: rgba(0,0,0,0.55); border-radius: 8px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; color: white; font-size: 12px;
}
.upload-overlay.error { background: rgba(255,77,79,0.75); }
.error-icon { font-size: 20px; }
.error-text { font-size: 12px; }
.retry-btn {
  font-size: 11px; color: white; text-decoration: underline; cursor: pointer;
  margin-top: 2px;
}
.retry-btn:hover { color: #ffd666; }
.remove-img {
  width: 20px; height: 20px; border-radius: 50%; background: #ff4d4f;
  color: white; font-size: 12px; display: flex; align-items: center;
  justify-content: center; cursor: pointer;
}

/* 上传按钮 */
.upload-btn { cursor: pointer; }
</style>
