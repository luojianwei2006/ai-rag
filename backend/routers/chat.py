import json
import os
import uuid
import secrets
import asyncio
from datetime import datetime
from typing import Dict, Set
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models.models import Tenant, KnowledgeBase, ChatSession, ChatMessage
from utils.security import get_current_tenant, decode_token
from utils.crypto import encrypt_chat_params, decrypt_chat_params
from services.rag_service import query_knowledge_base
from services.llm_service import call_llm, get_tenant_llm_config, LLMError
from services.points_service import PointsService
from routers.embed import embed_manager
from config import settings

router = APIRouter(tags=["聊天"])

# 多语言文案映射
CHAT_I18N = {
    "zh": {
        "welcome": "您好！我是AI客服助手，请问有什么可以帮助您的？",
        "transfer_human": "已为您转接人工客服，请稍候...",
        "points_low": "抱歉，您的积分不足（当前余额: {balance} 点），无法使用AI客服服务。请联系管理员充值。",
        "ai_unavailable": "抱歉，AI服务暂时不可用，请联系客服。",
        "ai_error": "抱歉，AI服务暂时不可用，请稍后重试。",
        "process_error": "抱歉，处理您的问题时出现了错误，请稍后重试。",
        "company_fallback": "在线客服",
        "status_ai": "AI智能客服在线",
        "status_human": "人工客服为您服务",
    },
    "en": {
        "welcome": "Hello! I'm an AI customer service assistant. How can I help you?",
        "transfer_human": "Connecting you to a human agent, please wait...",
        "points_low": "Sorry, your credits are insufficient (current balance: {balance} pts). Please contact the administrator to recharge.",
        "ai_unavailable": "Sorry, the AI service is currently unavailable. Please contact customer support.",
        "ai_error": "Sorry, the AI service is temporarily unavailable. Please try again later.",
        "process_error": "Sorry, an error occurred while processing your request. Please try again later.",
        "company_fallback": "Customer Service",
        "status_ai": "AI Assistant Online",
        "status_human": "Human Agent Serving",
    },
}

