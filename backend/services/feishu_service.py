"""
飞书开放平台服务
支持接收和发送消息，对接AI客服系统
"""
import json
import time
import hashlib
import base64
from typing import Optional, Dict, Any, Set
import httpx
from database import SessionLocal
from models.models import Tenant, ChatSession, ChatMessage, KnowledgeBase
from services.rag_service import query_knowledge_base
from services.llm_service import call_llm, get_tenant_llm_config, LLMError
from services.points_service import PointsService

# 消息去重缓存：message_id -> timestamp
# 使用内存缓存，保存最近 5 分钟的消息 ID
_processed_message_ids: Dict[str, float] = {}


def _is_duplicate_message(message_id: str) -> bool:
    """检查消息是否已处理过（5分钟内）"""
    now = time.time()
    
    # 清理过期的消息 ID（超过 5 分钟）
    expired_ids = [mid for mid, ts in _processed_message_ids.items() if now - ts > 300]
    for mid in expired_ids:
        del _processed_message_ids[mid]
    
    # 检查当前消息是否已处理
    if message_id in _processed_message_ids:
        print(f"[FeishuService] 消息 {message_id} 已处理过，跳过")
        return True
    
    # 记录消息 ID
    _processed_message_ids[message_id] = now
    return False


class FeishuService:
    """飞书服务封装"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._access_token = None
        self._token_expire_time = 0
    
    async def _get_access_token(self) -> str:
        """获取飞书 access_token（带缓存）"""
        if self._access_token and time.time() < self._token_expire_time:
            print(f"[FeishuService] 使用缓存的 access_token")
            return self._access_token
        
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        
        print(f"[FeishuService] 请求 access_token")
        print(f"[FeishuService] URL: {url}")
        print(f"[FeishuService] App ID: {self.app_id}")
        print(f"[FeishuService] App Secret: {self.app_secret[:4]}****{self.app_secret[-4:] if len(self.app_secret) > 8 else ''}")
        print(f"[FeishuService] Payload: {payload}")
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            print(f"[FeishuService] Response status: {resp.status_code}")
            print(f"[FeishuService] Response headers: {dict(resp.headers)}")
            
            data = resp.json()
            print(f"[FeishuService] Response body: {data}")
            
            if data.get("code") != 0:
                raise Exception(f"获取access_token失败: {data}")
            
            self._access_token = data["tenant_access_token"]
            # 提前5分钟过期
            self._token_expire_time = time.time() + data["expire"] - 300
            print(f"[FeishuService] 获取 access_token 成功，有效期: {data.get('expire', 'unknown')} 秒")
            return self._access_token
    
    async def send_text_message(self, receive_id: str, content: str, receive_id_type: str = "open_id") -> bool:
        """发送文本消息给用户"""
        try:
            token = await self._get_access_token()
            
            url = f"{self.BASE_URL}/im/v1/messages?receive_id_type={receive_id_type}"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": content})
            }
            
            print(f"[FeishuService] 发送文本消息")
            print(f"[FeishuService] URL: {url}")
            print(f"[FeishuService] Headers: {headers}")
            print(f"[FeishuService] Payload: {payload}")
            print(f"[FeishuService] Receive ID: {receive_id}")
            print(f"[FeishuService] Receive ID Type: {receive_id_type}")
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload)
                print(f"[FeishuService] Response status: {resp.status_code}")
                
                data = resp.json()
                print(f"[FeishuService] Response body: {data}")
                
                if data.get("code") != 0:
                    print(f"[FeishuService] 发送飞书消息失败: {data}")
                    return False
                print(f"[FeishuService] 发送飞书消息成功")
                return True
        except Exception as e:
            print(f"[FeishuService] 发送飞书消息异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def send_card_message(self, receive_id: str, card_content: dict, receive_id_type: str = "open_id") -> bool:
        """发送卡片消息（富文本）"""
        try:
            token = await self._get_access_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.BASE_URL}/im/v1/messages?receive_id_type={receive_id_type}",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": receive_id,
                        "msg_type": "interactive",
                        "content": json.dumps(card_content)
                    }
                )
                data = resp.json()
                return data.get("code") == 0
        except Exception as e:
            print(f"发送飞书卡片消息异常: {e}")
            return False
    
    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        try:
            token = await self._get_access_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.BASE_URL}/contact/v3/users/{user_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = resp.json()
                if data.get("code") == 0:
                    return data.get("data", {}).get("user")
                return None
        except Exception as e:
            print(f"获取飞书用户信息异常: {e}")
            return None


def verify_feishu_signature(timestamp: str, nonce: str, encrypt_key: str, body: str, signature: str) -> bool:
    """验证飞书消息签名（加密模式）"""
    if not encrypt_key:
        return True  # 未配置加密密钥时不验证
    
    # 按飞书文档：signature = sha1(timestamp + nonce + encrypt_key + body)
    sign_str = timestamp + nonce + encrypt_key + body
    expected = hashlib.sha1(sign_str.encode()).hexdigest()
    return expected == signature


async def _process_ai_reply(tenant: Tenant, sender: dict, user_message: str) -> str:
    """处理 AI 回复逻辑"""
    # 获取或创建会话
    db = SessionLocal()
    try:
        open_id = sender.get("sender_id", {}).get("open_id", "")
        user_name = sender.get("sender_id", {}).get("user_id", "飞书用户")
        
        # 查找或创建会话
        session = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant.id,
            ChatSession.customer_name == f"feishu:{open_id}"
        ).first()
        
        if not session:
            session = ChatSession(
                tenant_id=tenant.id,
                session_id=f"feishu_{tenant.id}_{open_id}",
                customer_name=f"feishu:{open_id}",
                customer_ip="feishu",
                status="active"
            )
            db.add(session)
            db.commit()
        
        # 保存用户消息
        user_msg = ChatMessage(
            session_id=session.session_id,
            role="customer",
            content=user_message
        )
        db.add(user_msg)
        db.commit()
        
        # 检查是否请求人工
        human_keywords = ["人工", "人工客服", "转人工", "真人", "真人客服"]
        is_human_request = any(kw in user_message for kw in human_keywords)
        
        if is_human_request:
            session.is_human_service = True
            session.status = "human"
            db.commit()
            reply = "已为您转接人工客服，请稍候..."
        else:
            # AI 回复 - 先检查积分
            config = PointsService.get_config(db)
            cost = config.get("ai_reply_cost", 5)
            
            if tenant.points_balance < cost:
                reply = f"抱歉，您的积分不足（当前余额: {tenant.points_balance} 点），无法使用AI客服服务。请联系管理员充值。"
            else:
                # 获取知识库
                kbs = db.query(KnowledgeBase).filter(
                    KnowledgeBase.tenant_id == tenant.id,
                    KnowledgeBase.status == "ready"
                ).all()
                
                context = ""
                if kbs:
                    all_docs = []
                    for kb in kbs:
                        docs = query_knowledge_base(tenant.id, kb.id, user_message, n_results=3)
                        all_docs.extend(docs)
                    context = "\n".join(all_docs[:10])
                
                # 获取历史消息
                recent_msgs = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session.session_id
                ).order_by(ChatMessage.created_at.desc()).limit(10).all()
                recent_msgs.reverse()
                
                history = []
                for m in recent_msgs:
                    if m.role == "customer":
                        history.append({"role": "user", "content": m.content})
                    elif m.role == "ai":
                        history.append({"role": "assistant", "content": m.content})
                
                # 调用 LLM
                model, api_keys = get_tenant_llm_config(tenant, db)
                if not api_keys:
                    reply = "抱歉，AI服务暂时不可用，请联系客服。"
                else:
                    try:
                        reply = await call_llm(model, api_keys, history, context)
                    except LLMError:
                        reply = "抱歉，AI服务暂时不可用，请稍后重试。"
                    else:
                        # 仅 LLM 调用成功时才扣积分
                        PointsService.deduct_points(
                            db, tenant.id, cost, "ai_reply",
                            description="AI客服回答（飞书）",
                            related_id=session.session_id
                        )
        
        # 保存AI回复
        ai_msg = ChatMessage(
            session_id=session.session_id,
            role="ai",
            content=reply
        )
        db.add(ai_msg)
        db.commit()
        
        return reply
        
    finally:
        db.close()


async def handle_feishu_message(tenant: Tenant, event_data: dict) -> str:
    """
    处理飞书消息事件
    返回回复内容（空字符串表示无需回复）
    """
    # 飞书新版事件格式 (schema 2.0)
    schema = event_data.get("schema")
    header = event_data.get("header", {})
    event_type = event_data.get("type") or header.get("event_type")
    
    print(f"[Feishu Service] Schema: {schema}, Event type: {event_type}")
    print(f"[Feishu Service] Event data keys: {event_data.keys()}")
    
    # 处理 URL 验证（配置事件订阅时）- 旧版格式
    if event_data.get("type") == "url_verification":
        return event_data.get("challenge", "")
    
    # 统一处理消息事件 - 兼容新旧两种格式
    event = None
    
    # 新版格式 (schema 2.0)
    if schema == "2.0":
        event = event_data.get("event", {})
    # 旧版格式 (event_callback)
    elif event_type == "event_callback":
        event = event_data.get("event", {})
        # 旧版格式需要检查事件类型
        event_msg_type = event.get("type", "")
        if event_msg_type not in ["im.message.receive_v1", "message"]:
            print(f"[Feishu Service] Not a message event: {event_msg_type}")
            return ""
    # 直接的事件格式
    elif event_type == "im.message.receive_v1":
        event = event_data.get("event", {})
    
    if not event:
        print(f"[Feishu Service] Unknown event format")
        return ""
    
    print(f"[Feishu Service] Event content: {event}")
    
    message = event.get("message", {})
    sender = event.get("sender", {})
    
    print(f"[Feishu Service] Message: {message}")
    print(f"[Feishu Service] Sender: {sender}")
    
    # 获取消息 ID 进行去重检查
    message_id = message.get("message_id", "")
    if message_id and _is_duplicate_message(message_id):
        print(f"[Feishu Service] 消息 {message_id} 重复，跳过处理")
        return ""
    
    # 只处理文本消息
    msg_type = message.get("message_type", "")
    if msg_type != "text":
        print(f"[Feishu Service] Not a text message: {msg_type}")
        return ""
    
    # 解析消息内容
    try:
        content = json.loads(message.get("content", "{}"))
        user_message = content.get("text", "").strip()
        print(f"[Feishu Service] User message: {user_message}")
    except json.JSONDecodeError as e:
        print(f"[Feishu Service] Failed to parse content: {e}")
        return ""
    
    if not user_message:
        return ""
    
    # 调用 AI 回复逻辑
    return await _process_ai_reply(tenant, sender, user_message)
