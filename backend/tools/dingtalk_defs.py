# dingtalk_defs.py —— 把钉钉群通知注册成模型工具
from backend.tools.dingtalk_tools import dingtalk_send
from backend.tools.registry import register_tool


register_tool({
    "type": "function",
    "function": {
        "name": "dingtalk_send",
        "description": (
            "向配置好的钉钉群机器人发送文本通知。"
            "调用后系统会暂停并等待用户确认，不会立即发送。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "通知正文，最多 4000 字",
                },
                "at_mobiles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "需要 @ 的手机号列表；没有则留空",
                },
                "at_all": {
                    "type": "boolean",
                    "description": "是否 @所有人，默认 false",
                },
            },
            "required": ["text"],
        },
    },
})(dingtalk_send)