# 人工介入关键词
HUMAN_KEYWORDS = [
    "人工", "人工客服", "转人工", "真人", "真人客服",
    "找人工", "要人工", "接人工", "帮我找人", "人工服务"
]

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        # 客户连接: session_id -> WebSocket
        self.customer_connections: Dict[str, WebSocket] = {}
        # 商户监控连接: tenant_id -> Set[WebSocket]
        self.tenant_monitor_connections: Dict[int, Set[WebSocket]] = {}

    async def connect_customer(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.customer_connections[session_id] = ws

    def disconnect_customer(self, session_id: str):
        self.customer_connections.pop(session_id, None)

    async def connect_tenant_monitor(self, tenant_id: int, ws: WebSocket):
        if tenant_id not in self.tenant_monitor_connections:
            self.tenant_monitor_connections[tenant_id] = set()
        self.tenant_monitor_connections[tenant_id].add(ws)
        print(f"[monitor] 监控端已连接 tenant={tenant_id} total_conns={len(self.tenant_monitor_connections[tenant_id])}")

    def disconnect_tenant_monitor(self, tenant_id: int, ws: WebSocket):
        if tenant_id in self.tenant_monitor_connections:
            self.tenant_monitor_connections[tenant_id].discard(ws)
            print(f"[monitor] 监控端已断开 tenant={tenant_id} remaining={len(self.tenant_monitor_connections[tenant_id])}")

    async def send_to_customer(self, session_id: str, message: dict):
        ws = self.customer_connections.get(session_id)
        print(f"[send_to_customer] session_id={session_id[:8]} role={message.get('role','')} has_ws={ws is not None}")
        if ws:
            try:
                await ws.send_json(message)
                print(f"[send_to_customer] ✅ 发送成功 session_id={session_id[:8]}")
            except Exception as e:
                print(f"[send_to_customer] ❌ 发送失败 session_id={session_id[:8]}: {e}")
                self.disconnect_customer(session_id)

    async def broadcast_to_tenant(self, tenant_id: int, message: dict):
        """向商户的所有监控连接广播消息"""
        connections = self.tenant_monitor_connections.get(tenant_id, set())
        msg_type = message.get("type", "?")
        session_id_short = (message.get('session_id') or "")[:8]
        role = message.get("role", "")
        content_short = (message.get("content") or "")[:30]
        print(f"[broadcast] tenant={tenant_id} conns={len(connections)} type={msg_type} sid={session_id_short} role={role} content='{content_short}'")
        disconnected = set()
        for ws in list(connections):
            try:
                await ws.send_json(message)
            except Exception as e:
                print(f"[broadcast] ❌ 发送失败 tenant={tenant_id}: {e}")
                disconnected.add(ws)
        for ws in disconnected:
            connections.discard(ws)
        if disconnected:
            print(f"[broadcast] 清理了 {len(disconnected)} 个断开的连接")


manager = ConnectionManager()


async def broadcast_to_all(tenant, message: dict):
    """同时推送给商户监控端和嵌入监控端"""
    await manager.broadcast_to_tenant(tenant.id, message)
    if tenant.embed_api_key:
        await embed_manager.broadcast(tenant.embed_api_key, message)


# ─────── REST 接口 ───────

class SendMessageRequest(BaseModel):
    content: str


class HumanReplyRequest(BaseModel):
    session_id: str
    content: str


@router.get("/api/chat/sessions")
async def get_chat_sessions(
    uid: str = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取商户的所有会话，支持按 uid 筛选"""
    query = db.query(ChatSession).filter(ChatSession.tenant_id == tenant.id)
    if uid:
        query = query.filter(ChatSession.uid == uid)
    sessions = query.order_by(ChatSession.created_at.desc()).limit(100).all()

    result = []
    for s in sessions:
        last_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == s.session_id
        ).order_by(ChatMessage.created_at.desc()).first()

        result.append({
            "session_id": s.session_id,
            "uid": s.uid or "",
            "customer_name": s.customer_name,
            "status": s.status,
            "is_human_service": s.is_human_service,
            "taken_over": s.taken_over or False,
            "last_message": last_msg.content[:50] if last_msg else "",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "online": s.session_id in manager.customer_connections
        })

    # 合并相同 uid 的会话（取最新的一条）
    uid_map = {}
    merged = []
    for item in result:
        uid = item.get("uid") or item["session_id"]
        if uid not in uid_map:
            uid_map[uid] = item
            item["all_session_ids"] = [item["session_id"]]
            merged.append(item)
        else:
            uid_map[uid]["all_session_ids"].append(item["session_id"])
            # 如果当前条更新的，替换
            curr_created = item.get("created_at")
            prev_created = uid_map[uid].get("created_at")
            if curr_created and prev_created and curr_created > prev_created:
                item["all_session_ids"] = uid_map[uid]["all_session_ids"]
                uid_map[uid] = item
                merged[-1] = item
    result = merged

    return result


@router.get("/api/chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取会话消息历史"""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 如果该会话有 uid，查询该 uid 下所有会话的消息
    if session.uid:
        uid_sessions = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant.id,
            ChatSession.uid == session.uid
        ).all()
        session_ids = [s.session_id for s in uid_sessions]
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id.in_(session_ids)
        ).order_by(ChatMessage.created_at.asc()).all()
    else:
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

    return [{
        "id": m.id,
        "role": m.role,
        "msg_type": m.msg_type or "text",
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None
    } for m in messages]


