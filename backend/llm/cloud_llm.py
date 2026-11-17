# cloud_llm.py —— 云端通用问答：本地脱敏后再发送
"""只做通用问答：不查知识库、不调用工具、不保存原文。"""

import os

from dotenv import load_dotenv
from openai import OpenAI

from backend.privacy.desensitizer import (
    desensitize, has_residual, restore,
)

load_dotenv()

# 云端模型客户端（DeepSeek 兼容 OpenAI 接口）
_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "deepseek-chat")

# 系统提示词：明确云端能力边界
SYSTEM_PROMPT = (
    "你是通用问答助手。你只能回答通用知识问题，"
    "不能查询任何企业知识库，也不能执行任何工具或动作。"
    "如果用户询问企业内部的制度、数据或流程，请说明"
    "云端模式无法访问企业知识库，请切换到本地模式；"
    "但如果是用户自己的个人信息（姓名、电话、部门等），"
    "只要历史对话里有，就正常回答。"
    "回答要简洁、准确。"
)


def cloud_answer(question: str, history: list = None) -> dict:
    """云端通用问答：问题与历史都先脱敏，再发送"""
    sanitized, mapping = desensitize(question)
    if has_residual(sanitized):
        return {
            "answer": "检测到脱敏未通过，已阻止发送到云端。",
            "sanitized": sanitized,
            "citations": [],
        }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 历史消息逐条脱敏；有残留的条目直接跳过，不发送
    for m in (history or [])[-6:]:
        content = str(m.get("content", ""))
        if not content:
            continue
        safe_content, _ = desensitize(content)
        if has_residual(safe_content):
            continue
        role = "user" if m.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": safe_content})

    messages.append({"role": "user", "content": sanitized})

    response = _client.chat.completions.create(
        model=CLOUD_MODEL,
        messages=messages,
        temperature=0.3,
    )
    answer = response.choices[0].message.content or ""

    # 仅在本地内存中还原当前问题的实体
    answer = restore(answer, mapping)

    return {
        "answer": answer,
        "sanitized": sanitized,
        "citations": [],
    }