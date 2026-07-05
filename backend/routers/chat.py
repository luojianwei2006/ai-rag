import json
import os
import uuid
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models.models import Tenant, KnowledgeBase, ChatSession, ChatMessage, FaqCategory, FaqItem
from utils.security import get_current_tenant, decode_token
from utils.crypto import encrypt_chat_params, decrypt_chat_params
from services.rag_service import query_knowledge_base
from services.llm_service import call_llm, get_tenant_llm_config, LLMError
from services.points_service import PointsService
from routers.embed import embed_manager
from config import settings

router = APIRouter(tags=["聊天"])

# ─────── 常量 ───────

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

HUMAN_KEYWORDS = [
    "人工", "人工客服", "转人工", "真人", "真人客服",
    "找人工", "要人工", "接人工", "帮我找人", "人工服务"
]

# ─────── 在线状态 ───────
_customer_online: Dict[str, float] = {}  # session_id -> last_poll_ts

def is_session_online(session_id: str) -> bool:
    last = _customer_online.get(session_id)
    return last and (datetime.now().timestamp() - last) < 30

def mark_session_online(session_id: str):
    _customer_online[session_id] = datetime.now().timestamp()


def _format_message(m) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "msg_type": m.msg_type or "text",
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None
    }


# ─────── 商户管理接口 ───────

class HumanReplyRequest(BaseModel):
    session_id: str
    content: str


