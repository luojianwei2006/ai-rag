<template>
  <div class="import-page">
    <div class="page-header">
      <t-button variant="text" @click="$router.push('/tenant/knowledge')">
        <t-icon name="chevron-left" />返回知识库
      </t-button>
      <h2>从网页导入知识库</h2>
    </div>

    <!-- Step 1: 输入URL -->
    <t-card class="step-card" v-if="step === 'input'">
      <template #header>
        <span class="step-title">📎 Step 1 — 输入网址</span>
      </template>

      <div class="url-form">
        <t-input
          v-model="url"
          placeholder="请输入网页地址，例如：https://example.com"
          size="large"
          clearable
          style="flex:1"
        >
          <template #prefix><t-icon name="link" /></template>
        </t-input>
      </div>

      <div class="crawl-mode">
        <div class="mode-label">爬取范围：</div>
        <t-radio-group v-model="crawlMode">
          <t-radio value="single">
            <div class="mode-item">
              <div class="mode-name">📄 只爬取当前页面</div>
              <div class="mode-desc">仅获取该URL对应的页面内容</div>
            </div>
          </t-radio>
          <t-radio value="site">
            <div class="mode-item">
              <div class="mode-name">🌐 爬取整个网站</div>
              <div class="mode-desc">从该URL出发，爬取同域名下所有网页</div>
            </div>
          </t-radio>
        </t-radio-group>

        <div v-if="crawlMode === 'site'" class="depth-setting">
          <span>爬取深度：</span>
          <t-slider :value="maxDepth" @change="val => maxDepth = val" :min="1" :max="5" :step="1" style="width:200px;display:inline-block;margin:0 12px" />
          <span class="depth-value">{{ maxDepth }} 层</span>
          <t-tag theme="warning" variant="light" size="small" style="margin-left:8px">最多爬取100个页面</t-tag>
        </div>
      </div>

      <div class="action-bar">
        <t-button theme="primary" size="large" :loading="crawling" :disabled="!url" @click="startCrawl">
          <t-icon name="search" />开始爬取
        </t-button>
      </div>
    </t-card>

    <!-- Step 2: 爬取中 -->
    <t-card class="step-card" v-if="step === 'crawling'">
      <template #header>
        <span class="step-title">⏳ 正在爬取...</span>
      </template>
      <div class="crawling-status">
        <t-loading size="large" />
        <div class="crawl-info">
          <div class="crawl-url">{{ url }}</div>
          <div class="crawl-progress">已爬取 <strong>{{ crawlProgress }}</strong> 个页面，发现 <strong>{{ crawlTotal }}</strong> 个链接...</div>
        </div>
      </div>
    </t-card>

    <!-- Step 3: 爬取结果 -->
    <t-card class="step-card" v-if="step === 'result'">
      <template #header>
        <div class="result-header">
          <span class="step-title">✅ Step 2 — 选择要导入的页面</span>
          <div class="result-actions">
            <t-tag theme="success">共 {{ results.length }} 个页面</t-tag>
            <t-button variant="outline" size="small" @click="selectAll">全选</t-button>
            <t-button variant="outline" size="small" @click="selectNone">全不选</t-button>
            <t-button variant="text" size="small" @click="step = 'input'">重新爬取</t-button>
          </div>
        </div>
      </template>

      <div class="result-list">
        <div
          v-for="(item, idx) in results"
          :key="item.url"
          class="result-item"
          :class="{ selected: item.selected }"
        >
          <t-checkbox v-model="item.selected" class="item-checkbox" />
          <div class="item-content" @click="item.selected = !item.selected">
            <div class="item-header">
              <span class="item-title">{{ item.title }}</span>
              <span class="item-length">{{ item.content_length }} 字</span>
            </div>
            <div class="item-url">{{ item.url }}</div>
            <div class="item-preview">{{ item.content_preview }}</div>
          </div>
          <t-button
            theme="danger"
            variant="text"
            size="small"
            class="item-delete"
            @click.stop="results.splice(idx, 1)"
          >
            <t-icon name="delete" />
          </t-button>
        </div>

        <div v-if="results.length === 0" class="empty-result">
          <t-icon name="error-circle" size="40px" />
          <div>未爬取到任何内容，请检查URL是否可访问</div>
          <t-button @click="step = 'input'">重新输入</t-button>
        </div>
      </div>

      <!-- Step 3: 填写名称并导入 -->
      <div class="import-section" v-if="selectedItems.length > 0">
        <t-divider>导入设置</t-divider>
        <div class="import-form">
          <div class="form-row">
            <span class="form-label">知识库名称：</span>
            <t-input v-model="kbName" placeholder="请输入知识库名称" style="width:300px" />
          </div>
          <div class="selected-count">
            已选择 <strong>{{ selectedItems.length }}</strong> 个页面
          </div>
        </div>

        <t-button
          theme="primary"
          size="large"
          :loading="importing"
          :disabled="!kbName"
          @click="startImport"
        >
          <t-icon name="upload" />开始入库
        </t-button>
      </div>
    </t-card>

    <!-- Step 4: 导入进度 -->
    <t-card class="step-card" v-if="step === 'importing'">
      <template #header>
        <span class="step-title">📥 正在导入知识库...</span>
      </template>

      <div class="import-progress">
        <div class="progress-info">
          <div class="kb-name">知识库：{{ kbName }}</div>
          <div class="progress-count">共 {{ importItems.length }} 个页面</div>
        </div>

        <div class="progress-list">
          <div
            v-for="(item, idx) in importItems"
            :key="item.url"
            class="progress-item"
            :class="importProgressMap[idx]"
          >
            <span class="progress-icon">
              <t-icon v-if="importProgressMap[idx] === 'done'" name="check-circle-filled" style="color:#00a870" />
              <t-icon v-else-if="importProgressMap[idx] === 'current'" name="loading" style="color:#0052d9" />
              <t-icon v-else name="time" style="color:#999" />
            </span>
            <span class="progress-title">{{ item.title }}</span>
            <span class="progress-url">{{ item.url }}</span>
          </div>
        </div>

        <div class="progress-bar-wrap">
          <t-progress :percentage="importPercent" :label="importPercent + '%'" />
        </div>

        <div v-if="importDone" class="import-done">
          <t-icon name="check-circle" size="32px" style="color:#00a870" />
          <div>导入完成！知识库已创建</div>
          <t-button theme="primary" @click="$router.push('/tenant/knowledge')">查看知识库</t-button>
        </div>
      </div>
    </t-card>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { knowledgeApi } from '@/api'

