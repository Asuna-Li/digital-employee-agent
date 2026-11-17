# email_defs.py —— 把 QQ 邮件函数注册成模型可调用工具
from backend.tools.registry import register_tool
from backend.tools.email_tools import email_search, email_read, email_send

register_tool({
    "type": "function",
    "function": {
        "name": "email_search",
        "description": "搜索 QQ 邮箱最近邮件，返回编号、日期、发件人、主题",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "关键词，匹配发件人或主题；留空列出最近邮件",
                },
                "max_count": {
                    "type": "integer",
                    "description": "最多返回多少封，默认 5",
                },
            },
            "required": [],
        },
    },
})(email_search)

register_tool({
    "type": "function",
    "function": {
        "name": "email_read",
        "description": "读取指定编号邮件的完整内容，编号来自 email_search",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "邮件编号"},
            },
            "required": ["uid"],
        },
    },
})(email_read)

register_tool({
    "type": "function",
    "function": {
        "name": "email_send",
        "description": (
            "发送 QQ 邮件，可选附件。调用后系统会暂停并等待用户确认，"
            "不会立即发送。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "收件人邮箱"},
                "subject": {"type": "string", "description": "邮件主题"},
                "body": {"type": "string", "description": "邮件正文"},
                "attachment_file": {
                    "type": "string",
                    "description": "附件文件名，仅限 data/reports 或 data/approvals；不需要留空",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
})(email_send)
