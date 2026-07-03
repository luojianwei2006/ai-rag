"""
嵌入监控路由：供第三方平台通过 iframe 嵌入实时监控页面。
通过 embed_api_key 验证身份，无需登录。
"""
import json
import asyncio
from typing import Dict, Set, List
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload
from database import get_db, SessionLocal
from models.models import Tenant, ChatSession, ChatMessage
from datetime import datetime, timezone

from pydantic import BaseModel

# 嵌入监控多语言文案
EMBED_I18N = {
    "zh": {
        "taken_over_sys": "人工客服已接管会话",
        "taken_over_notify": "人工客服已接管，将为您服务",
        "released_sys": "人工客服已释放会话",
        "released_notify": "人工客服已结束对话",
    },
    "en": {
        "taken_over_sys": "Human agent has taken over the session",
        "taken_over_notify": "Human agent has taken over, will serve you",
        "released_sys": "Human agent has released the session",
        "released_notify": "Human agent has ended the conversation",
    },
}

router = APIRouter(tags=["嵌入监控"])

class SendMessageRequest(BaseModel):
    session_id: str
    content: str


# ─── 嵌入监控 WebSocket 连接管理 ───

class EmbedConnectionManager:
    def __init__(self):
        # api_key -> Set[WebSocket]
        self.embed_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, api_key: str, ws: WebSocket):
        await ws.accept()
        if api_key not in self.embed_connections:
            self.embed_connections[api_key] = set()
        self.embed_connections[api_key].add(ws)

    def disconnect(self, api_key: str, ws: WebSocket):
        if api_key in self.embed_connections:
            self.embed_connections[api_key].discard(ws)

    async def broadcast(self, api_key: str, message: dict):
        """向该 api_key 对应的所有嵌入连接广播"""
        connections = self.embed_connections.get(api_key, set())
        disconnected = set()
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            connections.discard(ws)


embed_manager = EmbedConnectionManager()


def get_tenant_by_embed_key(api_key: str, db: Session) -> Tenant:
    """通过 embed_api_key 查找商户"""
    tenant = db.query(Tenant).filter(
        Tenant.embed_api_key == api_key,
        Tenant.is_active == True
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="无效的 API Key")
    return tenant


@router.get("/api/embed/info")
async def get_embed_info(api_key: str, db: Session = Depends(get_db)):
    """获取嵌入监控信息（第三方通过 api_key 访问）"""
    tenant = get_tenant_by_embed_key(api_key, db)
    
    # 获取最近会话列表
    sessions = db.query(ChatSession).filter(
        ChatSession.tenant_id == tenant.id
    ).order_by(ChatSession.last_active.desc()).limit(50).all()
    
    session_list = []
    for s in sessions:
        # 查询最后一条消息
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
    
    return {
        "tenant_id": tenant.id,
        "company_name": tenant.company_name or "在线客服",
        "avatar_url": tenant.avatar_url or None,
        "sessions": session_list,
    }


@router.get("/api/embed/messages")
async def get_embed_messages(
    api_key: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """获取指定会话的消息历史（第三方通过 api_key 访问）"""
    tenant = get_tenant_by_embed_key(api_key, db)
    
    # 验证会话属于该商户
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).limit(200).all()
    
    message_list = []
    for m in messages:
        message_list.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    
    return {
        "session_id": session_id,
        "messages": message_list,
    }