@router.post("/api/chat/human-reply")
async def human_reply(
    req: HumanReplyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """商户发送人工回复"""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == req.session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 人工回复扣费检查
    config = PointsService.get_config(db)
    cost = config.get("human_reply_cost", 1)
    
    if tenant.points_balance < cost:
        raise HTTPException(
            status_code=400, 
            detail=f"积分不足，人工回复需要 {cost} 点，当前余额: {tenant.points_balance} 点"
        )

    # 保存消息
    msg = ChatMessage(
        session_id=req.session_id,
        role="human_agent",
        content=req.content
    )
    db.add(msg)
    db.commit()

    # 扣除积分
    success, message, new_balance = PointsService.deduct_points(
        db, tenant.id, cost, "human_reply",
        description="人工客服回复",
        related_id=req.session_id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # 判断客户类型
    if session.customer_ip == "feishu" or session.session_id.startswith("feishu_"):
        # 飞书用户：通过飞书 API 发送消息
        from services.feishu_service import FeishuService
        
        # 从 customer_name 中提取 open_id (格式: feishu:{open_id})
        open_id = session.customer_name.replace("feishu:", "") if session.customer_name else None
        
        if open_id and tenant.feishu_app_id and tenant.feishu_app_secret:
            try:
                feishu = FeishuService(tenant.feishu_app_id, tenant.feishu_app_secret)
                success = await feishu.send_text_message(open_id, req.content)
                if not success:
                    raise HTTPException(status_code=500, detail="飞书消息发送失败")
            except Exception as e:
                print(f"[HumanReply] 发送飞书消息失败: {e}")
                raise HTTPException(status_code=500, detail=f"飞书消息发送失败: {str(e)}")
        else:
            print(f"[HumanReply] 无法发送飞书消息: open_id={open_id}, feishu_configured={bool(tenant.feishu_app_id)}")
    
    elif session.customer_ip == "wecom" or session.session_id.startswith("wecom_"):
        # 企业微信用户：通过企业微信 API 发送消息
        from services.wecom_service import WeComService
        
        # 从 customer_name 中提取 user_id (格式: wecom:{user_id})
        user_id = session.customer_name.replace("wecom:", "") if session.customer_name else None
        
        if user_id and tenant.wecom_corp_id and tenant.wecom_agent_id and tenant.wecom_secret:
            try:
                wecom = WeComService(
                    corp_id=tenant.wecom_corp_id,
                    agent_id=tenant.wecom_agent_id,
                    secret=tenant.wecom_secret
                )
                success = await wecom.send_text_message(user_id, req.content)
                if not success:
                    raise HTTPException(status_code=500, detail="企业微信消息发送失败")
            except Exception as e:
                print(f"[HumanReply] 发送企业微信消息失败: {e}")
                raise HTTPException(status_code=500, detail=f"企业微信消息发送失败: {str(e)}")
        else:
            print(f"[HumanReply] 无法发送企业微信消息: user_id={user_id}, wecom_configured={bool(tenant.wecom_corp_id)}")
    
    else:
        # 网页用户：通过 WebSocket 推送
        print(f"[human_reply] 准备发给客户 session_id={req.session_id[:8]} content='{req.content[:30]}'")
        await manager.send_to_customer(req.session_id, {
            "type": "message",
            "role": "human_agent",
            "content": req.content,
            "timestamp": datetime.now().isoformat()
        })
        print(f"[human_reply] ✅ 已发给客户 session_id={req.session_id[:8]}")

    # 广播给管理后台监控端（让管理员自己的回复也实时显示）
    print(f"[human_reply] 准备广播给管理后台 tenant={tenant.id} session_id={req.session_id[:8]}")
    await broadcast_to_all(tenant, {
        "type": "message",
        "session_id": req.session_id,
        "role": "human_agent",
        "content": req.content,
        "timestamp": datetime.now().isoformat()
    })
    print(f"[human_reply] ✅ 已广播给管理后台")

    return {
        "message": "发送成功",
        "points_deducted": cost,
        "points_balance": new_balance
    }


# ─────── 客户端公开接口 ───────

@router.get("/api/public/chat/{chat_token}/info")
async def get_chat_info(chat_token: str, db: Session = Depends(get_db)):
    """获取客服信息（客户端使用）"""
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")
    return {
        "company_name": tenant.company_name or CHAT_I18N.get(tenant.chat_language or "zh", {}).get("company_fallback", "在线客服"),
        "chat_token": chat_token,
        "language": tenant.chat_language or "zh",
        "avatar_url": tenant.avatar_url or None,
        "embed_api_key": tenant.embed_api_key or ""
    }


# ─────── 客户端图片上传 ───────

@router.post("/api/public/chat/upload-image")
async def upload_chat_image(chat_token: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """客户聊天上传图片"""
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")

    # 校验文件类型
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
        raise HTTPException(status_code=400, detail="仅支持图片格式: png/jpg/jpeg/gif/webp/bmp")

    # 限制大小 10MB
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    # 保存到 uploads/chat_images/
    upload_dir = os.path.join(settings.UPLOAD_DIR, "chat_images", str(tenant.id))
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    url = f"/static/chat_images/{tenant.id}/{filename}"
    print(f"[Upload] tenant={tenant.id} file={filename} size={len(content)} ext={ext} url={url}")
    return {"url": url}


# ─────── WebSocket ───────

@router.websocket("/ws/chat/{chat_token}")
async def customer_chat_ws(
    websocket: WebSocket,
    chat_token: str
):
    """客户聊天 WebSocket，支持 uid 和 nickname 查询参数"""
    import traceback
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
        if not tenant or not tenant.is_active:
            await websocket.close(code=4004)
            return

        # 读取查询参数：优先使用加密参数 p，兼容旧的 uid/nickname 明文参数
        params = dict(websocket.query_params)
        req_uid = params.get("uid")
        req_nickname = params.get("nickname", "")
        p = params.get("p")
        if p:
            try:
                # 优先使用商户专属 key 解密
                decrypt_key = tenant.embed_api_key or None
                decrypted = decrypt_chat_params(p, key=decrypt_key)
                req_uid = decrypted.get("uid") or req_uid
                req_nickname = decrypted.get("nickname") or req_nickname
            except Exception:
                # 商户 key 解密失败，尝试默认 key
                try:
                    decrypted = decrypt_chat_params(p, key=None)  # None = 使用默认密钥
                    req_uid = decrypted.get("uid") or req_uid
                    req_nickname = decrypted.get("nickname") or req_nickname
                except Exception:
                    pass  # 都失败则继续使用明文参数

        # 创建会话
        session_id = secrets.token_urlsafe(16)
        session = ChatSession(
            tenant_id=tenant.id,
            session_id=session_id,
            uid=req_uid or None,
            customer_name=req_nickname or "访客",
            customer_ip=websocket.client.host if websocket.client else "unknown",
            status="active"
        )
        db.add(session)
        db.commit()

        await manager.connect_customer(session_id, websocket)

        # 更新在线状态
        session.online = True
        session.last_active = datetime.now()
        db.commit()

        # 获取语言设置
        lang = tenant.chat_language or "zh"
        i18n = CHAT_I18N.get(lang, CHAT_I18N["zh"])

        # 通知商户（附带 uid 和 customer_name）
        await broadcast_to_all(tenant, {
            "type": "new_session",
            "session_id": session_id,
            "uid": req_uid or "",
            "customer_name": session.customer_name,
            "timestamp": datetime.now().isoformat()
        })

        # 如果有 uid，加载最近一次会话的历史消息发给客户端
        if req_uid:
            prev_session = db.query(ChatSession).filter(
                ChatSession.tenant_id == tenant.id,
                ChatSession.uid == req_uid,
                ChatSession.session_id != session_id,
            ).order_by(ChatSession.created_at.desc()).first()

            if prev_session:
                history_msgs = db.query(ChatMessage).filter(
                    ChatMessage.session_id == prev_session.session_id
                ).order_by(ChatMessage.created_at.asc()).all()

                for hm in history_msgs:
                    await websocket.send_json({
                        "type": "history_message",
                        "role": hm.role,
                        "msg_type": hm.msg_type or "text",
                        "content": hm.content,
                        "timestamp": hm.created_at.isoformat() if hm.created_at else ""
                    })

        # 发送欢迎消息
        if tenant.ai_enabled is False:
            # AI 客服已关闭，发送人工客服提示
            offline_msg = "您好，AI客服已关闭，将由人工客服为您服务，请稍候。"
            if lang == "en":
                offline_msg = "Hello, AI assistant is currently unavailable. A human agent will assist you shortly."
            await websocket.send_json({
                "type": "message",
                "role": "system",
                "content": offline_msg,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            })
        else:
            welcome = i18n["welcome"]
            welcome_msg = ChatMessage(session_id=session_id, role="ai", content=welcome)
            db.add(welcome_msg)
            db.commit()

            await websocket.send_json({
                "type": "message",
                "role": "ai",
                "content": welcome,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            })

        # 消息循环
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("content", "").strip()
            msg_type = payload.get("msg_type", "text")  # text / image

            if not user_message:
                continue

            # 保存用户消息
            user_msg = ChatMessage(session_id=session_id, role="customer", msg_type=msg_type, content=user_message)
            db.add(user_msg)
            db.commit()

            # 广播给商户（客户发了消息）
            print(f"[WS chat] 客户消息广播 session_id={session_id[:8]} content='{user_message[:30]}'")
            await broadcast_to_all(tenant, {
                "type": "message",
                "session_id": session_id,
                "uid": session.uid or "",
                "role": "customer",
                "msg_type": msg_type,
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })
            print(f"[WS chat] ✅ 客户消息已广播 session_id={session_id[:8]}")

            # 检查是否请求人工
            is_human_request = any(kw in user_message for kw in HUMAN_KEYWORDS)

            if is_human_request or session.is_human_service:
                # 转人工
                if not session.is_human_service:
                    session.is_human_service = True
                    session.status = "human"
                    db.commit()

                    transfer_msg = i18n["transfer_human"]
                    ai_msg = ChatMessage(session_id=session_id, role="ai", content=transfer_msg)
                    db.add(ai_msg)
                    db.commit()

                    await websocket.send_json({
                        "type": "message",
                        "role": "system",
                        "content": transfer_msg,
                        "timestamp": datetime.now().isoformat()
                    })

                    # 通知商户
                    await broadcast_to_all(tenant, {
                        "type": "human_requested",
                        "session_id": session_id,
                        "uid": session.uid or "",
                        "customer_name": session.customer_name,
                        "content": user_message,
                        "timestamp": datetime.now().isoformat()
                    })
                continue

            # AI 回复（仅当 AI 启用时）
            if not tenant.ai_enabled:
                continue

            # AI回复
            try:
                # AI 回复扣费检查
                config = PointsService.get_config(db)
                cost = config.get("ai_reply_cost", 5)
                
                if tenant.points_balance < cost:
                    reply = i18n["points_low"].format(balance=tenant.points_balance)
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

                    # 获取历史消息（最近10条）
                    recent_msgs = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id
                    ).order_by(ChatMessage.created_at.desc()).limit(10).all()
                    recent_msgs.reverse()

                    history = []
                    for m in recent_msgs:
                        if m.role == "customer":
                            history.append({"role": "user", "content": m.content})
                        elif m.role == "ai":
                            history.append({"role": "assistant", "content": m.content})

                    model, api_keys = get_tenant_llm_config(tenant, db)
                    if not api_keys:
                        reply = i18n["ai_unavailable"]
                    else:
                        try:
                            # 根据语言设置构建 system prompt
                            lang_instruction = ""
                            if lang == "en":
                                lang_instruction = "\n\nYou MUST respond in English."
                            reply = await call_llm(model, api_keys, history, context, system_prompt=None, lang_instruction=lang_instruction)
                        except LLMError:
                            reply = i18n["ai_error"]
                        else:
                            # 仅 LLM 调用成功时才扣积分
                            PointsService.deduct_points(
                                db, tenant.id, cost, "ai_reply",
                                description="AI客服回答（网页）",
                                related_id=session_id
                            )

            except LLMError:
                # LLM 调用失败已在上方处理，此处不再重复
                pass
            except Exception as e:
                reply = i18n["process_error"]

            # 保存AI回复
            ai_msg = ChatMessage(session_id=session_id, role="ai", content=reply)
            db.add(ai_msg)
            db.commit()

            # 发送给客户
            print(f"[WS chat] 准备发 AI 回复给客户 session_id={session_id[:8]} content='{reply[:30]}'")
            await websocket.send_json({
                "type": "message",
                "role": "ai",
                "content": reply,
                "timestamp": datetime.now().isoformat()
            })
            print(f"[WS chat] ✅ AI 回复已发给客户 session_id={session_id[:8]}")

            # 广播给商户
            print(f"[WS chat] 准备广播 AI 回复给管理后台 session_id={session_id[:8]}")
            await broadcast_to_all(tenant, {
                "type": "message",
                "session_id": session_id,
                "uid": session.uid or "",
                "customer_name": session.customer_name,
                "role": "ai",
                "content": reply,
                "timestamp": datetime.now().isoformat()
            })
            print(f"[WS chat] ✅ AI 回复已广播给管理后台")

    except WebSocketDisconnect:
        manager.disconnect_customer(session_id)
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session:
            session.status = "closed"
            session.online = False
            session.last_active = datetime.now()
            db.commit()
        await broadcast_to_all(tenant, {
            "type": "session_closed",
            "session_id": session_id,
            "uid": session.uid if session else "",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"[WS chat ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        manager.disconnect_customer(session_id if 'session_id' in locals() else "")
    finally:
        db.close()


@router.websocket("/ws/monitor/{token}")
async def tenant_monitor_ws(websocket: WebSocket, token: str):
    """商户监控 WebSocket"""
    db = SessionLocal()
    await websocket.accept()
    
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "tenant":
            await websocket.close(code=4001, reason="Invalid token")
            return

        tenant = db.query(Tenant).filter(Tenant.id == payload.get("sub")).first()
        if not tenant:
            await websocket.close(code=4004, reason="Tenant not found")
            return

        await manager.connect_tenant_monitor(tenant.id, websocket)

        # 发送初始会话数据
        sessions = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant.id
        ).order_by(ChatSession.last_active.desc()).limit(50).all()
        
        session_list = []
        for s in sessions:
            last_msg = db.query(ChatMessage).filter(
                ChatMessage.session_id == s.session_id
            ).order_by(ChatMessage.created_at.desc()).first()

            session_list.append({
                "session_id": s.session_id,
                "uid": s.uid or "",
                "customer_name": s.customer_name or "访客",
                "online": s.online,
                "is_human_service": s.is_human_service,
                "last_message": last_msg.content[:50] if last_msg else "",
                "last_message_time": s.last_active.isoformat() if s.last_active else None,
            })
        
        await websocket.send_json({
            "type": "init",
            "sessions": session_list,
        })

        # 保持连接，处理心跳
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")

    except WebSocketDisconnect:
        if 'tenant' in locals():
            manager.disconnect_tenant_monitor(tenant.id, websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if 'tenant' in locals():
            manager.disconnect_tenant_monitor(tenant.id, websocket)
    finally:
        db.close()