// ---- 状态 ----
const step = ref('input')        // input / crawling / result / importing
const url = ref('')
const crawlMode = ref('single')
const maxDepth = ref(3)
const crawling = ref(false)
const importing = ref(false)
const importDone = ref(false)

const results = ref([])          // 爬取结果列表
const crawlProgress = ref(0)
const crawlTotal = ref(0)

const kbName = ref('')
const importItems = ref([])      // 待导入列表
const importProgressMap = ref({}) // {idx: 'pending'|'current'|'done'}
const importPercent = ref(0)

let pollTimer = null

// ---- 计算属性 ----
const selectedItems = computed(() => results.value.filter(r => r.selected))

// ---- 方法 ----
function selectAll() {
  results.value.forEach(r => r.selected = true)
}
function selectNone() {
  results.value.forEach(r => r.selected = false)
}

async function startCrawl() {
  if (!url.value) return
  crawling.value = true
  step.value = 'crawling'
  crawlProgress.value = 0
  crawlTotal.value = 0

  try {
    const res = await knowledgeApi.startCrawl({
      url: url.value,
      mode: crawlMode.value,
      max_depth: maxDepth.value
    })
    const taskId = res.task_id
    // 轮询进度
    pollTimer = setInterval(async () => {
      try {
        const status = await knowledgeApi.getCrawlStatus(taskId)
        crawlProgress.value = status.progress || 0
        crawlTotal.value = status.total || 0

        if (status.status === 'done') {
          clearInterval(pollTimer)
          results.value = (status.results || []).map(r => ({ ...r, selected: true }))
          step.value = 'result'
          crawling.value = false
          // 自动设置知识库名称
          if (!kbName.value && results.value.length > 0) {
            try {
              const domain = new URL(url.value).hostname
              kbName.value = domain
            } catch {}
          }
        } else if (status.status === 'error') {
          clearInterval(pollTimer)
          MessagePlugin.error('爬取失败：' + (status.error || '未知错误'))
          step.value = 'input'
          crawling.value = false
        }
      } catch (e) {}
    }, 1500)

  } catch (e) {
    step.value = 'input'
    crawling.value = false
  }
}

