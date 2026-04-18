<template>
  <div class="history-layout">
    <t-card title="聊天历史记录" :bordered="false">
      <t-row :gutter="16" style="margin-bottom: 16px;">
        <t-col :span="6">
          <t-select v-model="filterStatus" placeholder="筛选状态" clearable @change="loadSessions">
            <t-option value="" label="全部状态" />
            <t-option value="active" label="进行中" />
            <t-option value="human" label="人工服务" />
            <t-option value="closed" label="已结束" />
          </t-select>
        </t-col>
      </t-row>

      <t-table :data="sessions" :columns="columns" row-key="session_id" :loading="loading" stripe>
        <template #status="{ row }">
          <t-tag :theme="statusTheme(row.status)">{{ statusLabel(row.status) }}</t-tag>
        </template>
        <template #online="{ row }">
          <div class="dot" :class="row.online ? 'online' : 'offline'"></div>
        </template>
        <template #actions="{ row }">
          <t-button size="small" variant="outline" @click="viewHistory(row)">查看记录</t-button>
        </template>
      </t-table>
    </t-card>

    <!-- 历史记录详情弹窗 -->
    <t-dialog
      v-model:visible="showDetail"
      :header="'会话记录 - ' + (currentSession?.customer_name || '访客')"
      width="640px"
      :footer="false"
    >
      <div class="history-messages" ref="historyContainer">
        <div v-for="m in detailMessages" :key="m.id" class="message-row" :class="m.role">
          <div class="message-bubble">
            <div class="message-role">{{ roleLabel(m.role) }}</div>
            <div class="message-content">{{ m.content }}</div>
            <div class="message-time">{{ new Date(m.created_at).toLocaleString('zh-CN') }}</div>
          </div>
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { chatApi } from '@/api'

const loading = ref(false)
const sessions = ref([])
const filterStatus = ref('')
const showDetail = ref(false)
const currentSession = ref(null)
const detailMessages = ref([])

const columns = [
  { colKey: 'customer_name', title: '访客' },
  { colKey: 'customer_ip', title: 'IP', width: 130 },
  { colKey: 'status', title: '状态', cell: 'status', width: 100 },
  { colKey: 'online', title: '在线', cell: 'online', width: 70 },
  { colKey: 'created_at', title: '开始时间', width: 160 },
  { colKey: 'actions', title: '操作', cell: 'actions', width: 100 }
]

function statusTheme(s) {
  return { active: 'primary', human: 'warning', closed: 'default' }[s] || 'default'
}
function statusLabel(s) {
  return { active: '进行中', human: '人工服务', closed: '已结束' }[s] || s
}
function roleLabel(r) {
  return { customer: '客户', ai: 'AI', human_agent: '人工客服', system: '系统' }[r] || r
}

async function loadSessions() {
  loading.value = true
  try {
    sessions.value = await chatApi.getSessions()
  } finally {
    loading.value = false
  }
}

async function viewHistory(session) {
  currentSession.value = session
  try {
    detailMessages.value = await chatApi.getMessages(session.session_id)
    showDetail.value = true
  } catch (e) {}
}

onMounted(loadSessions)
</script>

<style scoped>
.dot { width: 8px; height: 8px; border-radius: 50%; margin: 0 auto; }
.dot.online { background: #52c41a; }
.dot.offline { background: #d1d5db; }
.history-messages { max-height: 500px; overflow-y: auto; padding: 8px; }
.message-row { display: flex; margin-bottom: 12px; }
.message-row.human_agent { justify-content: flex-end; }
.message-bubble { max-width: 80%; }
.message-role { font-size: 11px; color: #888; margin-bottom: 3px; }
.message-content { padding: 10px 14px; border-radius: 10px; font-size: 14px; white-space: pre-wrap; }
.customer .message-content { background: #f0f0f0; }
.ai .message-content { background: #e8f0fe; }
.human_agent .message-content { background: #667eea; color: white; }
.message-time { font-size: 11px; color: #aaa; margin-top: 3px; }
</style>
