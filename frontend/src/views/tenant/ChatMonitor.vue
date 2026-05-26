<template>
  <div class="monitor-layout">
    <!-- 左侧会话列表 -->
    <div class="session-list">
      <div class="list-header">
        <span>会话列表</span>
        <t-tag theme="primary" size="small">{{ onlineSessions.length }} 在线</t-tag>
      </div>
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="session-item"
          :class="{ active: selectedSession?.session_id === s.session_id, online: s.online, human: s.is_human_service, taken: s.taken_over }"
          @click="selectSession(s)"
        >
          <div class="session-avatar">{{ (s.customer_name && s.customer_name !== '访客' ? s.customer_name : (s.uid || '访'))[0] }}</div>
          <div class="session-info">
            <div class="session-name">
              <template v-if="s.uid">
                <span class="session-uid">{{ s.uid }}</span>
                <span v-if="s.customer_name && s.customer_name !== '访客'" class="session-nickname">{{ s.customer_name }}</span>
              </template>
              <template v-else>
                {{ s.customer_name || '访客' }}
              </template>
              <t-tag v-if="s.is_human_service" size="small" theme="warning" style="margin-left:4px">人工</t-tag>
              <t-tag v-if="s.taken_over" size="small" theme="danger" style="margin-left:4px">已接管</t-tag>
            </div>
            <div class="session-msg">{{ s.last_message || '暂无消息' }}</div>
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
      <div v-if="sessions.length === 0" class="no-sessions">暂无会话</div>
    </div>

    <!-- 右侧聊天内容 -->
    <div class="chat-panel">
      <div v-if="!selectedSession" class="no-selected">
        <div style="font-size:48px">💬</div>
        <div>选择一个会话查看聊天内容</div>
      </div>
      <template v-else>
        <div class="chat-header">
          <span>{{ selectedSession.customer_name || '访客' }}</span>
          <t-tag :theme="selectedSession.online ? 'success' : 'default'" size="small">
            {{ selectedSession.online ? '在线' : '离线' }}
          </t-tag>
        </div>

        <div class="chat-messages" ref="messageContainer">
          <div v-for="m in messages" :key="m.id" class="message-row" :class="m.role">
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
            发送人工回复
          </t-button>
        </div>
        <div v-else-if="selectedSession.taken_over" class="reply-area taken-notice">
          ⚠️ 该会话已被嵌入监控端接管，无法在此回复
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { chatApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
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
    return '输入人工回复内容（飞书用户）...'
  }
  if (isWeComSession.value) {
    return '输入人工回复内容（企业微信用户）...'
  }
  return '输入人工回复内容（仅在人工接管后发送）...'
})

// 是否可以发送回复
const canSendReply = computed(() => {
  if (!selectedSession.value) return false
  // 第三方平台用户（飞书/企业微信）可以随时回复
  if (isThirdPartySession.value) return true
  // 网页用户需要在线
  return selectedSession.value.online
})

function roleLabel(role) {
  return { customer: '客户', ai: 'AI助手', human_agent: '人工客服', system: '系统' }[role] || role
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
  return new Date(t).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
function copySessionLink(session) {
  const uid = session.uid || ''
  if (!uid) {
    MessagePlugin.warning('该会话没有 uid')
    return
  }
  navigator.clipboard.writeText(uid).then(() => {
    MessagePlugin.success('uid 已复制')
  }).catch(() => {
    MessagePlugin.error('复制失败，请手动复制')
  })
}

async function loadSessions() {
  try {
    sessions.value = await chatApi.getSessions()
  } catch (e) {}
}

async function selectSession(session) {
  // 如果会话已被嵌入监控端接管，阻止进入并提示
  if (session.taken_over) {
    MessagePlugin.warning('该会话已被嵌入监控端接管，请在嵌入监控页面处理')
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
  replying.value = true
  try {
    await chatApi.humanReply({
      session_id: selectedSession.value.session_id,
      content: replyContent.value.trim()
    })
    messages.value.push({ role: 'human_agent', content: replyContent.value, created_at: new Date().toISOString() })
    replyContent.value = ''
    await nextTick()
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
    console.log('[ChatMonitor] WebSocket 已连接')
  }

  ws.onmessage = (e) => {
    // 处理心跳包
    if (e.data === 'ping' || e.data === 'pong') {
      console.log('[ChatMonitor] 心跳:', e.data)
      return
    }
    try {
      const data = JSON.parse(e.data)
      console.log('[ChatMonitor] 解析消息:', data.type, data)

      if (data.type === 'new_session') {
        loadSessions()
        MessagePlugin.info(`新用户开始咨询`)
      } else if (data.type === 'message' || data.type === 'human_requested') {
        // 更新会话列表（使用新对象触发响应式更新）
        const idx = sessions.value.findIndex(s => s.session_id === data.session_id)
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
          if (data.type === 'human_requested') {
            MessagePlugin.warning(`会话 ${data.session_id?.substring(0, 8)} 请求人工服务`)
          }
        } else {
          // 列表中还没有这个会话，重新加载
          loadSessions()
        }
        // 如果当前查看的会话有新消息
        if (selectedSession.value?.session_id === data.session_id) {
          if (data.role && data.content) {
            const newMsg = {
              id: Date.now(),
              role: data.role,
              msg_type: data.msg_type || 'text',
              content: data.content,
              created_at: data.timestamp
            }
            console.log('[ChatMonitor] ✅ 推送消息到界面:', newMsg.role, newMsg.content?.substring(0, 50))
            messages.value.push(newMsg)
            nextTick(() => {
              messageContainer.value?.scrollTo({ top: messageContainer.value.scrollHeight, behavior: 'smooth' })
            })
          }
        } else {
          console.log('[ChatMonitor] ⏭️ 消息不属于当前会话: selected=', selectedSession.value?.session_id?.substring(0,8), 'received=', data.session_id?.substring(0,8))
        }
      } else if (data.type === 'session_closed') {
        const idx = sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          sessions.value[idx] = { ...sessions.value[idx], online: false }
        }
      } else if (data.type === 'session_online') {
        const idx = sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          sessions.value[idx] = { ...sessions.value[idx], online: true }
        }
      } else if (data.type === 'taken_over' || data.type === 'released') {
        const idx = sessions.value.findIndex(s => s.session_id === data.session_id)
        if (idx >= 0) {
          sessions.value[idx] = {
            ...sessions.value[idx],
            taken_over: data.type === 'taken_over',
            is_human_service: data.type === 'taken_over' ? true : sessions.value[idx].is_human_service
          }
        }
      }
    } catch (err) {
      console.error('[ChatMonitor] 消息解析失败:', err)
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
