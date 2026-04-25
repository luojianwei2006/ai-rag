from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Admin(Base):
    """管理员表"""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SystemConfig(Base):
    """系统配置表（SMTP、默认API Key、扣费设置等）"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class PointsTransaction(Base):
    """积分消费记录表"""
    __tablename__ = "points_transactions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    transaction_type = Column(String(50), nullable=False)  # knowledge_add, ai_reply, human_reply, recharge
    points = Column(Integer, nullable=False)  # 正数为充值，负数为消费
    description = Column(String(255), nullable=True)
    related_id = Column(String(100), nullable=True)  # 关联ID（如知识库ID、会话ID等）
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="points_transactions")


class Tenant(Base):
    """商户表"""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    company_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    # 客服链接唯一标识
    chat_token = Column(String(64), unique=True, index=True, nullable=False)
    # API Key配置
    use_system_api_key = Column(Boolean, default=True)
    custom_api_keys = Column(JSON, default=dict)  # {"glm": "key", "openai": "key", "gemini": "key"}
    preferred_model = Column(String(50), default="glm")  # 首选模型
    
    # 飞书配置
    feishu_enabled = Column(Boolean, default=False)
    feishu_app_id = Column(String(100), nullable=True)
    feishu_app_secret = Column(String(255), nullable=True)
    feishu_encrypt_key = Column(String(255), nullable=True)
    
    # 企业微信配置
    wecom_enabled = Column(Boolean, default=False)
    wecom_corp_id = Column(String(100), nullable=True)
    wecom_agent_id = Column(String(50), nullable=True)
    wecom_secret = Column(String(255), nullable=True)
    wecom_token = Column(String(255), nullable=True)
    wecom_encoding_aes_key = Column(String(255), nullable=True)
    
    # 积分余额
    points_balance = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联
    knowledge_bases = relationship("KnowledgeBase", back_populates="tenant", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="tenant", cascade="all, delete-orphan")
    points_transactions = relationship("PointsTransaction", back_populates="tenant", cascade="all, delete-orphan")
    xhs_accounts = relationship("XhsAccount", back_populates="tenant", cascade="all, delete-orphan")
    xhs_materials = relationship("XhsMaterial", back_populates="tenant", cascade="all, delete-orphan")
    xhs_tasks = relationship("XhsTask", back_populates="tenant", cascade="all, delete-orphan")


class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_type = Column(String(20), nullable=True)  # excel, word, txt
    status = Column(String(20), default="processing")  # processing, ready, failed
    progress = Column(Integer, default=0)  # 处理进度 0-100
    progress_message = Column(String(100), default="等待处理")  # 进度描述
    chunk_count = Column(Integer, default=0)
    # ChromaDB collection name
    collection_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="knowledge_bases")


class ChatSession(Base):
    """聊天会话表"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    customer_name = Column(String(100), nullable=True, default="访客")
    customer_ip = Column(String(50), nullable=True)
    status = Column(String(20), default="active")  # active, human, closed
    is_human_service = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.session_id"), nullable=False)
    role = Column(String(20), nullable=False)  # customer, ai, human_agent
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


# ==================== 小红书相关模型 ====================

class XhsAccount(Base):
    """小红书账号表（矩阵管理）"""
    __tablename__ = "xhs_accounts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    nickname = Column(String(100), nullable=False)          # 账号昵称（便于识别）
    xhs_username = Column(String(100), nullable=True)       # 小红书用户名（可选，仅展示用）
    # 登录凭证（cookies JSON字符串，由首次登录后自动保存）
    cookies = Column(Text, nullable=True)
    # 账号补充信息
    persona = Column(Text, nullable=True)                   # 账号人设描述（用于提示词）
    niche = Column(String(200), nullable=True)              # 账号定位/领域
    tags = Column(String(500), nullable=True)               # 常用标签，逗号分隔
    status = Column(String(20), default="active")           # active / inactive / cookie_expired
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="xhs_accounts")
    tasks = relationship("XhsTask", back_populates="account")


class XhsMaterial(Base):
    """素材库表"""
    __tablename__ = "xhs_materials"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(200), nullable=False)              # 素材名称
    material_type = Column(String(20), nullable=False, default="image")  # 仅 image
    file_path = Column(String(500), nullable=True)          # 图片文件路径
    content = Column(Text, nullable=True)                   # 保留字段（备用）
    description = Column(String(500), nullable=True)        # 图片描述（用于提示词引用）
    tags = Column(String(500), nullable=True)               # 标签，逗号分隔
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="xhs_materials")


class XhsTask(Base):
    """小红书发布任务表"""
    __tablename__ = "xhs_tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("xhs_accounts.id"), nullable=False)

    # 任务基本信息
    title = Column(String(200), nullable=False)             # 文章标题
    system_prompt = Column(Text, nullable=True)             # 大模型角色说明（系统提示词）
    user_prompt = Column(Text, nullable=False)              # 用户提示词
    api_key_config = Column(JSON, nullable=True)            # 使用的API Key配置 {"provider":"openai","api_key":"sk-...","model":"gpt-4o"}
    material_ids = Column(JSON, default=list)               # 选用的素材ID列表

    # 生成结果
    generated_title = Column(String(200), nullable=True)    # AI生成的标题
    generated_content = Column(Text, nullable=True)         # AI生成的正文
    generated_tags = Column(Text, nullable=True)            # AI生成的标签（逗号分隔）

    # 任务状态
    status = Column(String(30), default="draft")
    # draft（草稿）→ generating（生成中）→ generated（已生成，待发布）
    # → publishing（发布中）→ published（已发布）→ failed（失败）

    error_message = Column(Text, nullable=True)             # 错误信息
    published_url = Column(String(500), nullable=True)      # 发布成功后的笔记链接

    # 调度（可选）
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # 定时发布时间（null=立即）

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="xhs_tasks")
    account = relationship("XhsAccount", back_populates="tasks")