@router.post("/api/embed/send_message")
async def send_embed_message(
    request: SendMessageRequest,
    api_key: str,
    db: Session = Depends(get_db)
):
    """从嵌入监控端发送消息（人工客服回复）"""
    tenant = get_tenant_by_embed_key(api_key, db)

    # 验证会话属于该商户
    session = db.query(ChatSession).filter(
        ChatSession.session_id == request.session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 标记为已接管
    session.taken_over = True
    session.is_human_service = True

    # 保存消息
    message = ChatMessage(
        session_id=request.session_id,
        role="human_agent",
        content=request.content
    )
    db.add(message)

    # 更新会话的最后消息
    last_msg = db.query(ChatMessage).filter(
        ChatMessage.session_id == request.session_id
    ).order_by(ChatMessage.created_at.desc()).first()
    session.last_active = last_msg.created_at if last_msg else datetime.now(timezone.utc)

    db.commit()

    # 客户通过轮询获取消息，无需推送

    # 通知嵌入监控端
    try:
        await embed_manager.broadcast(tenant.embed_api_key, {
            "type": "message",
            "session_id": request.session_id,
            "role": "human_agent",
            "content": request.content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception:
        pass

    return {"success": True, "message": "消息已发送"}


@router.post("/api/embed/takeover")
async def takeover_session(
    api_key: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """接管会话（标记为已接管）"""
    tenant = get_tenant_by_embed_key(api_key, db)
    
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session.taken_over = True
    session.is_human_service = True
    
    # 多语言文案
    lang = tenant.chat_language or "zh"
    i18n = EMBED_I18N.get(lang, EMBED_I18N["zh"])
    
    # 保存系统消息
    takeover_msg = ChatMessage(
        session_id=session_id,
        role="system",
        content=i18n["taken_over_sys"]
    )
    db.add(takeover_msg)
    db.commit()

    # 客户通过轮询获取消息，无需推送

    # 通知嵌入监控端
    try:
        await embed_manager.broadcast(tenant.embed_api_key, {
            "type": "taken_over",
            "session_id": session_id,
            "role": "system",
            "content": i18n["taken_over_sys"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception:
        pass

    return {"success": True, "message": "已接管会话"}


@router.post("/api/embed/release")
async def release_session(
    api_key: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """释放会话（取消接管）"""
    tenant = get_tenant_by_embed_key(api_key, db)
    
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session.taken_over = False
    
    # 多语言文案
    lang = tenant.chat_language or "zh"
    i18n = EMBED_I18N.get(lang, EMBED_I18N["zh"])
    
    # 保存系统消息
    release_msg = ChatMessage(
        session_id=session_id,
        role="system",
        content=i18n["released_sys"]
    )
    db.add(release_msg)
    db.commit()

    # 客户通过轮询获取消息，无需推送

    # 通知嵌入监控端
    try:
        await embed_manager.broadcast(tenant.embed_api_key, {
            "type": "released",
            "session_id": session_id,
            "role": "system",
            "content": i18n["released_sys"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception:
        pass

    return {"success": True, "message": "已释放会话"}


@router.websocket("/ws/embed/monitor")
async def embed_monitor_ws(websocket: WebSocket):
    """嵌入监控 WebSocket（第三方嵌入页面使用）"""
    db = SessionLocal()
    api_key = None
    try:
        params = dict(websocket.query_params)
        api_key = params.get("api_key", "")
        if not api_key:
            await websocket.close(code=4001, reason="缺少 api_key")
            return

        tenant = db.query(Tenant).filter(
            Tenant.embed_api_key == api_key,
            Tenant.is_active == True
        ).first()
        if not tenant:
            await websocket.close(code=4001, reason="无效的 api_key")
            return

        await embed_manager.connect(api_key, websocket)

        # 发送初始数据：会话列表
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
        if api_key:
            embed_manager.disconnect(api_key, websocket)
    except Exception:
        if api_key:
            embed_manager.disconnect(api_key, websocket)
    finally:
        db.close()


def notify_embed_monitors(tenant_id: int, message: dict, db: Session):
    """通知嵌入监控端（从 chat.py 调用）
    
    需要在 chat.py 的 WebSocket 消息处理中调用此函数，
    把新的消息/会话事件推送给嵌入监控端。
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.embed_api_key:
        return
    try:
        asyncio.create_task(
            embed_manager.broadcast(tenant.embed_api_key, message)
        )
    except Exception:
        pass
