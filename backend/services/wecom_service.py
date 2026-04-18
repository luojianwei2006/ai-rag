"""
企业微信服务
支持接收和发送消息，对接AI客服系统
"""
import json
import time
import hashlib
from typing import Optional, Dict, Any
import httpx
from database import SessionLocal
from models.models import Tenant, ChatSession, ChatMessage, KnowledgeBase
from services.rag_service import query_knowledge_base
from services.llm_service import call_llm, get_tenant_llm_config
from services.points_service import PointsService

# 消息去重缓存：message_id -> timestamp
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
        print(f"[WeComService] 消息 {message_id} 已处理过，跳过")
        return True
    
    # 记录消息 ID
    _processed_message_ids[message_id] = now
    return False


class WeComService:
    """企业微信服务封装"""
    
    BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"
    
    def __init__(self, corp_id: str, agent_id: str, secret: str, token: str = None, encoding_aes_key: str = None):
        self.corp_id = corp_id
        self.agent_id = int(agent_id) if agent_id else 0
        self.secret = secret
        self.token = token  # 用于验证消息签名
        self.encoding_aes_key = encoding_aes_key  # 用于解密消息
        self._access_token = None
        self._token_expire_time = 0
    
    async def _get_access_token(self) -> str:
        """获取企业微信 access_token（带缓存）"""
        if self._access_token and time.time() < self._token_expire_time:
            print(f"[WeComService] 使用缓存的 access_token")
            return self._access_token
        
        url = f"{self.BASE_URL}/gettoken"
        params = {"corpid": self.corp_id, "corpsecret": self.secret}
        
        print(f"[WeComService] 请求 access_token")
        print(f"[WeComService] URL: {url}")
        print(f"[WeComService] Corp ID: {self.corp_id}")
        print(f"[WeComService] Secret: {self.secret[:4]}****{self.secret[-4:] if len(self.secret) > 8 else ''}")
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            print(f"[WeComService] Response status: {resp.status_code}")
            
            data = resp.json()
            print(f"[WeComService] Response body: {data}")
            
            if data.get("errcode") != 0:
                raise Exception(f"获取access_token失败: {data}")
            
            self._access_token = data["access_token"]
            # 提前5分钟过期
            self._token_expire_time = time.time() + data["expires_in"] - 300
            print(f"[WeComService] 获取 access_token 成功，有效期: {data.get('expires_in', 'unknown')} 秒")
            return self._access_token
    
    async def send_text_message(self, user_id: str, content: str) -> bool:
        """发送文本消息给用户"""
        try:
            token = await self._get_access_token()
            
            url = f"{self.BASE_URL}/message/send"
            params = {"access_token": token}
            payload = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {"content": content},
                "safe": 0
            }
            
            print(f"[WeComService] 发送文本消息")
            print(f"[WeComService] URL: {url}")
            print(f"[WeComService] User ID: {user_id}")
            print(f"[WeComService] Agent ID: {self.agent_id}")
            print(f"[WeComService] Payload: {payload}")
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, params=params, json=payload)
                print(f"[WeComService] Response status: {resp.status_code}")
                
                data = resp.json()
                print(f"[WeComService] Response body: {data}")
                
                if data.get("errcode") != 0:
                    print(f"[WeComService] 发送企业微信消息失败: {data}")
                    return False
                print(f"[WeComService] 发送企业微信消息成功")
                return True
        except Exception as e:
            print(f"[WeComService] 发送企业微信消息异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        try:
            token = await self._get_access_token()
            url = f"{self.BASE_URL}/user/get"
            params = {"access_token": token, "userid": user_id}
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                if data.get("errcode") == 0:
                    return data
                return None
        except Exception as e:
            print(f"[WeComService] 获取企业微信用户信息异常: {e}")
            return None


def verify_wecom_signature(token: str, timestamp: str, nonce: str, msg_encrypt: str) -> str:
    """验证企业微信消息签名"""
    # 按企业微信文档：signature = sha1(sort(token + timestamp + nonce + msg_encrypt))
    tmp_list = [token, timestamp, nonce, msg_encrypt]
    tmp_list.sort()
    tmp_str = "".join(tmp_list)
    return hashlib.sha1(tmp_str.encode()).hexdigest()


def parse_wecom_message(xml_data: str) -> dict:
    """解析企业微信 XML 消息"""
    import xml.etree.ElementTree as ET
    
    try:
        root = ET.fromstring(xml_data)
        result = {}
        for child in root:
            result[child.tag] = child.text
        return result
    except Exception as e:
        print(f"[WeComService] 解析 XML 消息失败: {e}")
        return {}


async def _process_ai_reply(tenant: Tenant, user_id: str, user_name: str, user_message: str) -> str:
    """处理 AI 回复逻辑"""
    db = SessionLocal()
    try:
        # 查找或创建会话
        session = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant.id,
            ChatSession.customer_name == f"wecom:{user_id}"
        ).first()
        
        if not session:
            session = ChatSession(
                tenant_id=tenant.id,
                session_id=f"wecom_{tenant.id}_{user_id}",
                customer_name=f"wecom:{user_id}",
                customer_ip="wecom",
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
                    reply = await call_llm(model, api_keys, history, context)
                    
                    # 扣除积分
                    PointsService.deduct_points(
                        db, tenant.id, cost, "ai_reply",
                        description="AI客服回答（企业微信）",
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


async def handle_wecom_message(tenant: Tenant, message_data: dict) -> str:
    """
    处理企业微信消息事件
    返回回复内容（空字符串表示无需回复）
    """
    msg_type = message_data.get("MsgType", "").lower()
    user_id = message_data.get("FromUserName", "")
    user_name = message_data.get("FromUserName", "企业微信用户")
    msg_id = message_data.get("MsgId", "")
    
    print(f"[WeCom Service] MsgType: {msg_type}, User: {user_id}, MsgId: {msg_id}")
    
    # 去重检查
    if msg_id and _is_duplicate_message(msg_id):
        print(f"[WeCom Service] 消息 {msg_id} 重复，跳过处理")
        return ""
    
    # 只处理文本消息
    if msg_type != "text":
        print(f"[WeCom Service] 非文本消息类型: {msg_type}")
        return ""
    
    user_message = message_data.get("Content", "").strip()
    print(f"[WeCom Service] 用户消息: {user_message}")
    
    if not user_message:
        return ""
    
    # 调用 AI 回复逻辑
    return await _process_ai_reply(tenant, user_id, user_name, user_message)
