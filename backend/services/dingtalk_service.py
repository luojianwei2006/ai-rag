"""钉钉机器人通知服务

通过钉钉群机器人 Webhook 发送通知消息。
支持加签（HMAC-SHA256）安全方式。
"""

import time
import hmac
import hashlib
import base64
import urllib.parse

import httpx


async def send_dingtalk_notification(webhook_url: str, title: str, content: str, secret: str = None, msgtype: str = "text") -> bool:
    """发送钉钉机器人消息

    支持钉钉加签安全方式：
    - 如果提供了 secret，自动计算签名并拼接到 Webhook URL
    - 如果没有 secret，直接使用原 URL 发送

    Args:
        webhook_url: 钉钉机器人 Webhook 地址
        title: 消息标题（markdown类型时使用）
        content: 消息内容
        secret: 钉钉机器人加签密钥（可选）
        msgtype: 消息类型，默认 text（纯文本），也可传 markdown

    Returns:
        True 表示发送成功，False 表示发送失败
    """
    # 如果提供了加签密钥，计算签名并拼接 URL
    if secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    if msgtype == "markdown":
        payload = {"msgtype": "markdown", "markdown": {"title": title, "text": content}}
    else:
        payload = {"msgtype": "text", "text": {"content": content}}

    try:
        print(f"[DingTalk] 发送消息到: {webhook_url[:60]}...")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            result = resp.json()
            print(f"[DingTalk] 响应: {result}")
            ok = result.get("errcode") == 0
            if not ok:
                print(f"[DingTalk] 发送失败: {result.get('errmsg', '未知错误')}")
            return ok
    except Exception as e:
        print(f"[DingTalk] 发送异常: {e}")
        return False
