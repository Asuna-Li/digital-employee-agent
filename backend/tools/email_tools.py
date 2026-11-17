# email_tools.py —— QQ 邮箱工具（IMAP 收信 + SMTP 发信）
import imaplib
import mimetypes
import os
import re
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parseaddr

from dotenv import load_dotenv

load_dotenv()

QQ_EMAIL = os.getenv("QQ_EMAIL", "")
QQ_AUTH_CODE = os.getenv("QQ_AUTH_CODE", "")
IMAP_HOST = "imap.qq.com"
SMTP_HOST = "smtp.qq.com"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ATTACHMENT_DIRS = [
    os.path.join(BASE_DIR, "data", "reports"),
    os.path.join(BASE_DIR, "data", "approvals"),
]


def _ensure_config():
    if not QQ_EMAIL or not QQ_AUTH_CODE:
        raise ValueError("缺少 QQ_EMAIL 或 QQ_AUTH_CODE，请检查 .env")


def _imap():
    """建立 IMAP 连接，收件箱只读打开"""
    _ensure_config()
    conn = imaplib.IMAP4_SSL(IMAP_HOST, 993)
    conn.login(QQ_EMAIL, QQ_AUTH_CODE)
    conn.select("INBOX", readonly=True)
    return conn


def _decode(value: str) -> str:
    """解码邮件头"""
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for text, charset in parts:
        if isinstance(text, bytes):
            result.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(text)
    return "".join(result)


def _get_body(msg) -> str:
    """提取正文：优先纯文本，其次 HTML 去标签"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                return re.sub(r"<[^>]+>", " ", text).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace").strip()
    return "(无正文)"


def email_search(keyword: str = "", max_count: int = 10) -> str:
    """搜索最近邮件，按时间由近到远返回编号、日期、发件人、主题"""
    conn = _imap()
    try:
        _, data = conn.uid("search", None, "ALL")
        all_uids = (data[0] or b"").split()
        recent = all_uids[-max(1, int(max_count)):]

        lines = []
        kw = (keyword or "").strip().lower()

        for raw_uid in reversed(recent):
            uid = raw_uid.decode()
            _, msg_data = conn.uid("fetch", uid, "(RFC822)")
            if not msg_data or msg_data[0] is None:
                continue

            msg = __import__("email").message_from_bytes(msg_data[0][1])
            sender = _decode(parseaddr(_decode(msg.get("From", "")))[1])
            subject = _decode(msg.get("Subject", ""))
            date = _decode(msg.get("Date", ""))

            haystack = f"{sender} {subject}".lower()
            if kw and kw not in haystack:
                continue

            lines.append(f"编号:{uid} | {date} | 发件人:{sender} | 主题:{subject}")

        if not lines:
            return f"最近 {len(recent)} 封邮件里没有匹配“{keyword}”的结果"
        return "收件箱邮件：\n" + "\n".join(lines)
    finally:
        conn.logout()


def email_read(uid: str) -> str:
    """读取某封邮件的完整内容"""
    conn = _imap()
    try:
        _, msg_data = conn.uid("fetch", str(uid), "(RFC822)")
        if not msg_data or msg_data[0] is None:
            return f"找不到编号 {uid} 的邮件"

        msg = __import__("email").message_from_bytes(msg_data[0][1])
        sender = _decode(msg.get("From", ""))
        date = _decode(msg.get("Date", ""))
        subject = _decode(msg.get("Subject", ""))
        body = _get_body(msg)

        return (f"发件人: {sender}\n日期: {date}\n主题: {subject}\n"
                f"----------------\n正文:\n{body}")
    finally:
        conn.logout()


def _resolve_attachment(attachment_file: str):
    """附件只允许来自 data/reports 或 data/approvals"""
    if not attachment_file:
        return None
    name = os.path.basename(str(attachment_file).replace("\\", "/"))
    for folder in ATTACHMENT_DIRS:
        candidate = os.path.join(folder, name)
        if os.path.exists(candidate):
            return candidate
    raise ValueError("附件不存在：只允许 data/reports 或 data/approvals 下的文件")


def email_send(to: str, subject: str, body: str,
               attachment_file: str = "") -> str:
    """发送 QQ 邮件，可选附件"""
    _ensure_config()
    attachment_path = _resolve_attachment(attachment_file)

    msg = EmailMessage()
    msg["From"] = QQ_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment_path:
        with open(attachment_path, "rb") as f:
            data = f.read()
        ctype, _ = mimetypes.guess_type(attachment_path)
        if ctype and "/" in ctype:
            maintype, subtype = ctype.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(
            data, maintype=maintype, subtype=subtype,
            filename=os.path.basename(attachment_path),
        )

    with smtplib.SMTP_SSL(SMTP_HOST, 465) as server:
        server.login(QQ_EMAIL, QQ_AUTH_CODE)
        server.send_message(msg)

    return (f"邮件已发送至 {to}，主题：{subject}，"
            f"附件：{os.path.basename(attachment_path) if attachment_path else '无'}")
