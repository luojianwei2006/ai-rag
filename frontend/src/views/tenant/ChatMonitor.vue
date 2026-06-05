<template>
  <div class="monitor-layout">
    <!-- 左侧会话列表 -->
    <div class="session-list">
      <div class="list-header">
        <t-tag theme="primary" size="small">{{ onlineSessions.length }} {{ t('online') }}</t-tag>
      </div>
        <div
          v-for="s of sessions"
          :key="s.session_id || s"
          class="session-item"
          :class="{ active: selectedSession?.session_id === s.session_id, online: s.online, human: s.is_human_service, taken: s.taken_over }"
          @click="selectSession(s)"
        >
          <div class="session-avatar">{{ (s.customer_name && s.customer_name !== t('guest') ? s.customer_name : (s.uid || t('guest')[0])) }}</div>
          <div class="session-info">
            <div class="session-name">
              <template v-if="s.uid">
                <span class="session-uid">{{ s.uid }}</span>
                <span v-if="s.customer_name && s.customer_name !== t('guest')" class="session-nickname">{{ s.customer_name }}</span>
              </template>
              <template v-else>
                {{ s.customer_name || t('guest') }}
              </template>
              <t-tag v-if="s.is_human_service" size="small" theme="warning" style="margin-left:4px">{{ t('human_tag') }}</t-tag>
              <t-tag v-if="s.taken_over" size="small" theme="danger" style="margin-left:4px">{{ t('taken_tag') }}</t-tag>
            </div>
            <div class="session-msg">{{ s.last_message || t('no_message') }}</div>
          </div>
          <div class="session-actions">
            <t-tooltip content="复制 uid">
              <span class="copy-btn" @click.stop="copySessionLink(s)">
                <t-icon name="file-copy" />
              </span>
            </t-tooltip>
          </div>
          <div class="session-status" :class="s.online ? 'online' : 'offline'"></div>
        </div>
      <div v-if="sessions.length === 0" class="no-sessions">{{ t('no_session') }}</div>
    </div>

    <!-- 右侧聊天内容 -->
    <div class="chat-panel">
        <div v-if="!selectedSession" class="no-selected">
          <div style="font-size:48px">💬</div>
          <div>{{ t('select_session') }}</div>
        </div>
      <template v-else>
        <div class="chat-header">
          <span>{{ selectedSession.customer_name || t('guest') }}</span>
          <t-tag :theme="selectedSession.online ? 'success' : 'default'" size="small">
            {{ selectedSession.online ? t('online') : t('offline') }}
          </t-tag>
        </div>

        <div class="chat-messages" ref="messageContainer">
          <div v-for="m of messages" :key="m.id || Date.now()" class="message-row" :class="m.role">
            <div class="message-bubble">
              <div class="message-role">{{ roleLabel(m.role) }}</div>
              <img v-if="m.msg_type === 'image'" :src="imgUrl(m.content)" class="message-image" @click="previewImage(imgUrl(m.content))" />
              <div v-else class="message-content">{{ m.content }}</div>
              <div class="message-time">{{ formatTime(m.created_at) }}</div>
            </div>
          </div>
        </div>

        <!-- 人工回复区域：非托管状态显示输入框 -->
        <div v-if="selectedSession && !selectedSession.taken_over" class="reply-area">
          <textarea
            v-model="replyContent"
            :placeholder="replyPlaceholder"
            rows="2"
            class="reply-textarea"
            @keydown.enter.prevent="sendHumanReply"
          ></textarea>
          <t-button
            theme="primary"
            :loading="replying"
            :disabled="!canSendReply || !replyContent.trim()"
            @click="sendHumanReply"
            style="margin-top:8px"
          >
            {{ t('send_button') }}
          </t-button>
        </div>
        <div v-else-if="selectedSession.taken_over" class="reply-area taken-notice">
          {{ t('taken_notice') }}
        </div>
      </template>
        </div>
    </div>
  </template>

  <script>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { chatApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const i18nMessages = {
  zh: {
    taken_notice: '⚠️ 该会话已被嵌入监控端接管，无法在此回复',
    reply_placeholder: '输入人工回复内容，Enter 发送...',
    reply_placeholder_feishu: '输入人工回复内容（飞书用户）...',
    reply_placeholder_wecom: '输入人工回复内容（企业微信用户）...',
    role_customer: '客户',
    role_ai: 'AI助手',
    role_human: '人工客服',
    role_system: '系统',
    send_button: '发送人工回复',
    taken_tag: '已接管',
    human_tag: '人工',
    online: '在线',
    offline: '离线',
    no_session: '暂无会话',
    no_message: '暂无消息',
    select_session: '选择一个会话查看聊天内容',
    guest: '访客',
    no_uid: '该会话没有 uid',
    uid_copied: 'uid 已复制',
    copy_failed: '复制失败，请手动复制',
    taken_warning: '该会话已被嵌入监控端接管，请在嵌入监控页面处理',
    new_session: '新用户开始咨询',
    human_request: '请求人工服务',
  },
  en: {
    taken_notice: '⚠️ This session has been taken over by the embed monitor, cannot reply here',
    reply_placeholder: 'Type your reply, press Enter to send...',
    reply_placeholder_feishu: 'Type your reply (Feishu user)...',
    reply_placeholder_wecom: 'Type your reply (WeCom user)...',
    role_customer: 'Customer',
    role_ai: 'AI Assistant',
    role_human: 'Human Agent',
    role_system: 'System',
    send_button: 'Send Reply',
    taken_tag: 'Taken Over',
    human_tag: 'Human',
    online: 'Online',
    offline: 'Offline',
    no_session: 'No sessions',
    no_message: 'No messages',
    select_session: 'Select a session to view messages',
    guest: 'Guest',
    no_uid: 'This session has no uid',
    uid_copied: 'uid copied',
    copy_failed: 'Copy failed, please copy manually',
    taken_warning: 'This session has been taken over by the embed monitor, please handle it on the embed monitor page',
    new_session: 'New user started consultation',
    human_request: 'requested human service',
  },
}

const auth = useAuthStore()
const lang = auth.user?.chat_language || 'zh'
const t = (key) => i18nMessages[lang]?.[key] || i18nMessages['zh'][key]

const sessions = ref([])
const selectedSession = ref(null)
const messages = ref([])
const replyContent = ref('')
const replying = ref(false)
const messageContainer = ref(null)
let ws = null
let refreshTimer = null

const onlineSessions = computed(() => sessions.value.filter(s => s.online))

// 判断是否为飞书会话
const isFeishuSession = computed(() => {
  if (!selectedSession.value) return false
  return selectedSession.value.session_id?.startsWith('feishu_') || 
         selectedSession.value.customer_name?.startsWith('feishu:')
})

// 判断是否为企业微信会话
const isWeComSession = computed(() => {
  if (!selectedSession.value) return false
  return selectedSession.value.session_id?.startsWith('wecom_') || 
         selectedSession.value.customer_name?.startsWith('wecom:')
})

// 是否为第三方平台会话（飞书/企业微信）
const isThirdPartySession = computed(() => {
  return isFeishuSession.value || isWeComSession.value
})

// 回复框占位符
const replyPlaceholder = computed(() => {
  if (isFeishuSession.value) {
    return t('reply_placeholder_feishu')
  }
  if (isWeComSession.value) {
    return t('reply_placeholder_wecom')
  }
  return t('reply_placeholder')
})

// 是否可以发送回复
const canSendReply = computed(() => {
  if (!selectedSession.value) return false
  // 被托管的不允许回复
  if (selectedSession.value.taken_over) return false
  return true
})

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
  const locale = lang === 'en' ? 'en-US' : 'zh-CN'
  return new Date(t).toLocaleString(locale, { hour: '2-digit', minute: '2-digit' })
}
function copySessionLink(session) {
  const uid = session.uid || ''
  if (!uid) {
    MessagePlugin.warning(t('no_uid'))
    return
  }
  navigator.clipboard.writeText(uid).then(() => {
    MessagePlugin.success(t('uid_copied'))
  }).catch(() => {
    MessagePlugin.error(t('copy_failed'))
  })
}

