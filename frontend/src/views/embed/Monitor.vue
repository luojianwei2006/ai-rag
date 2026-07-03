<template>
  <div class="embed-monitor">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-overlay">
      <t-loading :text="t('loading')" size="medium" />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-overlay">
      <t-icon name="error-circle" size="48px" />
      <div class="error-text">{{ error }}</div>
    </div>

    <!-- 监控内容：左右布局 -->
    <template v-else>
      <div class="monitor-container">
        <!-- 左侧：会话列表 -->
        <div class="session-panel">
          <div class="panel-title">{{ t('session_list') }} ({{ sessions.length }})</div>
          <div class="session-list">
            <div
              v-for="s of sessions"
              :key="s.session_id"
              class="session-item"
              :class="{
                active: selectedSession?.session_id === s.session_id,
                online: s.online,
                taken: s.taken_over
              }"
              @click="selectSession(s)"
            >
              <div class="session-avatar">{{ getAvatar(s) }}</div>
              <div class="session-info">
                <div class="session-name">
                  <span v-if="s.uid" class="session-uid">{{ s.uid }}</span>
                  <span v-else>{{ s.customer_name || t('guest') }}</span>
                  <t-tag v-if="s.is_human_service" size="small" theme="warning">{{ t('human_tag') }}</t-tag>
                  <t-tag v-if="s.taken_over" size="small" theme="danger">{{ t('taken_tag') }}</t-tag>
                </div>
                <div class="session-msg">{{ s.last_message || t('no_message') }}</div>
              </div>
              <div class="session-meta">
                <div class="session-time" v-if="s.last_message_time">
                  {{ formatTime(s.last_message_time) }}
                </div>
                <div class="online-dot" :class="{ active: s.online }"></div>
              </div>
            </div>
            <div v-if="sessions.length === 0" class="no-sessions">
              {{ t('no_session') }}
            </div>
          </div>
        </div>

        <!-- 右侧：消息面板 -->
        <div v-if="selectedSession" class="message-panel">
          <div class="panel-header">
            <span class="panel-title">
              {{ selectedSession.customer_name || t('guest') }}
              <span v-if="selectedSession.uid" class="uid-tag">({{ selectedSession.uid }})</span>
            </span>
            <div class="header-actions">
              <t-tag :theme="selectedSession.online ? 'success' : 'default'" size="small">
                {{ selectedSession.online ? t('online') : t('offline') }}
              </t-tag>
              <t-button
                v-if="!selectedSession.taken_over"
                size="small"
                theme="primary"
                @click="takeoverSession"
              >
                {{ t('takeover_btn') }}
              </t-button>
              <t-button
                v-else
                size="small"
                theme="default"
                @click="releaseSession"
              >
                {{ t('release_btn') }}
              </t-button>
            </div>
          </div>

          <div class="message-list" ref="messageContainer">
            <div v-for="m of messages" :key="m.id" class="message-item" :class="m.role">
              <div class="msg-role">{{ roleLabel(m.role) }}</div>
              <img v-if="m.msg_type === 'image'" :src="imgUrl(m.content)" class="msg-image" @click="previewImage(imgUrl(m.content))" />
              <div v-else class="msg-content">{{ m.content }}</div>
              <div class="msg-time">{{ formatTime(m.created_at) }}</div>
            </div>
            <div v-if="messages.length === 0" class="no-messages">
              {{ t('no_message') }}
            </div>
          </div>

          <!-- 消息输入 -->
          <div class="message-input">
            <t-input
              v-model="newMessage"
              :placeholder="t('placeholder')"
              @keyup.enter="sendMessage"
              :disabled="!selectedSession.taken_over"
            />
            <t-button
              theme="primary"
              @click="sendMessage"
              :disabled="!newMessage.trim() || !selectedSession.taken_over"
            >
                {{ t('send_btn') }}
              </t-button>
          </div>
        </div>

        <!-- 右侧：未选择会话 -->
        <div v-else class="message-panel empty-panel">
          <div class="empty-hint">
            <t-icon name="chat" size="48px" />
            <div>{{ t('select_session') }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'

const i18nMessages = {
  zh: {
    takeover_success: '已接管会话',
    release_success: '已释放会话',
    takeover_fail: '接管失败',
    release_fail: '释放失败',
    send_fail: '发送失败',
    loading: '正在连接...',
    session_list: '会话列表',
    no_message: '暂无消息',
    no_session: '暂无会话',
    guest: '访客',
    human_tag: '人工',
    taken_tag: '已接管',
    online: '在线',
    offline: '离线',
    takeover_btn: '接管会话',
    release_btn: '释放会话',
    placeholder: '输入回复消息...',
    send_btn: '发送',
    select_session: '请选择左侧会话',
    role_customer: '客户',
    role_ai: 'AI',
    role_human: '人工',
    role_system: '系统',
    load_fail: '加载会话失败',
    api_key_missing: '缺少 api_key 参数',
    ws_fail: 'WebSocket 连接失败',
    new_session: '新用户开始咨询',
    human_request: '有用户请求人工服务',
  },
  en: {
    takeover_success: 'Session taken over',
    release_success: 'Session released',
    takeover_fail: 'Takeover failed',
    release_fail: 'Release failed',
    send_fail: 'Send failed',
    loading: 'Connecting...',
    session_list: 'Sessions',
    no_message: 'No messages',
    no_session: 'No sessions',
    guest: 'Guest',
    human_tag: 'Human',
    taken_tag: 'Taken',
    online: 'Online',
    offline: 'Offline',
    takeover_btn: 'Take Over',
    release_btn: 'Release',
    placeholder: 'Type your message...',
    send_btn: 'Send',
    select_session: 'Select a session',
    role_customer: 'Customer',
    role_ai: 'AI',
    role_human: 'Human',
    role_system: 'System',
    load_fail: 'Failed to load sessions',
    api_key_missing: 'Missing api_key parameter',
    ws_fail: 'WebSocket connection failed',
    new_session: 'New user started consultation',
    human_request: 'User requested human service',
  },
}
const route = useRoute()
const lang = route.query.lang || 'zh'
const t = (key) => i18nMessages[lang]?.[key] || i18nMessages['zh'][key]

const sessions = ref([])
const selectedSession = ref(null)
const messages = ref([])
const loading = ref(true)
const error = ref('')
const messageContainer = ref(null)
const newMessage = ref('')
let ws = null
let pollTimer = null
let embedLastMsgId = 0  // 轮询用：已加载的最后一条消息id

const onlineCount = computed(() => sessions.value.filter(s => s.online).length)
const humanCount = computed(() => sessions.value.filter(s => s.is_human_service).length)

function getAvatar(session) {
  const name = session.customer_name && session.customer_name !== t('guest')
    ? session.customer_name
    : (session.uid || t('guest'))[0]
  return name[0]
}

function roleLabel(role) {
  const map = {
    customer: t('role_customer'),
    ai: t('role_ai'),
    human_agent: t('role_human'),
    system: t('role_system'),
  }
  return map[role] || role
}
function imgUrl(path) {
  const base = import.meta.env.DEV ? 'http://localhost:8000' : location.origin
  return path.startsWith('http') ? path : `${base}${path}`
}
function previewImage(url) {
  window.open(url, '_blank')
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const locale = lang === 'en' ? 'en-US' : 'zh-CN'
  if (isToday) {
    return d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleString(locale, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadSessions() {
  try {
    const apiKey = route.query.api_key
    const res = await fetch(`/api/embed/info?api_key=${apiKey}`)
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || t('load_fail'))
    }
    const data = await res.json()
    sessions.value = data.sessions || []
  } catch (e) {
    console.error('[EmbedMonitor] Failed to load sessions:', e)
    error.value = e.message || t('load_fail')
  }
}

function selectSession(session) {
  selectedSession.value = session
  embedLastMsgId = 0  // 切换会话时重置
  loadMessages(session.session_id)
}

async function loadMessages(sessionId) {
  try {
    const apiKey = route.query.api_key
    const res = await fetch(`/api/embed/messages?api_key=${apiKey}&session_id=${sessionId}`)
    if (res.ok) {
      const data = await res.json()
      messages.value = data.messages || []
      if (messages.value.length > 0) {
        embedLastMsgId = messages.value[messages.value.length - 1].id || 0
      }
      await nextTick()
      scrollToBottom()
    }
  } catch (e) {
    console.error('[EmbedMonitor] 加载消息失败:', e)
  }
}

async function takeoverSession() {
  if (!selectedSession.value) return
  try {
    const apiKey = route.query.api_key
    const res = await fetch(`/api/embed/takeover?api_key=${apiKey}&session_id=${selectedSession.value.session_id}`, {
      method: 'POST'
    })
    if (res.ok) {
      selectedSession.value.taken_over = true
      selectedSession.value.is_human_service = true
      MessagePlugin.success(t('takeover_success'))
    }
  } catch (e) {
    MessagePlugin.error(t('takeover_fail'))
  }
}

async function releaseSession() {
  if (!selectedSession.value) return
  try {
    const apiKey = route.query.api_key
    const res = await fetch(`/api/embed/release?api_key=${apiKey}&session_id=${selectedSession.value.session_id}`, {
      method: 'POST'
    })
    if (res.ok) {
      selectedSession.value.taken_over = false
      MessagePlugin.success(t('release_success'))
    }
  } catch (e) {
    MessagePlugin.error(t('release_fail'))
  }
}

async function sendMessage() {
  if (!newMessage.value.trim() || !selectedSession.value?.taken_over) return

  try {
    const apiKey = route.query.api_key
    const res = await fetch(`/api/embed/send_message?api_key=${apiKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: selectedSession.value.session_id,
        content: newMessage.value
      })
    })

    if (res.ok) {
      // 清空输入框，消息会通过 WebSocket 广播回来
      newMessage.value = ''
    } else {
      const data = await res.json()
      MessagePlugin.error(data.detail || t('send_fail'))
    }
  } catch (e) {
    MessagePlugin.error(t('send_fail'))
    console.error('[EmbedMonitor] 发送消息失败:', e)
  }
}

// 轮询新消息（3秒一次，WebSocket 的兜底方案）
async function pollMessages() {
  if (!selectedSession.value?.session_id) return
  try {
    const apiKey = route.query.api_key
    const res = await fetch(`/api/embed/messages?api_key=${apiKey}&session_id=${selectedSession.value.session_id}`)
    if (res.ok) {
      const data = await res.json()
      const allMsgs = data.messages || []
      // 只追加新消息
      const newMsgs = embedLastMsgId > 0
        ? allMsgs.filter(m => m.id > embedLastMsgId)
        : allMsgs
      if (newMsgs.length > 0) {
        messages.value = [...messages.value, ...newMsgs]
        embedLastMsgId = newMsgs[newMsgs.length - 1].id
        // 判断是否在底部，是才自动滚动
        const el = messageContainer.value
        const isAtBottom = el && (el.scrollHeight - el.scrollTop - el.clientHeight) < 60
        if (isAtBottom) {
          await nextTick()
          scrollToBottom()
        }
      }
    }
  } catch (e) {
    // 轮询失败静默忽略
  }
}

function scrollToBottom() {
  const container = messageContainer.value
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

function connectWebSocket() {
  const apiKey = route.query.api_key
  if (!apiKey) {
    error.value = '缺少 api_key 参数'
    loading.value = false
    return
  }

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const wsUrl = `${protocol}://${location.host}/ws/embed/monitor?api_key=${apiKey}`

  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    loading.value = false
    error.value = ''
    console.log('[EmbedMonitor] WebSocket 已连接')
  }

  ws.onmessage = (e) => {
    if (e.data === 'ping' || e.data === 'pong') {
      console.log('[EmbedMonitor] 心跳:', e.data)
      return
    }
    try {
      const data = JSON.parse(e.data)
      console.log('[EmbedMonitor] 收到消息:', data.type, data)
      handleWebSocketMessage(data)
    } catch (err) {
      console.error('[EmbedMonitor] WebSocket 消息解析失败:', err, e.data)
    }
  }

  ws.onerror = (e) => {
    console.error('[EmbedMonitor] WebSocket 错误:', e)
    error.value = t('ws_fail')
    loading.value = false
  }

  ws.onclose = (e) => {
    console.log('[EmbedMonitor] WebSocket 已断开:', e.code, e.reason, '3秒后重连...')
    setTimeout(connectWebSocket, 3000)
  }
}

function handleWebSocketMessage(data) {
  console.log('[EmbedMonitor] WebSocket message:', data.type, data)

  switch (data.type) {
    case 'init':
      if (data.sessions && data.sessions.length > 0) {
        sessions.value = data.sessions
        console.log('[EmbedMonitor] 初始化加载', data.sessions.length, '个会话')
      }
      break

    case 'new_session':
      loadSessions()
      MessagePlugin.info(t('new_session'))
      break

    case 'message':
      updateSessionLastMessage(data.session_id, data.content)
      // 强制更新 selectedSession 引用，确保响应式生效
      const currentSessionId = selectedSession.value?.session_id
      console.log('[EmbedMonitor] message 事件: session_id=', data.session_id, '当前选中=', currentSessionId)
      if (currentSessionId === data.session_id) {
        const newMsg = {
          id: Date.now(),  // 必须有 id，否则 :key="m.id" 渲染异常
          role: data.role,
          msg_type: data.msg_type || 'text',
          content: data.content,
          created_at: data.timestamp
        }
        console.log('[EmbedMonitor] 推送消息到界面:', newMsg)
        messages.value = [...messages.value, newMsg]
        embedLastMsgId = Math.max(embedLastMsgId, newMsg.id || Date.now())
        nextTick(() => {
          scrollToBottom()
        })
      }
      break

    case 'human_requested':
      updateSessionStatus(data.session_id, { is_human_service: true })
      MessagePlugin.warning(t('human_request'))
      break

    case 'session_closed':
      updateSessionStatus(data.session_id, { online: false })
      break

    case 'session_online':
      updateSessionStatus(data.session_id, { online: true })
      break

    case 'taken_over':
      updateSessionStatus(data.session_id, { taken_over: true, is_human_service: true })
      break

    case 'released':
      updateSessionStatus(data.session_id, { taken_over: false })
      break
  }
}

function updateSessionLastMessage(sessionId, lastMessage) {
  const idx = sessions.value.findIndex(s => s.session_id === sessionId)
  if (idx >= 0) {
    const updated = {
      ...sessions.value[idx],
      last_message: lastMessage?.substring(0, 50),
      last_message_time: new Date().toISOString()
    }
    sessions.value[idx] = updated
    // 将该会话移到列表顶部
    sessions.value.splice(idx, 1)
    sessions.value.unshift(updated)
  }
}

function updateSessionStatus(sessionId, updates) {
  const idx = sessions.value.findIndex(s => s.session_id === sessionId)
  if (idx >= 0) {
    sessions.value[idx] = { ...sessions.value[idx], ...updates }
  }
}

onMounted(() => {
  const apiKey = route.query.api_key
  if (!apiKey) {
    error.value = t('api_key_missing')
    loading.value = false
    return
  }

  console.log('[EmbedMonitor] 开始加载...')
  loadSessions().then(() => {
    console.log('[EmbedMonitor] 会话加载完成:', sessions.value.length)
    connectWebSocket()
  }).catch(err => {
    console.error('[EmbedMonitor] 加载失败:', err)
    connectWebSocket()
  })

  // 每3秒轮询兜底（WebSocket 断开时也能兜底）
  pollTimer = setInterval(pollMessages, 3000)
})

onUnmounted(() => {
  if (ws) { ws.close(); ws = null }
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.embed-monitor {
  height: 100vh;
  background: #f5f7fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.loading-overlay,
.error-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 16px;
  color: #666;
}

.error-overlay {
  color: #e34d59;
}

.error-text {
  font-size: 14px;
  text-align: center;
  padding: 0 20px;
}

/* 主容器：左右布局 */
.monitor-container {
  display: flex;
  height: 100vh;
}

/* 左侧会话面板 */
.session-panel {
  width: 320px;
  background: white;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
}

.panel-title {
  padding: 16px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  border-bottom: 1px solid #e5e7eb;
}

.session-list {
  flex: 1;
  overflow-y: auto;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.15s;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.active {
  background: #e8f0fe;
}

.session-item.taken {
  background: #fff3e0;
}

.session-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  overflow: hidden;
}

.session-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.session-uid {
  color: #4facfe;
  font-weight: 600;
}

.session-msg {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin-top: 4px;
}

.session-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.session-time {
  font-size: 11px;
  color: #bbb;
}

.online-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.online-dot.active {
  background: #52c41a;
}

.no-sessions {
  text-align: center;
  padding: 40px 0;
  color: #999;
  font-size: 14px;
}

/* 右侧消息面板 */
.message-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  margin: 8px 8px 8px 0;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.message-panel.empty-panel {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-hint {
  text-align: center;
  color: #999;
  font-size: 14px;
}

.empty-hint div {
  margin-top: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.uid-tag {
  color: #999;
  font-size: 14px;
  font-weight: normal;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message-item {
  margin-bottom: 12px;
}

.message-item.customer {
  text-align: left;
}

.message-item.human_agent {
  text-align: right;
}

.msg-role {
  font-size: 11px;
  color: #999;
  margin-bottom: 4px;
}

.msg-content {
  display: inline-block;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  max-width: 80%;
}

.customer .msg-content {
  background: #f0f0f0;
  color: #333;
}

.human_agent .msg-content {
  background: #667eea;
  color: white;
}

.ai .msg-content {
  background: #e8f0fe;
  color: #333;
}

.msg-time {
  font-size: 10px;
  color: #ccc;
  margin-top: 4px;
}

.no-messages {
  text-align: center;
  padding: 40px 0;
  color: #999;
  font-size: 14px;
}

/* 消息输入 */
.message-input {
  display: flex;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid #e5e7eb;
}

/* 图片消息 */
.msg-image {
  max-width: 240px; max-height: 300px; border-radius: 8px; cursor: pointer;
  display: block; margin-bottom: 6px; object-fit: cover;
}
.msg-image:hover { opacity: 0.85; }
</style>
