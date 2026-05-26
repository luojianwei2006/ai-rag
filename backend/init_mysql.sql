-- ==================== 客服管理平台 MySQL 建表脚本 ====================
-- 使用方法：
-- 1. 先创建数据库：CREATE DATABASE IF NOT EXISTS customer_service DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 2. 切换到该数据库：USE customer_service;
-- 3. 执行本脚本：source init_mysql.sql;

-- 如果表已存在则删除（⚠️ 会丢失数据，生产环境请谨慎）
-- DROP TABLE IF EXISTS points_transactions, chat_messages, chat_sessions, xhs_tasks, xhs_materials, xhs_accounts, knowledge_bases, tenants, system_configs, admins;

-- ==================== 1. admins ====================
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_admins_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员表';

-- ==================== 2. system_configs ====================
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(100) NOT NULL UNIQUE,
    value TEXT DEFAULT NULL,
    description VARCHAR(255) DEFAULT NULL,
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_system_configs_key (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表（SMTP、默认API Key、扣费设置等）';

-- ==================== 3. tenants ====================
CREATE TABLE IF NOT EXISTS tenants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    company_name VARCHAR(100) DEFAULT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    chat_token VARCHAR(64) NOT NULL UNIQUE,
    use_system_api_key TINYINT(1) DEFAULT 1,
    custom_api_keys JSON DEFAULT NULL,
    preferred_model VARCHAR(50) DEFAULT 'glm',
    feishu_enabled TINYINT(1) DEFAULT 0,
    feishu_app_id VARCHAR(100) DEFAULT NULL,
    feishu_app_secret VARCHAR(255) DEFAULT NULL,
    feishu_encrypt_key VARCHAR(255) DEFAULT NULL,
    wecom_enabled TINYINT(1) DEFAULT 0,
    wecom_corp_id VARCHAR(100) DEFAULT NULL,
    wecom_agent_id VARCHAR(50) DEFAULT NULL,
    wecom_secret VARCHAR(255) DEFAULT NULL,
    wecom_token VARCHAR(255) DEFAULT NULL,
    wecom_encoding_aes_key VARCHAR(255) DEFAULT NULL,
    points_balance INT DEFAULT 0,
    chat_language VARCHAR(10) DEFAULT 'zh',
    ai_enabled TINYINT(1) DEFAULT 1,
    avatar_url VARCHAR(500) DEFAULT NULL,
    embed_api_key VARCHAR(64) DEFAULT NULL UNIQUE,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_tenants_email (email),
    INDEX idx_tenants_chat_token (chat_token),
    INDEX idx_tenants_embed_api_key (embed_api_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户表';

-- ==================== 4. points_transactions ====================
CREATE TABLE IF NOT EXISTS points_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL,
    transaction_type VARCHAR(50) NOT NULL COMMENT 'knowledge_add, ai_reply, human_reply, recharge',
    points INT NOT NULL COMMENT '正数为充值，负数为消费',
    description VARCHAR(255) DEFAULT NULL,
    related_id VARCHAR(100) DEFAULT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_points_transactions_tenant_id (tenant_id),
    CONSTRAINT fk_points_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='积分消费记录表';

-- ==================== 5. knowledge_bases ====================
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT DEFAULT NULL,
    file_path VARCHAR(500) DEFAULT NULL,
    file_name VARCHAR(255) DEFAULT NULL,
    file_type VARCHAR(20) DEFAULT NULL COMMENT 'excel, word, txt',
    status VARCHAR(20) DEFAULT 'processing' COMMENT 'processing, ready, failed',
    progress INT DEFAULT 0 COMMENT '处理进度 0-100',
    progress_message VARCHAR(100) DEFAULT '等待处理',
    chunk_count INT DEFAULT 0,
    collection_name VARCHAR(100) DEFAULT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_knowledge_bases_tenant_id (tenant_id),
    CONSTRAINT fk_knowledge_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库表';

-- ==================== 6. chat_sessions ====================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    uid VARCHAR(100) DEFAULT NULL,
    customer_name VARCHAR(100) DEFAULT '访客',
    customer_ip VARCHAR(50) DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'active' COMMENT 'active, human, closed',
    is_human_service TINYINT(1) DEFAULT 0,
    online TINYINT(1) DEFAULT 0 COMMENT '用户是否在线',
    taken_over TINYINT(1) DEFAULT 0 COMMENT '是否被嵌入监控端接管',
    last_active DATETIME(6) DEFAULT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_chat_sessions_tenant_id (tenant_id),
    INDEX idx_chat_sessions_session_id (session_id),
    INDEX idx_chat_sessions_uid (uid),
    CONSTRAINT fk_session_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天会话表';

-- ==================== 7. chat_messages ====================
CREATE TABLE IF NOT EXISTS chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL COMMENT 'customer, ai, human_agent',
    msg_type VARCHAR(20) DEFAULT 'text' COMMENT 'text, image',
    content TEXT NOT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_chat_messages_session_id (session_id),
    CONSTRAINT fk_message_session FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天消息表';

-- ==================== 8. xhs_accounts ====================
CREATE TABLE IF NOT EXISTS xhs_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL,
    nickname VARCHAR(100) NOT NULL COMMENT '账号昵称（便于识别）',
    xhs_username VARCHAR(100) DEFAULT NULL COMMENT '小红书用户名（可选，仅展示用）',
    cookies TEXT DEFAULT NULL COMMENT '登录凭证（cookies JSON字符串）',
    persona TEXT DEFAULT NULL COMMENT '账号人设描述（用于提示词）',
    niche VARCHAR(200) DEFAULT NULL COMMENT '账号定位/领域',
    tags VARCHAR(500) DEFAULT NULL COMMENT '常用标签，逗号分隔',
    status VARCHAR(20) DEFAULT 'active' COMMENT 'active / inactive / cookie_expired',
    last_login_at DATETIME(6) DEFAULT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_xhs_accounts_tenant_id (tenant_id),
    CONSTRAINT fk_xhs_account_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小红书账号表（矩阵管理）';

-- ==================== 9. xhs_materials ====================
CREATE TABLE IF NOT EXISTS xhs_materials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL,
    name VARCHAR(200) NOT NULL COMMENT '素材名称',
    material_type VARCHAR(20) DEFAULT 'image' COMMENT '仅 image',
    file_path VARCHAR(500) DEFAULT NULL COMMENT '图片文件路径',
    content TEXT DEFAULT NULL COMMENT '保留字段（备用）',
    description VARCHAR(500) DEFAULT NULL COMMENT '图片描述（用于提示词引用）',
    tags VARCHAR(500) DEFAULT NULL COMMENT '标签，逗号分隔',
    width INT DEFAULT NULL COMMENT '图片宽度（像素）',
    height INT DEFAULT NULL COMMENT '图片高度（像素）',
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_xhs_materials_tenant_id (tenant_id),
    CONSTRAINT fk_xhs_material_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='素材库表';

-- ==================== 10. xhs_tasks ====================
CREATE TABLE IF NOT EXISTS xhs_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL,
    account_id INT NOT NULL,
    title VARCHAR(200) NOT NULL COMMENT '文章标题',
    system_prompt TEXT DEFAULT NULL COMMENT '大模型角色说明（系统提示词）',
    user_prompt TEXT NOT NULL COMMENT '用户提示词',
    api_key_config JSON DEFAULT NULL COMMENT '使用的API Key配置',
    material_ids JSON DEFAULT NULL COMMENT '选用的素材ID列表',
    generated_title VARCHAR(200) DEFAULT NULL COMMENT 'AI生成的标题',
    generated_content TEXT DEFAULT NULL COMMENT 'AI生成的正文',
    generated_tags TEXT DEFAULT NULL COMMENT 'AI生成的标签（逗号分隔）',
    status VARCHAR(30) DEFAULT 'draft' COMMENT 'draft → generating → generated → publishing → published / failed',
    error_message TEXT DEFAULT NULL COMMENT '错误信息',
    published_url VARCHAR(500) DEFAULT NULL COMMENT '发布成功后的笔记链接',
    scheduled_at DATETIME(6) DEFAULT NULL COMMENT '定时发布时间（null=立即）',
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_xhs_tasks_tenant_id (tenant_id),
    INDEX idx_xhs_tasks_account_id (account_id),
    CONSTRAINT fk_xhs_task_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_xhs_task_account FOREIGN KEY (account_id) REFERENCES xhs_accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小红书发布任务表';

-- ==================== 初始化管理员账户 ====================
-- 密码：admin123（bcrypt hash）
-- 如需修改密码，运行 Python：
--   from utils.security import get_password_hash; print(get_password_hash("your-password"))
INSERT IGNORE INTO admins (username, hashed_password) VALUES (
    'admin',
    '$2b$12$EixZaYROxY/NOcy4T.nH9uH例如：TZtZ5dvMTF.pzIw8WrPjHt6Y2'
);
-- 上面是示例 hash，请用真实 hash 替换，或直接用后端自动创建功能（启动 backend 会自动创建）

COMMIT;
