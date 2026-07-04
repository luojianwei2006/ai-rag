"""钉钉机器人通知服务

通过钉钉群机器人 Webhook 发送 Markdown 格式的通知消息。
"""

import httpx


async def send_dingtalk_notification(webhook_url: str, title: str, content: str) -> bool:
    """发送钉钉机器人消息（Markdown格式）

    Args:
        webhook_url: 钉钉机器人 Webhook 地址
        title: 消息标题
        content: Markdown 格式的消息内容

    Returns:
        True 表示发送成功，False 表示发送失败
    """
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            result = resp.json()
            return result.get("errcode") == 0
    except Exception as e:
        print(f"[DingTalk] 发送失败: {e}")
        return False