async function startImport() {
  if (!kbName.value || selectedItems.value.length === 0) return
  importing.value = true
  importItems.value = [...selectedItems.value]
  importProgressMap.value = {}
  importItems.value.forEach((_, idx) => {
    importProgressMap.value[idx] = 'pending'
  })
  importPercent.value = 0
  importDone.value = false
  step.value = 'importing'

  try {
    // 模拟逐个勾选进度（实际是一次性提交，后端处理）
    for (let i = 0; i < importItems.value.length; i++) {
      importProgressMap.value[i] = 'current'
      importPercent.value = Math.round((i / importItems.value.length) * 90)
      await new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 100))
      importProgressMap.value[i] = 'done'
    }
    importPercent.value = 95

    // 提交入库
    await knowledgeApi.importFromCrawl({
      kb_name: kbName.value,
      items: importItems.value.map(item => ({
        url: item.url,
        title: item.title,
        content: item.content
      }))
    })

    importPercent.value = 100
    importDone.value = true
    MessagePlugin.success('知识库导入成功！')
  } catch (e) {
    step.value = 'result'
  } finally {
    importing.value = false
  }
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.import-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.step-card {
  margin-bottom: 24px;
}
.step-title {
  font-size: 16px;
  font-weight: 600;
}

/* URL输入 */
.url-form {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

/* 爬取模式 */
.crawl-mode {
  margin-bottom: 24px;
}
.mode-label {
  font-weight: 500;
  margin-bottom: 12px;
  color: #333;
}
.mode-item {
  margin-left: 4px;
}
.mode-name {
  font-weight: 500;
}
.mode-desc {
  font-size: 12px;
  color: #999;
}
:deep(.t-radio) {
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  transition: all .2s;
  width: 100%;
}
:deep(.t-radio.t-is-checked) {
  border-color: #0052d9;
  background: #f0f5ff;
}
.depth-setting {
  display: flex;
  align-items: center;
  margin-top: 12px;
  padding: 12px 16px;
  background: #f5f5f5;
  border-radius: 8px;
}
.depth-value {
  font-weight: 600;
  color: #0052d9;
}

.action-bar {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

/* 爬取中 */
.crawling-status {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 32px;
  justify-content: center;
}
.crawl-info {
  text-align: left;
}
.crawl-url {
  font-size: 14px;
  color: #0052d9;
  margin-bottom: 8px;
}
.crawl-progress {
  color: #666;
}

/* 结果列表 */
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.result-list {
  max-height: 500px;
  overflow-y: auto;
}
.result-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all .2s;
}
.result-item:hover {
  border-color: #0052d9;
  background: #f8faff;
}
.result-item.selected {
  border-color: #0052d9;
  background: #f0f5ff;
}
.item-checkbox {
  margin-top: 2px;
  flex-shrink: 0;
}
.item-content {
  flex: 1;
  min-width: 0;
}
.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.item-title {
  font-weight: 500;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 500px;
}
.item-length {
  font-size: 12px;
  color: #999;
  white-space: nowrap;
  flex-shrink: 0;
}
.item-url {
  font-size: 12px;
  color: #0052d9;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-preview {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.item-delete {
  flex-shrink: 0;
}
.empty-result {
  text-align: center;
  padding: 48px;
  color: #999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

/* 导入设置 */
.import-section {
  margin-top: 24px;
}
.import-form {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.form-label {
  font-weight: 500;
  white-space: nowrap;
}
.selected-count {
  color: #666;
  font-size: 14px;
}

/* 导入进度 */
.import-progress {
  padding: 8px 0;
}
.progress-info {
  margin-bottom: 16px;
}
.kb-name {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}
.progress-count {
  color: #666;
  font-size: 14px;
}
.progress-list {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 16px;
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  padding: 8px;
}
.progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 4px;
  font-size: 13px;
  transition: background .2s;
}
.progress-item.done {
  background: #f0faf5;
}
.progress-item.current {
  background: #f0f5ff;
}
.progress-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}
.progress-title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}
.progress-url {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.progress-bar-wrap {
  margin: 16px 0;
}
.import-done {
  text-align: center;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #00a870;
  font-size: 16px;
}
</style>
