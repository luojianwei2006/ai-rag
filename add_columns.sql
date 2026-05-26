-- 添加缺失的字段到 t_user_task_record 表

-- 1. 提交截止时间（接取后 N 小时内必须提交）
ALTER TABLE t_user_task_record 
ADD COLUMN accept_deadline DATETIME(6) COMMENT '提交截止时间';

-- 2. AI审核时间（预留）
ALTER TABLE t_user_task_record 
ADD COLUMN ai_checked_at DATETIME(6) COMMENT 'AI审核时间';

-- 3. 人工审核时间
ALTER TABLE t_user_task_record 
ADD COLUMN manual_checked_at DATETIME(6) COMMENT '人工审核时间';

-- 4. 奖励发放时间
ALTER TABLE t_user_task_record 
ADD COLUMN reward_granted_at DATETIME(6) COMMENT '奖励发放时间';

