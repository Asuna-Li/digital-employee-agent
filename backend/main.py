# main.py —— 本地服务骨架：REST + WebSocket + 假数据流式回答
"""阶段 1 目标：不接真实模型，也能把客户端事件链路完整跑通。"""

import asyncio
import uuid
import os
import time
from backend.memory_store import (
    append_message, get_recent_messages,
)

from fastapi import File, Form, UploadFile
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from backend import protocol as P
# from backend.rag.knowledge import answer
from backend.llm.router import generate_answer
from backend.voice.asr import transcribe_file
from backend.memory_vectors import remember_turn

app = FastAPI(title="个人知识问答 Agent - 骨架版")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_TMP = os.path.join(BASE_DIR, "data", "tmp")
os.makedirs(VOICE_TMP, exist_ok=True)

CONFIG = {
    "mode": "local",                 # local / cloud
    "cloud_enabled": False,          # 云端开关
    "docs_dir": "D:/my-agent/docs",
    "local_model": "qwen2.5-7b-awq",
    "embedding_model": "bge-m3",
}

DOCUMENTS = [
    {"file_name": "company.txt", "status": "indexed", "pages": 1},
    {"file_name": "员工手册.pdf", "status": "indexed", "pages": 120},
]


@app.get(P.API_HEALTH)
async def health():
    """健康检查：客户端启动时先调用它"""
    return {"status": "ok", "model_state": "unloaded", "vram_gb": 0.0}


@app.get(P.API_CONFIG)
async def get_config():
    """读取当前配置"""
    return CONFIG


@app.put(P.API_CONFIG)
async def update_config(payload: dict = Body(...)):
    """更新配置：只允许已知字段，防止误写"""
    for key in ("mode", "cloud_enabled", "docs_dir",
                "local_model", "embedding_model"):
        if key in payload:
            CONFIG[key] = payload[key]
    return CONFIG


@app.get(P.API_DOCUMENTS)
async def list_documents():
    """返回文档与索引状态"""
    return {"documents": DOCUMENTS}


@app.post(P.API_INDEX_REBUILD)
async def rebuild_index():
    """阶段 1 只返回占位结果，阶段 2 接真实入库"""
    return {"status": "accepted", "message": "骨架版：索引重建接口已就绪"}


@app.get(P.API_MEMORY)
async def memory_view():
    """查看本地记忆与云端脱敏摘要"""
    return {
        "local": ["用户偏好：回答要简洁"],
        "cloud_sanitized": ["用户咨询过流程类问题"],
    }


# def _fake_answer(text: str, mode: str) -> str:
#     """生成一段假回答，用来验证流式与状态机"""
#     mode_cn = "本地隐私模式" if mode == "local" else "云端增强模式"
#     return (
#         f"这是骨架版回答，后端已收到：{text}。"
#         f"当前运行在{mode_cn}。真实接入后，这里会由 RAG 检索结果生成，"
#         "并附带文件名、页码和命中片段。"
#     )


def _remember_turn_safe(user_text: str, assistant_text: str,
                        owner: str, session_id: str,
                        privacy_scope: str):
    """后台写入长期记忆；任何异常只记录，不影响主流程"""
    try:
        saved = remember_turn(user_text, assistant_text, owner,
                             session_id, privacy_scope)
        print(f"[记忆] 长期记忆写入完成，新增 {len(saved)} 条")
    except Exception as e:
        print(f"[记忆] 长期记忆写入失败：{e}")