async function loadSessions() {
  try {
    const data = await chatApi.getSessions()
    const arr = Array.isArray(data) ? data : []
    console.log('[ChatMonitor] loadSessions 返回', arr.length, '条')
    sessions.value = arr
    // 同步 selectedSession 引用，避免 10 秒刷新后引用 stale
    if (selectedSession.value) {
      const found = arr.find(s => s && s.session_id === selectedSession.value.session_id)
      if (found) {
        selectedSession.value = found
      }
    }
  } catch (e) {
    console.error('[ChatMonitor] loadSessions 失败:', e)
    sessions.value = []
  }
}

async function selectSession(session) {
  // 如果会话已被嵌入监控端接管，阻止进入并提示
  if (session.taken_over) {
    MessagePlugin.warning(t('taken_warning'))
    return
  }

  selectedSession.value = session
  try {
    messages.value = await chatApi.getMessages(session.session_id)
    await nextTick()
    messageContainer.value?.scrollTo({ top: messageContainer.value.scrollHeight, behavior: 'smooth' })
  } catch (e) {}
}

async function sendHumanReply() {
  if (!replyContent.value.trim()) return
  const content = replyContent.value.trim()
  replying.value = true
  console.log('[ChatMonitor] 发送人工回复:', content.substring(0, 50), 'session=', selectedSession.value?.session_id?.substring(0,8))
  try {
    await chatApi.humanReply({
      session_id: selectedSession.value.session_id,
      content: content
    })
    // 本地先推送，不依赖 WebSocket 广播回传
    const newMsg = {
      id: Date.now(),
      role: 'human_agent',
      msg_type: 'text',
      content: content,
      created_at: new Date().toISOString()
    }
    console.log('[ChatMonitor] ✅ 本地推送人工回复:', newMsg)
    messages.value.push(newMsg)
    replyContent.value = ''
    await nextTick()
    console.log('[ChatMonitor] messageContainer.value=', messageContainer.value)
    messageContainer.value?.scrollTo({ top: messageContainer.value.scrollHeight, behavior: 'smooth' })
  } finally {
    replying.value = false
  }
}

