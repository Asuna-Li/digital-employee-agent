# protocol.py —— 前后端事件协议的唯一权威定义
"""所有 WebSocket 事件名和 REST 路径都从这里引用，避免两边写错字符串。"""

import json

# ---------- 客户端 -> 服务端 ----------
CLIENT_USER_TEXT = "user_text"          # 发送文字
CLIENT_AUDIO_START = "audio_start"      # 开始说话
CLIENT_AUDIO_END = "audio_end"          # 说话结束
CLIENT_CANCEL = "cancel"                # 打断/取消
CLIENT_CONFIRM = "confirm_result"       # 副作用确认结果
CLIENT_MODE_SWITCH = "mode_switch"      # 切换本地/云端
CLIENT_MIC_TOGGLE = "mic_toggle"        # 麦克风开关

# ---------- 服务端 -> 客户端 ----------
SERVER_ASSISTANT_DELTA = "assistant_delta"    # 流式回答片段
SERVER_ASSISTANT_DONE = "assistant_done"      # 回答结束
SERVER_CITATION = "citation"                  # 引用来源
SERVER_TOOL_STATUS = "tool_status"            # 工具状态
SERVER_VOICE_STATE = "voice_state"            # 语音状态
SERVER_MIC_LEVEL = "mic_level"                # 麦克风音量
SERVER_CONFIRM_REQUIRED = "confirm_required"  # 请求确认
SERVER_MODEL_STATUS = "model_status"          # 模型加载状态
SERVER_ERROR = "error"                        # 错误

# ---------- REST 路径 ----------
API_HEALTH = "/api/health"
API_CONFIG = "/api/config"
API_DOCUMENTS = "/api/documents"
API_INDEX_REBUILD = "/api/index/rebuild"
API_MEMORY = "/api/memory"


async def send_event(ws, event: str, **fields):
    """统一发送 JSON 事件，保证中文可读、字段扁平"""
    payload = {"event": event}
    payload.update(fields)
    await ws.send_text(json.dumps(payload, ensure_ascii=False))