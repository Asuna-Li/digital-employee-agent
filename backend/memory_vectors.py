#长期记忆：Chroma 向量存储 + 本地模型提炼
import json
import os
import uuid
from datetime import datetime

import chromadb
from llama_index.core import Settings

# 复用知识库模块里已经加载好的 bge-m3 和 Qwen
from backend.rag.knowledge import BASE_DIR, _setup_embedding, _setup_llm

MEMORY_DIR = os.path.join(BASE_DIR, "storage", "memory_chroma")
COLLECTION_NAME = "memory"

_client = None
_collection = None


def _get_collection():
    """获取（或创建）长期记忆集合"""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=MEMORY_DIR)
        _collection = _client.get_or_create_collection(COLLECTION_NAME)
    return _collection


def _embed(text: str) -> list:
    """用本地 bge-m3 生成向量"""
    _setup_embedding()
    return Settings.embed_model.get_text_embedding(text)


# ---------- 记忆提炼 ----------

def extract_memories(dialogue: str) -> list:
    """从一段对话里提炼值得长期记住的信息"""
    _setup_llm()
    prompt = (
        "你是记忆提取器。从对话中提炼值得长期记住的信息。规则：\n"
        "1. 只提炼用户明确表达的事实、偏好、决定或结论；助手的话不算；\n"
        "2. type 只能是 preference/fact/task/conclusion/general；\n"
        "3. 用户自述的姓名、部门、手机号、偏好、计划属于 fact 或 "
        "preference，必须提取；\n"
        '4. 每条输出 JSON 对象，例如 '
        '{"text": "用户喜欢美式咖啡", "type": "preference"}；\n'
        "5. 只输出 JSON 数组，没有值得记住的内容就输出 []。\n\n"
        "示例：\n"
        "用户：我叫张三，在技术部，手机号是11111111\n"
        "输出：[{\"text\":\"用户叫张三\",\"type\":\"fact\"},"
        "{\"text\":\"用户在技术部\",\"type\":\"fact\"},"
        "{\"text\":\"用户的手机号是11111111\",\"type\":\"fact\"}]\n\n"
        f"对话：\n{dialogue}\n"
        "只输出 JSON："
    )
    response = Settings.llm.complete(prompt)
    text = str(response).strip()

    # 去掉模型可能加的代码块标记
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                text = part
                break

    # 兜底：从普通说明文字里截取第一个 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        text = text[start:end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []
    return [
        m for m in data
        if isinstance(m, dict) and str(m.get("text", "")).strip()
    ]


# ---------- 记忆写入 ----------

