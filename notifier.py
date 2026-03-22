"""邮件通知模块"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

import markdown


def send_email(report_md: str, config: dict) -> None:
    """
    将Markdown报告转为HTML并通过邮件发送。

    Args:
        report_md: Markdown格式的报告
        config: 配置字典
    """
    email_config = config.get("email", {})

    if not email_config.get("enabled", False):
        print("[Notifier] 邮件通知未启用，跳过")
        return

    smtp_host = email_config.get("smtp_host", "smtp.gmail.com")
    smtp_port = email_config.get("smtp_port", 587)
    sender = email_config.get("sender", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    recipients = email_config.get("recipients", [])
    subject_prefix = email_config.get("subject_prefix", "[Daily Paper]")

    if not sender or not password or not recipients:
        print("[Notifier] 邮件配置不完整（sender/password/recipients），跳过发送")
        return

    # Markdown -> HTML
    html_body = markdown.markdown(
        report_md,
        extensions=["tables", "fenced_code", "codehilite"],
    )

    html_template = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                   max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
            h1 {{ color: #1a1a1a; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
            h2 {{ color: #2c3e50; margin-top: 30px; }}
            h3 {{ color: #34495e; }}
            a {{ color: #3498db; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            blockquote {{ background: #f9f9f9; border-left: 4px solid #3498db;
                         padding: 10px 15px; margin: 10px 0; }}
            details {{ background: #f5f5f5; padding: 10px; border-radius: 4px; margin: 10px 0; }}
            summary {{ cursor: pointer; font-weight: bold; }}
            hr {{ border: none; border-top: 1px solid #e0e0e0; margin: 20px 0; }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"{subject_prefix} {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(report_md, "plain", "utf-8"))
    msg.attach(MIMEText(html_template, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"[Notifier] 邮件已发送至: {', '.join(recipients)}")
    except Exception as e:
        print(f"[Notifier] 邮件发送失败: {e}")
        raise