async def _stream_answer(ws: WebSocket, text: str, mode: str, state: dict, session_id: str = "default", user_id: str = "default"):
    """真实检索版：先查知识库，再流式输出检索结论和引用来源"""
    request_id = str(uuid.uuid4())
    thinking = "THINKING_LOCAL" if mode == "local" else "THINKING_CLOUD"
    await P.send_event(ws, P.SERVER_VOICE_STATE, state=thinking)

    # 本地模式模拟加载模型；云端模式不占显存
    if mode == "local":
        await P.send_event(ws, P.SERVER_MODEL_STATUS,
                           model=CONFIG["local_model"],
                           state="loaded", vram_gb=6.2)
    else:
        await P.send_event(ws, P.SERVER_MODEL_STATUS,
                           model="cloud", state="unloaded", vram_gb=0.0)

    # 关键：检索是阻塞的 CPU 操作，放到线程里跑，避免卡住事件循环
    # 读取最近 10 条历史
    history = get_recent_messages(session_id, limit=10)
    print(f"[记忆] 文字会话 session={session_id} 历史条数={len(history)}")

    try:
        qa = await asyncio.to_thread(generate_answer, text, mode, history, user_id)
    except Exception as e:
        await P.send_event(ws, P.SERVER_ERROR,
                           code="answer_failed", message=str(e))
        await P.send_event(ws, P.SERVER_ASSISTANT_DONE,
                           request_id=request_id, cancelled=False)
        return

    answer_text = qa["answer"]
    results = qa.get("citations", [])
    is_cloud = qa.get("mode") == "cloud"


    # 流式输出
    chunk_size = 10
    for i in range(0, len(answer_text), chunk_size):
        if state["cancel"]:
            await P.send_event(ws, P.SERVER_ASSISTANT_DONE,
                               request_id=request_id, cancelled=True)
            await P.send_event(ws, P.SERVER_VOICE_STATE, state="IDLE")
            return
        await P.send_event(ws, P.SERVER_ASSISTANT_DELTA,
                           request_id=request_id, text=answer_text[i:i + chunk_size])
        await asyncio.sleep(0.05)

    # 发送真实引用来源
    await P.send_event(ws, P.SERVER_CITATION,
                       request_id=request_id, items=results)

    # 写入会话记忆：云端只进内存，本地落 SQLite
    privacy = "cloud" if mode == "cloud" else "local"
    append_message(session_id, "user", text, privacy_scope=privacy)
    append_message(session_id, "assistant", qa["answer"],
                   privacy_scope=privacy)

    # 后台提炼并写入长期记忆，不阻塞本次回答
    asyncio.create_task(asyncio.to_thread(
        _remember_turn_safe,
        text, qa["answer"], user_id, session_id, privacy,
    ))

    await P.send_event(ws, P.SERVER_ASSISTANT_DONE,
                       request_id=request_id, cancelled=False)

    if mode == "local":
        await P.send_event(ws, P.SERVER_MODEL_STATUS,
                           model=CONFIG["local_model"],
                           state="unloaded", vram_gb=0.0)
    await P.send_event(ws, P.SERVER_VOICE_STATE, state="IDLE")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """客户端唯一实时通道：所有事件都从这里收发"""
    await ws.accept()

    # 连接后先同步一次状态
    await P.send_event(ws, P.SERVER_VOICE_STATE, state="IDLE")
    await P.send_event(ws, P.SERVER_MODEL_STATUS,
                       model=CONFIG["local_model"],
                       state="unloaded", vram_gb=0.0)

    state = {"cancel": False, "task": None}

    try:
        while True:
            data = await ws.receive_json()
            event = data.get("event", "")

            if event == P.CLIENT_CANCEL:
                # 打断：置取消标记，正在流式的任务会自行退出
                state["cancel"] = True
                await P.send_event(ws, P.SERVER_ASSISTANT_DONE,
                                   cancelled=True)

            elif event in (P.CLIENT_USER_TEXT, P.CLIENT_AUDIO_END):
                if state["task"] and not state["task"].done():
                    state["task"].cancel()
                state["cancel"] = False
                mode = data.get("mode", CONFIG["mode"])
                user_id = data.get("user_id", "default")
                session_id = data.get("session_id", "default")
                text = data.get("text") or "（语音输入示例）"
                state["task"] = asyncio.create_task(
                    _stream_answer(ws, text, mode, state, session_id, user_id))  # 传入

            elif event == P.CLIENT_AUDIO_START:
                await P.send_event(ws, P.SERVER_VOICE_STATE,
                                   state="LISTENING")

            elif event == P.CLIENT_MODE_SWITCH:
                CONFIG["mode"] = data.get("mode", "local")
                await P.send_event(ws, "mode_changed", mode=CONFIG["mode"])

            elif event == P.CLIENT_MIC_TOGGLE:
                enabled = bool(data.get("enabled"))
                await P.send_event(ws, P.SERVER_VOICE_STATE,
                                   state="LISTENING" if enabled else "IDLE")

            elif event == P.CLIENT_CONFIRM:
                await P.send_event(ws, P.SERVER_TOOL_STATUS,
                                   tool="confirm", state="done",
                                   detail=str(data.get("approved")))

    except WebSocketDisconnect:
        return


@app.post("/api/voice/ask")
async def voice_ask(file: UploadFile = File(...),
                    mode: str = Form("local"),
                    session_id: str = Form("default"),
                    user_id: str = Form("default")):
    """录音 -> 识别 -> 带历史问答 -> 写入会话记忆"""
    suffix = os.path.splitext(file.filename or "voice.wav")[1] or ".wav"
    tmp_path = os.path.join(VOICE_TMP, f"voice_{uuid.uuid4().hex}{suffix}")

    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    try:
        # 1. 识别
        t0 = time.time()
        transcript = await asyncio.to_thread(transcribe_file, tmp_path)
        print(f"[计时] ASR：{time.time() - t0:.2f}s")

        if not transcript:
            return {
                "transcript": "",
                "answer": "没有识别到语音，请重试。",
                "citations": [],
                "mode": mode,
            }

        # 2. 读取最近 10 条历史
        history = get_recent_messages(session_id, limit=10)
        print(f"[记忆] session={session_id} 历史条数={len(history)}")

        # 3. 带历史走本地/云端
        t1 = time.time()
        qa = await asyncio.to_thread(generate_answer,
                                     transcript, mode, history, user_id)
        print(f"[计时] RAG+LLM：{time.time() - t1:.2f}s")

        # 4. 写入会话记忆：云端只进内存，本地落 SQLite
        # 以用户选择的模式为准：云端会话绝不落盘
        privacy = "cloud" if mode == "cloud" else "local"
        append_message(session_id, "user", transcript,
                       privacy_scope=privacy)
        append_message(session_id, "assistant", qa["answer"],
                       privacy_scope=privacy)

        # 后台提炼并写入长期记忆，不阻塞本次回答
        asyncio.create_task(asyncio.to_thread(
            _remember_turn_safe,
            transcript, qa["answer"], user_id, session_id, privacy,
        ))

        return {
            "transcript": transcript,
            "answer": qa["answer"],
            "citations": qa.get("citations", []),
            "mode": qa.get("mode", mode),
            "session_id": session_id,
        }
    except Exception as e:
        return {"error": f"语音处理失败：{e}"}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