def add_memory(text: str, owner: str, mtype: str = "general",
               session_id: str = "", privacy_scope: str = "local") -> str:
    """写入一条长期记忆，返回记忆 ID"""
    collection = _get_collection()
    memory_id = str(uuid.uuid4())
    metadata = {
        "owner": owner,
        "type": mtype,
        "status": "active",
        "privacy_scope": privacy_scope,
        "session_id": session_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    collection.add(
        ids=[memory_id],
        documents=[text],
        embeddings=[_embed(text)],
        metadatas=[metadata],
    )
    return memory_id


def search_memory(question: str, owner: str, top_k: int = 5) -> list:
    """按 owner 检索相关记忆，只返回 status=active 的"""
    collection = _get_collection()
    if collection.count() == 0:
        return []

    result = collection.query(
        query_embeddings=[_embed(question)],
        n_results=top_k,
        where={"$and": [{"owner": owner}, {"status": "active"}]},
    )

    memories = []
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for memory_id, doc, meta, dist in zip(ids, docs, metas, distances):
        memories.append({
            "id": memory_id,
            "text": doc,
            "type": (meta or {}).get("type", "general"),
            "privacy_scope": (meta or {}).get("privacy_scope", "local"),
            "distance": round(float(dist), 4),
        })
    return memories


# ---------- 记忆治理 ----------

def soft_delete_memory(memory_id: str):
    """软删除：把 status 改成 superseded，保留原文"""
    collection = _get_collection()
    existing = collection.get(ids=[memory_id])
    if not existing.get("ids"):
        return
    metadata = (existing.get("metadatas") or [{}])[0] or {}
    metadata["status"] = "superseded"
    collection.update(ids=[memory_id], metadatas=[metadata])


def list_memories(owner: str) -> list:
    """列出某个 owner 的全部记忆（含已过时）"""
    collection = _get_collection()
    result = collection.get(where={"owner": owner})
    memories = []
    for memory_id, doc, meta in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", [])):
        memories.append({
            "id": memory_id,
            "text": doc,
            "type": (meta or {}).get("type"),
            "status": (meta or {}).get("status"),
            "privacy_scope": (meta or {}).get("privacy_scope"),
        })
    return memories


def clear_owner(owner: str):
    """删除某个 owner 的全部记忆（仅用于测试）"""
    collection = _get_collection()
    collection.delete(where={"owner": owner})


# ---------- 记忆写入：冲突判断 + 一轮对话沉淀 ----------

def remember_memory(text: str, owner: str, mtype: str = "general",
                    session_id: str = "", privacy_scope: str = "local") -> str:
    """写入一条记忆；发现同属性冲突时软删除旧记忆"""
    _setup_llm()

    # 1. 检索相似的旧记忆
    related = search_memory(text, owner, top_k=5)

    # 完全重复的记忆直接复用，避免每轮重复写入
    for old in related:
        if old["text"].strip() == text.strip() and old["type"] == mtype:
            return old["id"]

    # 2. 事实类只追加，不覆盖；其他类型判断是否冲突
    if related and mtype != "fact":
        old_list = json.dumps(
            [{"id": r["id"], "text": r["text"], "type": r["type"]}
             for r in related],
            ensure_ascii=False,
        )
        prompt = (
            "你是记忆管理员。判断新记忆是否与旧记忆直接冲突。\n"
            f"新记忆：{json.dumps({'text': text, 'type': mtype}, ensure_ascii=False)}\n"
            f"旧记忆：{old_list}\n"
            "规则：只有同一主体的同一属性直接矛盾（例如偏好从美式改为拿铁）"
            "才输出 REPLACE；不确定就 KEEP；宁可保留两条，绝不误删。\n"
            '只输出 JSON：{"action": "REPLACE", "old_ids": ["id1"]} '
            '或 {"action": "KEEP"}'
        )
        response = str(Settings.llm.complete(prompt)).strip()

        # 去掉模型可能加的代码块标记
        if "```" in response:
            for part in response.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    response = part
                    break

        try:
            decision = json.loads(response)
        except json.JSONDecodeError:
            decision = {"action": "KEEP"}

        if decision.get("action") == "REPLACE":
            for old_id in decision.get("old_ids", []) or []:
                soft_delete_memory(old_id)

    return add_memory(text, owner, mtype, session_id, privacy_scope)


def remember_turn(user_text: str, assistant_text: str, owner: str,
                  session_id: str = "", privacy_scope: str = "local") -> list:
    """一轮对话结束后：提炼记忆并写入长期记忆库"""
    _setup_llm()

    dialogue = f"用户：{user_text}\n助手：{assistant_text}"
    extracted = extract_memories(dialogue)
    saved = []

    for item in extracted:
        text = str(item.get("text", "")).strip()
        mtype = str(item.get("type", "general"))
        if not text:
            continue

        # 云端模式：只保存脱敏摘要，脱敏不通过就丢弃
        if privacy_scope == "cloud":
            from backend.privacy.desensitizer import (
                desensitize, has_residual,
            )
            safe_text, _ = desensitize(text)
            if has_residual(safe_text):
                continue
            text = safe_text

        memory_id = remember_memory(text, owner, mtype,
                                    session_id, privacy_scope)
        saved.append(memory_id)

    return saved