@router.get("/api/chat/sessions")
async def get_chat_sessions(
    uid: str = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取商户的所有会话"""
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
            "online": is_session_online(s.session_id)
        })

    # 合并相同 uid
    uid_map = {}
    merged = []
    for item in result:
        key = item.get("uid") or item["session_id"]
        if key not in uid_map:
            uid_map[key] = item
            item["all_session_ids"] = [item["session_id"]]
            merged.append(item)
        else:
            uid_map[key]["all_session_ids"].append(item["session_id"])
            if item.get("created_at") and uid_map[key].get("created_at") \
               and item["created_at"] > uid_map[key]["created_at"]:
                item["all_session_ids"] = uid_map[key]["all_session_ids"]
                uid_map[key] = item
                merged[-1] = item

    return merged


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

    return [_format_message(m) for m in messages]


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

    config = PointsService.get_config(db)
    cost = config.get("human_reply_cost", 1)

    if tenant.points_balance < cost:
        raise HTTPException(status_code=400,
            detail=f"积分不足，人工回复需要 {cost} 点，当前余额: {tenant.points_balance} 点")

    # 保存消息到数据库
    msg = ChatMessage(session_id=req.session_id, role="human_agent", content=req.content)
    db.add(msg)
    db.commit()

    PointsService.deduct_points(db, tenant.id, cost, "human_reply",
        description="人工客服回复", related_id=req.session_id)

    # 飞书/企业微信发送（使用原有逻辑）
    if session.customer_ip == "feishu" or session.session_id.startswith("feishu_"):
        from services.feishu_service import FeishuService
        open_id = session.customer_name.replace("feishu:", "") if session.customer_name else None
        if open_id and tenant.feishu_app_id and tenant.feishu_app_secret:
            feishu = FeishuService(tenant.feishu_app_id, tenant.feishu_app_secret)
            await feishu.send_text_message(open_id, req.content)

    elif session.customer_ip == "wecom" or session.session_id.startswith("wecom_"):
        from services.wecom_service import WeComService
        user_id = session.customer_name.replace("wecom:", "") if session.customer_name else None
        if user_id and tenant.wecom_corp_id and tenant.wecom_agent_id and tenant.wecom_secret:
            wecom = WeComService(corp_id=tenant.wecom_corp_id,
                                agent_id=tenant.wecom_agent_id, secret=tenant.wecom_secret)
            await wecom.send_text_message(user_id, req.content)

    # 推送嵌入监控（如果存在）
    if tenant.embed_api_key:
        try:
            await embed_manager.broadcast(tenant.embed_api_key, {
                "type": "message", "session_id": req.session_id,
                "uid": session.uid or "", "role": "human_agent",
                "content": req.content, "timestamp": datetime.now().isoformat()
            })
        except Exception:
            pass

    return {"message": "发送成功", "points_deducted": cost}


# ─────── 客户端公开接口 ───────

@router.get("/api/public/chat/{chat_token}/info")
async def get_chat_info(chat_token: str, db: Session = Depends(get_db)):
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


@router.post("/api/public/chat/upload-image")
async def upload_chat_image(chat_token: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
        raise HTTPException(status_code=400, detail="仅支持图片格式")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "chat_images", str(tenant.id))
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/static/chat_images/{tenant.id}/{filename}"}


# ─────── 公开 FAQ 接口 ───────

@router.get("/api/public/chat/{chat_token}/faq")
async def get_public_faq(chat_token: str, db: Session = Depends(get_db)):
    """获取商户 FAQ（客户端使用）"""
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")

    categories = db.query(FaqCategory).filter(
        FaqCategory.tenant_id == tenant.id
    ).order_by(FaqCategory.sort_order).all()

    lang = tenant.chat_language or "zh"
    result = []
    for cat in categories:
        items = db.query(FaqItem).filter(
            FaqItem.category_id == cat.id,
            FaqItem.tenant_id == tenant.id
        ).order_by(FaqItem.sort_order).all()

        result.append({
            "id": cat.id,
            "name": cat.name_en if lang == "en" and cat.name_en else cat.name_zh,
            "items": [{
                "id": it.id,
                "question": it.question_en if lang == "en" and it.question_en else it.question_zh,
                "answer": it.answer_en if lang == "en" and it.answer_en else it.answer_zh,
            } for it in items]
        })
    return {
        "has_faq": len(result) > 0,
        "categories": result
    }


# ─────── 客户端会话 & 消息接口（替代 WebSocket）───────

class StartSessionRequest(BaseModel):
    uid: str = ""
    nickname: str = ""
    p: str = ""  # 加密参数 p，解密后取得 uid 和 nickname

class SendMessageRequest(BaseModel):
    session_id: str
    content: str
    msg_type: str = "text"


@router.post("/api/public/chat/{chat_token}/start")
async def start_chat_session(
    chat_token: str,
    req: StartSessionRequest,
    db: Session = Depends(get_db),
    tenant_db: Session = Depends(get_db)
):
    """创建或复用会话，返回 session_id + 历史消息"""
    from fastapi import Request
    # 这里重新查 tenant，因为两个 db 参数是同一个
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")

    lang = tenant.chat_language or "zh"
    i18n = CHAT_I18N.get(lang, CHAT_I18N["zh"])

    # 解析 uid 和 nickname：优先解密 p 参数
    uid = req.uid
    nickname = req.nickname or "访客"
    if req.p:
        try:
            decrypt_key = tenant.embed_api_key or None
            decrypted = decrypt_chat_params(req.p, key=decrypt_key)
            uid = decrypted.get("uid") or uid
            nickname = decrypted.get("nickname") or nickname
        except Exception:
            try:
                decrypted = decrypt_chat_params(req.p, key=None)
                uid = decrypted.get("uid") or uid
                nickname = decrypted.get("nickname") or nickname
            except Exception:
                pass

    # 如果有 uid，复用最近的 active 会话
    session_id = None
    existing_session = None
    if uid:
        existing_session = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant.id,
            ChatSession.uid == uid,
            ChatSession.status == "active"
        ).order_by(ChatSession.created_at.desc()).first()

    if existing_session:
        # 复用现有会话
        session_id = existing_session.session_id
        session = existing_session
        session.online = True
        session.last_active = datetime.now()
        db.commit()
        print(f"[start] 🔄 复用会话 uid={uid} session_id={session_id[:8]}")
    else:
        # 创建新会话
        session_id = secrets.token_urlsafe(16)
        session = ChatSession(
            tenant_id=tenant.id,
            session_id=session_id,
            uid=uid or None,
            customer_name=nickname,
            customer_ip="rest",
            status="active",
            online=True,
            last_active=datetime.now()
        )
        db.add(session)
        db.commit()

        # 异步发送钉钉通知（不阻塞主流程）
        if tenant.dingtalk_webhook:
            try:
                from services.dingtalk_service import send_dingtalk_notification
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                markdown_text = (
                    f"## 🔔 新的客服咨询\n\n"
                    f"**客户昵称**：{nickname}\n"
                    f"**咨询时间**：{time_str}\n"
                    f"**会话ID**：{session_id}\n\n"
                    f"[查看详情](https://kefu.zenithgames.com/tenant/monitor)"
                )
                asyncio.create_task(
                    send_dingtalk_notification(tenant.dingtalk_webhook, "新的客服咨询", markdown_text, tenant.dingtalk_secret)
                )
            except Exception as e:
                print(f"[DingTalk] 创建通知任务失败: {e}")

        # 首次创建：发送欢迎消息
        if tenant.ai_enabled:
            welcome = i18n["welcome"]
            welcome_msg = ChatMessage(session_id=session_id, role="ai", content=welcome)
            db.add(welcome_msg)
            db.commit()
        else:
            offline_msg = "您好，AI客服已关闭，将由人工客服为您服务。"
            if lang == "en":
                offline_msg = "Hello, AI assistant is currently unavailable. A human agent will assist you shortly."
            ChatMessage(session_id=session_id, role="system", content=offline_msg)
            db.add(ChatMessage(session_id=session_id, role="system", content=offline_msg))
            db.commit()

        print(f"[start] 🆕 新会话 uid={uid} session_id={session_id[:8]}")

    mark_session_online(session_id)

    # 加载历史消息（该 uid 下所有会话，跨 session 加载）
    history = []
    if uid:
        all_sessions = db.query(ChatSession).filter(
            ChatSession.tenant_id == tenant.id,
            ChatSession.uid == uid
        ).all()
        all_sids = [s.session_id for s in all_sessions]
        if all_sids:
            history_msgs = db.query(ChatMessage).filter(
                ChatMessage.session_id.in_(all_sids)
            ).order_by(ChatMessage.created_at.asc()).all()
            history = [_format_message(m) for m in history_msgs]

    return {
        "session_id": session_id,
        "ai_enabled": tenant.ai_enabled,
        "history": history
    }


@router.post("/api/public/chat/{chat_token}/send")
async def send_chat_message(
    chat_token: str,
    req: SendMessageRequest,
    db: Session = Depends(get_db)
):
    """发送消息并获取 AI 回复（REST 接口，替代 WebSocket）"""
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")

    lang = tenant.chat_language or "zh"
    i18n = CHAT_I18N.get(lang, CHAT_I18N["zh"])

    session = db.query(ChatSession).filter(
        ChatSession.session_id == req.session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    session_id = req.session_id
    content = req.content.strip()
    msg_type = req.msg_type

    if not content:
        raise HTTPException(status_code=400, detail="消息不能为空")

    mark_session_online(session_id)

    # 1. 保存客户消息
    user_msg = ChatMessage(session_id=session_id, role="customer", msg_type=msg_type, content=content)
    db.add(user_msg)
    db.commit()

    # 2. 检查是否请求人工
    is_human_request = any(kw in content for kw in HUMAN_KEYWORDS)
    if is_human_request and not session.is_human_service:
        session.is_human_service = True
        session.status = "human"
        db.commit()

        transfer_msg = i18n["transfer_human"]
        ChatMessage(session_id=session_id, role="ai", content=transfer_msg)
        db.add(ChatMessage(session_id=session_id, role="ai", content=transfer_msg))
        db.commit()

        return {
            "reply": {"role": "system", "content": transfer_msg, "msg_type": "text"},
            "is_human": True
        }

    if session.is_human_service:
        return {"reply": None, "is_human": True}  # 人工模式，等人工回复

    # 3. AI 回复
    if not tenant.ai_enabled:
        return {"reply": None, "is_human": False}

    try:
        config = PointsService.get_config(db)
        cost = config.get("ai_reply_cost", 5)

        if tenant.points_balance < cost:
            reply = i18n["points_low"].format(balance=tenant.points_balance)
        else:
            # 知识库检索
            kbs = db.query(KnowledgeBase).filter(
                KnowledgeBase.tenant_id == tenant.id,
                KnowledgeBase.status == "ready"
            ).all()

            context = ""
            if kbs:
                all_docs = []
                for kb in kbs:
                    docs = query_knowledge_base(tenant.id, kb.id, content, n_results=3)
                    all_docs.extend(docs)
                context = "\n".join(all_docs[:10])

            # 历史消息
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
                    lang_instruction = ""
                    if lang == "en":
                        lang_instruction = "\n\nYou MUST respond in English."
                    reply = await call_llm(model, api_keys, history, context, system_prompt=None, lang_instruction=lang_instruction)
                except LLMError:
                    reply = i18n["ai_error"]
                else:
                    PointsService.deduct_points(db, tenant.id, cost, "ai_reply",
                        description="AI客服回答（网页）", related_id=session_id)

    except Exception:
        reply = i18n["process_error"]

    # 4. 保存 AI 回复
    ai_msg = ChatMessage(session_id=session_id, role="ai", content=reply)
    db.add(ai_msg)
    db.commit()

    # 5. 钉钉限流通知：30分钟内同一会话只通知一次
    if tenant.dingtalk_webhook and not session.is_human_service:
        now = datetime.now()
        should_notify = (
            session.last_dingtalk_notify is None
            or (now - session.last_dingtalk_notify) > timedelta(minutes=30)
        )
        if should_notify:
            try:
                session.last_dingtalk_notify = now
                db.commit()

                from services.dingtalk_service import send_dingtalk_notification

                customer_name = session.customer_name or "访客"
                time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                msg_preview = content[:20] + ("..." if len(content) > 20 else "")
                markdown_text = (
                    f"## 💬 新的客服消息\n\n"
                    f"**客户**：{customer_name}\n"
                    f"**消息**：{msg_preview}\n"
                    f"**时间**：{time_str}\n\n"
                    f"[查看详情](https://kefu.zenithgames.com/tenant/monitor)"
                )
                asyncio.create_task(
                    send_dingtalk_notification(
                        tenant.dingtalk_webhook, "新的客服消息", markdown_text, tenant.dingtalk_secret
                    )
                )
            except Exception as e:
                print(f"[DingTalk] 限流通知失败: {e}")

    return {
        "reply": {"role": "ai", "content": reply, "msg_type": "text"},
        "is_human": False
    }


@router.get("/api/public/chat/{chat_token}/poll")
async def poll_chat_messages(
    chat_token: str,
    session_id: str,
    after_id: int = 0,
    db: Session = Depends(get_db)
):
    """轮询新消息（客户端获取新的人工回复/AI消息）"""
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")

    mark_session_online(session_id)

    # 查询 after_id 之后的新消息（排除客户自己发的）
    query = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id,
        ChatMessage.id > after_id,
        ChatMessage.role != "customer"
    ).order_by(ChatMessage.created_at.asc())

    new_msgs = query.all()
    return [_format_message(m) for m in new_msgs]
