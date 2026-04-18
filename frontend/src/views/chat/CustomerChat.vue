<template>
  <div class="chat-page">
    <!-- 加载中 -->
    <div v-if="loading" class="loading-screen">
      <t-loading size="large" />
      <p>正在连接客服...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-screen">
      <div style="font-size:60px">😞</div>
      <h3>客服服务暂时不可用</h3>
      <p>{{ error }}</p>
    </div>

    <!-- 聊天界面 -->
    <div v-else class="chat-wrapper">
      <!-- 顶栏 -->
      <div class="chat-top">
        <div class="company-info">
          <div class="company-avatar">{{ companyName?.[0] || '客' }}</div>
          <div>
            <div class="company-name">{{ companyName }}</div>
            <div class="company-status">
              <span class="status-dot"></span>
              {{ isHuman ? '人工客服为您服务' : 'AI智能客服在线' }}
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
            <div class="msg-text">{{ msg.content }}</div>
            <div class="msg-time">{{ msg.time }}</div>
          </div>
          <div v-if="msg.role === 'customer'" class="user-avatar">我</div>
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
          <span class="quick-btn" @click="sendQuick('你好，我需要咨询一下')">👋 打招呼</span>
          <span class="quick-btn" @click="sendQuick('我需要人工客服')">👤 转人工</span>
        </div>
        <div class="input-row">
          <textarea
            v-model="inputText"
            placeholder="输入您的问题..."
            @keydown.enter.prevent="handleSend"
            ref="inputRef"
          ></textarea>
          <button class="send-btn" @click="handleSend" :disabled="!inputText.trim() || !connected">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
        <div class="input-hint">Enter 发送 · Shift+Enter 换行</div>
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

const loading = ref(true)
const error = ref('')
const companyName = ref('')
const messages = ref([])
const inputText = ref('')
const isTyping = ref(false)
const isHuman = ref(false)
const connected = ref(false)
const messagesArea = ref(null)
const inputRef = ref(null)
let ws = null

function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function addMessage(role, content) {
  messages.value.push({ role, content, time: now() })
  nextTick(() => {
    messagesArea.value?.scrollTo({ top: messagesArea.value.scrollHeight, behavior: 'smooth' })
  })
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text || !connected.value) return
  inputText.value = ''
  addMessage('customer', text)
  ws.send(JSON.stringify({ content: text }))
  isTyping.value = true
}

function sendQuick(text) {
  inputText.value = text
  handleSend()
}

function connectWs() {
  // 开发环境使用后端端口 8000，生产环境使用当前 host
  const isDev = import.meta.env.DEV
  const host = isDev ? 'localhost:8000' : location.host
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${host}/ws/chat/${chatToken}`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    connected.value = true
  }

  ws.onmessage = (e) => {
    // 处理心跳包
    if (e.data === 'ping' || e.data === 'pong') {
      return
    }
    const data = JSON.parse(e.data)
    isTyping.value = false

    if (data.type === 'message') {
      if (data.role === 'ai' || data.role === 'human_agent' || data.role === 'system') {
        addMessage(data.role, data.content)
        if (data.role === 'human_agent') isHuman.value = true
      }
    }
  }

  ws.onclose = () => {
    connected.value = false
    addMessage('system', '连接已断开，正在重连...')
    setTimeout(connectWs, 3000)
  }

  ws.onerror = () => {
    connected.value = false
  }
}

onMounted(async () => {
  try {
    const res = await axios.get(`/api/public/chat/${chatToken}/info`)
    companyName.value = res.data.company_name || '在线客服'
    loading.value = false
    connectWs()
  } catch (e) {
    error.value = '该客服链接无效或已失效'
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
}
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
</style>
