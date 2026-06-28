from dotenv import load_dotenv
load_dotenv()

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

log = logging.getLogger(__name__)

TYPE_BADGE = {
    "news":     '<span style="background:rgba(99,102,241,0.15);color:#818cf8;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-left:6px;">🌍 Geo</span>',
    "trending": '<span style="background:rgba(251,191,36,0.15);color:#fbbf24;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-left:6px;">🔥 Trending</span>',
    "x":        '<span style="background:rgba(255,255,255,0.08);color:#aaa;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-left:6px;">𝕏 From X</span>',
}

FORMAT_BADGE = '<span style="background:rgba(232,78,27,0.15);color:#ff6b35;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">{fmt}</span>'
SOURCE_BADGE = '<span style="background:rgba(232,78,27,0.15);color:#ff6b35;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-left:6px;">{src}</span>'


def build_draft_card(draft: dict) -> str:
    char_color = "#ff6b35" if draft["chars"] > 280 else "#444"
    link_html = f'<a href="{draft["link"]}" style="color:#666;font-size:11px;display:block;margin-top:6px;">Read source →</a>' if draft.get("link") else ""

    return f"""
    <div style="background:#111;border:1px solid #222;border-radius:10px;padding:20px;margin-bottom:16px;">
      <div style="margin-bottom:10px;">
        {FORMAT_BADGE.format(fmt=draft['format'])}
        {SOURCE_BADGE.format(src=draft['source'])}
        {TYPE_BADGE.get(draft.get('type', 'news'), '')}
        <span style="color:{char_color};font-size:11px;float:right;">{draft['chars']}/280</span>
      </div>
      <p style="color:#f0ede8;font-size:15px;line-height:1.65;margin:0 0 10px 0;">{draft['text']}</p>
      <p style="color:#444;font-size:11px;margin:0;">Based on: {draft['original_title'][:100]}</p>
      {link_html}
    </div>"""


def build_html(drafts: list) -> str:
    now = datetime.now().strftime("%a, %b %d · %I:%M %p")
    cards = "".join(build_draft_card(d) for d in drafts)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="background:#0a0a0a;color:#f0ede8;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">
    <div style="border-bottom:1px solid #1e1e1e;padding-bottom:20px;margin-bottom:28px;">
      <h1 style="font-size:22px;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;
                 background:linear-gradient(90deg,#e84e1b,#ff6b35);-webkit-background-clip:text;
                 -webkit-text-fill-color:transparent;margin:0 0 4px 0;">Secret Feeds</h1>
      <p style="color:#444;font-size:12px;margin:0;">Draft Drop · {now}</p>
    </div>
    <p style="color:#666;font-size:13px;margin:0 0 24px 0;">
      Here are your {len(drafts)} ready-to-post drafts. Copy, review, and post to X.
    </p>
    {cards}
    <div style="border-top:1px solid #1e1e1e;padding-top:20px;margin-top:28px;">
      <p style="color:#333;font-size:11px;margin:0;">
        Sent automatically by Secret Feeds Bot · Next drop in 30 minutes
      </p>
    </div>
  </div>
</body>
</html>"""


def send_email(drafts: list):
    sender   = os.getenv("EMAIL_FROM")
    password = os.getenv("EMAIL_APP_PASSWORD")
    receiver = os.getenv("EMAIL_TO")

    if not all([sender, password, receiver]):
        raise ValueError("EMAIL_FROM, EMAIL_APP_PASSWORD, and EMAIL_TO must all be set in .env")

    now = datetime.now().strftime("%b %d, %I:%M %p")
    subject = f"🌍 {len(drafts)} New Secret Feeds Drafts — {now}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Secret Feeds Bot <{sender}>"
    msg["To"]      = receiver

    msg.attach(MIMEText(build_html(drafts), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    log.info(f"📧 Email sent to {receiver}")
