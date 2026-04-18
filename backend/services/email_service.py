import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from sqlalchemy.orm import Session
from models.models import SystemConfig


def get_smtp_config(db: Session) -> dict:
    """从数据库读取SMTP配置"""
    configs = db.query(SystemConfig).filter(
        SystemConfig.key.in_(["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from", "smtp_tls"])
    ).all()
    return {c.key: c.value for c in configs}


async def send_email(
    db: Session,
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> tuple[bool, str]:
    """发送邮件，返回 (success, message)"""
    config = get_smtp_config(db)

    required_keys = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from"]
    for key in required_keys:
        if not config.get(key):
            return False, f"SMTP配置不完整，缺少 {key}"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["smtp_from"]
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        port = int(config["smtp_port"])
        use_tls = config.get("smtp_tls", "true").lower() == "true"

        if use_tls and port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config["smtp_host"], port, context=context) as server:
                server.login(config["smtp_user"], config["smtp_password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(config["smtp_host"], port) as server:
                if use_tls:
                    server.starttls()
                server.login(config["smtp_user"], config["smtp_password"])
                server.send_message(msg)

        return True, "邮件发送成功"
    except Exception as e:
        return False, f"邮件发送失败: {str(e)}"


async def send_password_email(db: Session, to_email: str, password: str, company_name: str = "") -> tuple[bool, str]:
    """发送密码邮件给新注册商户"""
    subject = "您的客服平台账户信息"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0;">🎉 欢迎加入客服平台</h1>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eee;">
            <p>您好，{company_name or '商户'}！</p>
            <p>您的账户已成功创建，以下是您的登录信息：</p>
            <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; margin: 20px 0;">
                <p><strong>登录邮箱：</strong>{to_email}</p>
                <p><strong>初始密码：</strong><span style="font-size: 18px; color: #764ba2; font-weight: bold;">{password}</span></p>
            </div>
            <p style="color: #666;">⚠️ 请登录后立即修改密码，保障账户安全。</p>
            <p style="color: #666; font-size: 12px;">如有疑问，请联系平台管理员。</p>
        </div>
    </body>
    </html>
    """
    return await send_email(db, to_email, subject, html_content)


async def send_reset_password_email(db: Session, to_email: str, new_password: str) -> tuple[bool, str]:
    """发送密码重置邮件"""
    subject = "您的密码已重置"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0;">🔐 密码重置通知</h1>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eee;">
            <p>您好！</p>
            <p>您的账户密码已被重置，新密码如下：</p>
            <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #f5576c; margin: 20px 0;">
                <p><strong>新密码：</strong><span style="font-size: 18px; color: #f5576c; font-weight: bold;">{new_password}</span></p>
            </div>
            <p style="color: #666;">⚠️ 请立即登录并修改密码！</p>
        </div>
    </body>
    </html>
    """
    return await send_email(db, to_email, subject, html_content)