function connectWebSocket() {
  const token = localStorage.getItem('token')
  if (!token) {
    console.error('[ChatMonitor] 缺少 token，无法建立 WebSocket 连接')
    return
  }
  // 开发环境使用后端端口 8000，生产环境使用当前 host
  const isDev = import.meta.env.DEV
  const host = isDev ? 'localhost:8000' : location.host
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${host}/ws/monitor/${token}`
  console.log('[ChatMonitor] 连接 WebSocket:', wsUrl)
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    console.log('[ChatMonitor] WebSocket 已连接 ✅')
  }

  ws.onmessage = (e) => {
    // 处理心跳包
    if (e.data === 'ping' || e.data === 'pong') {
      return
    }
    try {
      const data = JSON.parse(e.data)
      console.log('[ChatMonitor WS] 收到消息 type=', data.type, 'session_id=', data.session_id?.substring(0,8), 'role=', data.role, 'content=', data.content?.substring(0,30))

      if (data.type === 'new_session') {
        console.log('[ChatMonitor WS] ➕ 新会话:', data.customer_name, 'uid=', data.uid)
        loadSessions()
        MessagePlugin.info(t('new_session'))
      } else if (data.type === 'message' || data.type === 'human_requested') {
        const matchKey = data.uid || data.session_id
        console.log('[ChatMonitor WS] 📨 消息/请求 matchKey=', matchKey?.substring(0,8), 'selected.uid=', selectedSession.value?.uid, 'selected.sid=', selectedSession.value?.session_id?.substring(0,8))
        // 更新会话列表（使用新对象触发响应式更新）
        // 优先用 uid 匹配（客户刷新后 session_id 会变，uid 不变）
        const idx = data.uid
          ? sessions.value.findIndex(s => s.uid === data.uid)
          : sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          const updated = {
            ...sessions.value[idx],
            last_message: data.content?.substring(0, 50)
          }
          if (data.type === 'human_requested') {
            updated.is_human_service = true
          }
          sessions.value[idx] = updated
          // 移到列表顶部
          sessions.value.splice(idx, 1)
          sessions.value.unshift(updated)
          // 同步更新 selectedSession 引用（避免引用丢失导致消息不刷新）
          const isSelected = data.uid
            ? selectedSession.value?.uid === data.uid
            : selectedSession.value?.session_id === data.session_id
          if (isSelected) {
            console.log('[ChatMonitor WS] 🔄 同步 selectedSession 引用')
            selectedSession.value = updated
          }
          if (data.type === 'human_requested') {
            MessagePlugin.warning(`${matchKey?.substring(0, 8)} ${t('human_request')}`)
          }
        } else {
          // 列表中还没有这个会话，重新加载
          console.log('[ChatMonitor WS] ⚠️ 会话不在列表中，重新加载')
          loadSessions()
        }
        // 如果当前查看的会话有新消息（优先 uid 匹配）
        const isCurrentSession = data.uid
          ? selectedSession.value?.uid === data.uid
          : selectedSession.value?.session_id === data.session_id
        if (isCurrentSession) {
          if (data.role && data.content) {
            const newMsg = {
              id: Date.now(),
              role: data.role,
              msg_type: data.msg_type || 'text',
              content: data.content,
              created_at: data.timestamp
            }
            console.log('[ChatMonitor WS] ✅ 推送消息到界面:', newMsg.role, newMsg.content?.substring(0, 50))
            messages.value.push(newMsg)
            nextTick(() => {
              messageContainer.value?.scrollTo({ top: messageContainer.value.scrollHeight, behavior: 'smooth' })
            })
          } else {
            console.log('[ChatMonitor WS] ⚠️ 消息缺少 role 或 content，不推送')
          }
        } else {
          console.log('[ChatMonitor WS] ⏭️ skip: selected.uid=', selectedSession.value?.uid, 'selected.sid=', selectedSession.value?.session_id?.substring(0,8), 'received.uid=', data.uid, 'received.sid=', data.session_id?.substring(0,8))
        }
      } else if (data.type === 'session_closed') {
        console.log('[ChatMonitor WS] 🔴 会话关闭:', data.uid || data.session_id?.substring(0,8))
        const idx = data.uid
          ? sessions.value.findIndex(s => s.uid === data.uid)
          : sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          sessions.value[idx] = { ...sessions.value[idx], online: false }
        }
      } else if (data.type === 'session_online') {
        console.log('[ChatMonitor WS] 🟢 会话上线:', data.uid || data.session_id?.substring(0,8))
        const idx = data.uid
          ? sessions.value.findIndex(s => s.uid === data.uid)
          : sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          sessions.value[idx] = { ...sessions.value[idx], online: true }
        }
      } else if (data.type === 'taken_over' || data.type === 'released') {
        console.log('[ChatMonitor WS] 🔐 托管状态变化:', data.type, data.uid || data.session_id?.substring(0,8))
        const idx = data.uid
          ? sessions.value.findIndex(s => s.uid === data.uid)
          : sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          sessions.value[idx] = {
            ...sessions.value[idx],
            taken_over: data.type === 'taken_over',
            is_human_service: data.type === 'taken_over' ? true : sessions.value[idx].is_human_service
          }
        }
      } else if (data.type === 'init') {
        // WebSocket 连接成功后的初始数据推送
        console.log('[ChatMonitor WS] ✅ init 收到初始会话列表，共', data.sessions?.length, '条')
        if (Array.isArray(data.sessions)) {
          sessions.value = data.sessions
          // 同步 selectedSession 引用
          if (selectedSession.value) {
            const found = data.sessions.find(s => s.session_id === selectedSession.value.session_id)
            if (found) selectedSession.value = found
          }
        }
      } else {
        console.log('[ChatMonitor WS] ❓ 未知消息类型:', data.type)
      }
    } catch (err) {
      console.error('[ChatMonitor] 消息解析失败:', err, e.data?.substring(0, 200))
    }
  }

  ws.onerror = (e) => {
    console.error('[ChatMonitor] WebSocket 错误:', e)
  }

  ws.onclose = (e) => {
    console.log('[ChatMonitor] WebSocket 已断开:', e.code, e.reason, '3秒后重连...')
    setTimeout(connectWebSocket, 3000)
  }
}

onMounted(() => {
  loadSessions()
  connectWebSocket()
  refreshTimer = setInterval(loadSessions, 10000)
})

onUnmounted(() => {
  ws?.close()
  clearInterval(refreshTimer)
})
</script>

<style scoped>
.monitor-layout { display: flex; gap: 16px; height: calc(100vh - 100px); }
.session-list {
  width: 280px; flex-shrink: 0; background: white; border-radius: 12px;
  overflow-y: auto; border: 1px solid #f0f0f0;
}
.list-header {
  padding: 14px 16px; font-weight: 600; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; background: white;
}
.session-item {
  padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid #f9f9f9; transition: background 0.15s;
}
.session-item:hover { background: #f5f7fa; }
.session-item.active { background: #e8f0fe; }
.session-item.taken { background: #fff1f0; opacity: 0.7; }
.session-item.taken:hover { background: #fff1f0; }
.session-avatar {
  width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #667eea, #764ba2);
  color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0;
}
.session-info { flex: 1; overflow: hidden; }
.session-name { font-size: 14px; font-weight: 500; color: #333; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.session-uid { color: #4facfe; font-weight: 600; }
.session-nickname { color: #333; }
.session-msg { font-size: 12px; color: #888; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.session-actions { display: flex; align-items: center; margin-left: 4px; flex-shrink: 0; }
.copy-btn { padding: 4px; cursor: pointer; display: flex; border-radius: 4px; transition: background 0.15s; }
.copy-btn:hover { background: rgba(0,0,0,0.05); }
.session-actions .t-icon { font-size: 16px; color: #999; transition: color 0.15s; }
.copy-btn:hover .t-icon { color: #4facfe; }
.session-status { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.session-status.online { background: #52c41a; }
.session-status.offline { background: #d1d5db; }
.no-sessions { text-align: center; padding: 40px 0; color: #aaa; font-size: 14px; }

.chat-panel {
  flex: 1; background: white; border-radius: 12px; border: 1px solid #f0f0f0;
  display: flex; flex-direction: column; overflow: hidden;
}
.no-selected { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #aaa; gap: 12px; }
.chat-header {
  padding: 14px 20px; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; gap: 10px; font-weight: 600;
}
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.message-row { display: flex; margin-bottom: 12px; }
.message-row.customer { justify-content: flex-start; }
.message-row.ai, .message-row.system { justify-content: flex-start; }
.message-row.human_agent { justify-content: flex-end; }
.message-bubble { max-width: 75%; }
.message-role { font-size: 11px; color: #888; margin-bottom: 4px; }
.message-content {
  padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.5; white-space: pre-wrap;
}
.customer .message-content { background: #f0f0f0; color: #333; border-radius: 4px 12px 12px 12px; }
.ai .message-content { background: #e8f0fe; color: #333; border-radius: 4px 12px 12px 12px; }
.human_agent .message-content { background: #667eea; color: white; border-radius: 12px 4px 12px 12px; }
.system .message-content { background: #fff7e6; color: #666; font-size: 12px; text-align: center; }
.message-time { font-size: 11px; color: #aaa; margin-top: 3px; text-align: right; }

.reply-area { padding: 12px 16px; border-top: 1px solid #f0f0f0; }
.reply-area.taken-notice {
  text-align: center; color: #999; font-size: 13px; padding: 20px;
}
.reply-textarea {
  width: 100%;
  min-height: 60px;
  max-height: 120px;
  padding: 10px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  font-family: inherit;
}
.reply-textarea:focus {
  border-color: #667eea;
}

/* 图片消息 */
.message-image {
  max-width: 240px; max-height: 300px; border-radius: 8px; cursor: pointer;
  display: block; margin-bottom: 6px; object-fit: cover;
}
.message-image:hover { opacity: 0.85; }
</style>
