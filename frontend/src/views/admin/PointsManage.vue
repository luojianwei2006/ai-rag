<template>
  <div class="points-manage">
    <h2>积分管理</h2>
    
    <!-- 扣费设置 -->
    <div class="section">
      <h3>扣费设置</h3>
      <div class="settings-form">
        <t-form :data="settings" label-width="180px">
          <t-form-item label="知识库添加（点）">
            <t-input-number v-model="settings.knowledge_add_points" :min="0" />
          </t-form-item>
          <t-form-item label="AI客服回答（点）">
            <t-input-number v-model="settings.ai_reply_points" :min="0" />
          </t-form-item>
          <t-form-item label="人工客服回复（点）">
            <t-input-number v-model="settings.human_reply_points" :min="0" />
          </t-form-item>
          <t-form-item>
            <t-button theme="primary" :loading="saving" @click="saveSettings">保存设置</t-button>
          </t-form-item>
        </t-form>
      </div>
    </div>
    
    <!-- 商户积分管理 -->
    <div class="section">
      <h3>商户积分管理</h3>
      <t-table :data="tenants" :columns="columns" row-key="id">
        <template #points_balance="{ row }">
          <span :class="['points-badge', row.points_balance < 100 ? 'points-low' : '']">
            {{ row.points_balance || 0 }} 点
          </span>
        </template>
        <template #operation="{ row }">
          <t-space>
            <t-button theme="primary" size="small" @click="openRecharge(row)">充值</t-button>
            <t-button theme="default" size="small" @click="viewTransactions(row)">交易记录</t-button>
          </t-space>
        </template>
      </t-table>
    </div>
    
    <!-- 充值弹窗 -->
    <t-dialog
      v-model:visible="rechargeVisible"
      header="积分充值"
      :confirm-btn="{ content: '确认充值', loading: recharging }"
      @confirm="handleRecharge"
    >
      <div class="recharge-form">
        <p>商户：{{ selectedTenant?.company_name || selectedTenant?.email }}</p>
        <p>当前积分：<strong>{{ selectedTenant?.points_balance || 0 }} 点</strong></p>
        <t-form-item label="充值点数">
          <t-input-number v-model="rechargePoints" :min="1" :max="100000" />
        </t-form-item>
        <t-form-item label="备注">
          <t-input v-model="rechargeRemark" placeholder="可选" />
        </t-form-item>
      </div>
    </t-dialog>
    
    <!-- 交易记录弹窗 -->
    <t-dialog
      v-model:visible="transactionsVisible"
      header="交易记录"
      width="800px"
      :confirm-btn="null"
      :cancel-btn="{ content: '关闭' }"
    >
      <t-table :data="transactions" :columns="transactionColumns" row-key="id" />
      <div v-if="!transactions.length" class="empty-text">暂无交易记录</div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { adminApi } from '@/api'

const settings = ref({
  knowledge_add_points: 100,
  ai_reply_points: 5,
  human_reply_points: 1
})
const saving = ref(false)

const tenants = ref([])
const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'company_name', title: '商户名称', ellipsis: true },
  { colKey: 'email', title: '邮箱', ellipsis: true },
  { colKey: 'points_balance', title: '积分余额', width: 120 },
  { colKey: 'operation', title: '操作', width: 180 }
]

const rechargeVisible = ref(false)
const recharging = ref(false)
const selectedTenant = ref(null)
const rechargePoints = ref(100)
const rechargeRemark = ref('')

const transactionsVisible = ref(false)
const transactions = ref([])
const transactionColumns = [
  { colKey: 'created_at', title: '时间', width: 160 },
  { colKey: 'transaction_type', title: '类型', width: 100 },
  { 
    colKey: 'points', 
    title: '点数', 
    width: 80,
    cell: (h, { row }) => {
      const color = row.points > 0 ? '#00a870' : '#e34d59'
      return h('span', { style: { color, fontWeight: 'bold' } }, row.points > 0 ? `+${row.points}` : row.points)
    }
  },
  { colKey: 'description', title: '说明', ellipsis: true },
  { colKey: 'balance_after', title: '余额', width: 80 }
]

async function loadSettings() {
  try {
    const res = await adminApi.getPointsConfig()
    settings.value = { ...settings.value, ...res }
  } catch (e) {
    console.error('加载设置失败:', e)
  }
}

async function saveSettings() {
  saving.value = true
  try {
    await adminApi.savePointsConfig(settings.value)
    MessagePlugin.success('设置保存成功')
  } catch (e) {
    MessagePlugin.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function loadTenants() {
  try {
    const res = await adminApi.getTenantsPoints()
    // 将商户列表转换为包含积分余额的格式
    tenants.value = (res.tenants || []).map(t => ({
      ...t,
      points_balance: t.points_balance || 0
    }))
  } catch (e) {
    console.error('加载商户积分失败:', e)
  }
}

function openRecharge(tenant) {
  selectedTenant.value = tenant
  rechargePoints.value = 100
  rechargeRemark.value = ''
  rechargeVisible.value = true
}

async function handleRecharge() {
  if (!rechargePoints.value || rechargePoints.value <= 0) {
    return MessagePlugin.warning('请输入有效的充值点数')
  }
  recharging.value = true
  try {
    await adminApi.rechargeTenantPoints(selectedTenant.value.id, {
      points: rechargePoints.value,
      description: rechargeRemark.value || '管理员充值'
    })
    MessagePlugin.success('充值成功')
    rechargeVisible.value = false
    loadTenants()
  } catch (e) {
    MessagePlugin.error('充值失败')
  } finally {
    recharging.value = false
  }
}

async function viewTransactions(tenant) {
  selectedTenant.value = tenant
  transactionsVisible.value = true
  try {
    const res = await adminApi.getTenantPoints(tenant.id)
    transactions.value = res.transactions || []
  } catch (e) {
    console.error('加载交易记录失败:', e)
  }
}

onMounted(() => {
  loadSettings()
  loadTenants()
})
</script>

<style scoped>
.points-manage { padding: 24px; }
.section { margin-bottom: 32px; }
.section h3 { margin-bottom: 16px; color: #333; }
.settings-form { max-width: 400px; background: #f5f5f5; padding: 20px; border-radius: 8px; }
.points-badge { 
  display: inline-block; 
  padding: 4px 12px; 
  background: rgba(0,168,112,0.1); 
  color: #00a870; 
  border-radius: 4px;
  font-weight: bold;
}
.points-badge.points-low { 
  background: rgba(227,77,89,0.1); 
  color: #e34d59; 
}
.recharge-form { padding: 16px 0; }
.recharge-form p { margin-bottom: 12px; }
.empty-text { text-align: center; padding: 40px; color: #999; }
</style>
