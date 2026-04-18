<template>
  <t-card title="知识库问答测试" :bordered="false">
    <t-row :gutter="16">
      <t-col :span="8">
        <t-form-item label="选择知识库">
          <t-select v-model="selectedKb" placeholder="请选择知识库" style="width:100%">
            <t-option v-for="kb in readyKbs" :key="kb.id" :value="kb.id" :label="kb.name" />
          </t-select>
        </t-form-item>
      </t-col>
    </t-row>

    <div class="qa-container" ref="qaContainer">
      <div v-if="qaHistory.length === 0" class="empty-state">
        <div style="font-size:48px">🤖</div>
        <div>选择知识库后输入问题开始测试</div>
      </div>
      <div v-for="(item, i) in qaHistory" :key="i" class="qa-item">
        <div class="qa-question">
          <span class="qa-role">❓ 问题</span>
          <div class="qa-content question">{{ item.question }}</div>
        </div>
        <div class="qa-answer">
          <span class="qa-role">🤖 AI回答</span>
          <div class="qa-content answer">{{ item.answer }}</div>
          <div class="qa-meta">模型: {{ item.model }} | 匹配片段: {{ item.relevant_chunks }}</div>
        </div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        v-model="question"
        placeholder="输入问题，按Enter发送（Shift+Enter换行）"
        rows="2"
        class="qa-textarea"
        @keydown.enter.prevent="handleAsk"
      ></textarea>
      <t-button theme="primary" :loading="loading" @click="handleAsk" style="margin-top:8px;width:100%">
        发送问题
      </t-button>
    </div>
  </t-card>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { knowledgeApi } from '@/api'

const route = useRoute()
const kbList = ref([])
const selectedKb = ref(null)
const question = ref('')
const qaHistory = ref([])
const loading = ref(false)
const qaContainer = ref(null)

const readyKbs = computed(() => kbList.value.filter(kb => kb.status === 'ready'))

onMounted(async () => {
  try {
    kbList.value = await knowledgeApi.list()
    if (route.query.kb) {
      selectedKb.value = parseInt(route.query.kb)
    }
  } catch (e) {}
})

async function handleAsk() {
  if (!selectedKb.value) return MessagePlugin.warning('请先选择知识库')
  if (!question.value.trim()) return

  const q = question.value.trim()
  question.value = ''
  loading.value = true

  try {
    const res = await knowledgeApi.qaTest({ kb_id: Number(selectedKb.value), question: q })
    qaHistory.value.push(res)
    await nextTick()
    qaContainer.value?.scrollTo({ top: qaContainer.value.scrollHeight, behavior: 'smooth' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.qa-container {
  min-height: 300px; max-height: 500px; overflow-y: auto;
  border: 1px solid #f0f0f0; border-radius: 10px; padding: 16px; margin: 16px 0;
  background: #fafafa;
}
.empty-state { text-align: center; padding: 60px 0; color: #aaa; }
.qa-item { margin-bottom: 20px; }
.qa-question, .qa-answer { margin-bottom: 8px; }
.qa-role { font-size: 12px; color: #888; font-weight: 500; margin-bottom: 4px; display: block; }
.qa-content { padding: 12px 16px; border-radius: 10px; font-size: 14px; line-height: 1.6; }
.question { background: #e8f0fe; color: #333; }
.answer { background: white; border: 1px solid #e5e7eb; color: #333; white-space: pre-wrap; }
.qa-meta { font-size: 11px; color: #aaa; margin-top: 4px; text-align: right; }
.input-area { margin-top: 16px; }
.qa-textarea {
  width: 100%;
  min-height: 50px;
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
.qa-textarea:focus {
  border-color: #667eea;
}
</style>
