# dingtalk_tools.py —— 钉钉自定义群机器人通知
import base64
import hashlib
import hmac
import os
import time
import urllib.parse

import requests
from dotenv import load_dotenv

load_dotenv()

DINGTALK_WEBHOOK_URL = os.getenv("DINGTALK_WEBHOOK_URL", "").strip()
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "").strip()


def _ensure_config() -> None:
    if not DINGTALK_WEBHOOK_URL:
        raise ValueError("缺少 DINGTALK_WEBHOOK_URL，请检查 .env")
    if not DINGTALK_SECRET:
        raise ValueError("缺少 DINGTALK_SECRET，请检查 .env")


def _signed_webhook_url(webhook_url: str = "",
                        secret: str = "",
                        timestamp: int = None) -> str:
    """
    为钉钉机器人“加签”安全设置生成带 timestamp 和 sign 的 URL。

    钉钉要求：
    1. 使用“毫秒时间戳 + 换行符 + SECRET”计算 HMAC-SHA256。
    2. 对二进制摘要做 Base64，再进行 URL 编码。
    """
    webhook_url = (webhook_url or DINGTALK_WEBHOOK_URL).strip()
    secret = (secret or DINGTALK_SECRET).strip()
    if not webhook_url or not secret:
        raise ValueError("钉钉 Webhook 或加签密钥未配置")

    timestamp = int(timestamp or round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    separator = "&" if "?" in webhook_url else "?"
    return (
        f"{webhook_url}{separator}"
        f"timestamp={timestamp}&sign={sign}"
    )


def dingtalk_send(text: str,
                  at_mobiles: list = None,
                  at_all: bool = False) -> str:
    """向钉钉群发送文本通知，可 @ 指定手机号或 @所有人。"""
    _ensure_config()

    text = str(text or "").strip()
    if not text:
        return "钉钉通知内容为空，未发送。"
    if len(text) > 4000:
        return "钉钉通知内容超过 4000 字，请缩短后重试。"

    mobiles = [
        str(mobile).strip()
        for mobile in (at_mobiles or [])
        if str(mobile).strip()
    ]
    if len(mobiles) > 20:
        return "一次最多 @ 20 个手机号。"

    payload = {
        "msgtype": "text",
        "text": {"content": text},
        "at": {
            "atMobiles": mobiles,
            "isAtAll": bool(at_all),
        },
    }

    response = requests.post(
        _signed_webhook_url(),
        json=payload,
        timeout=10,
    )
    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as exc:
        raise ValueError("钉钉返回内容不是有效 JSON") from exc

    errcode = result.get("errcode")
    if errcode != 0:
        message = result.get("errmsg") or "未知错误"
        raise ValueError(f"钉钉发送失败：errcode={errcode}，errmsg={message}")

    target = "@所有人" if at_all else (
        f"@{'、'.join(mobiles)}" if mobiles else "群消息"
    )
    preview = text.replace("\r", " ").replace("\n", " ")[:80]
    return f"钉钉通知已发送（{target}）：{preview}"
