# router.py —— 按模式选择本地 RAG、长期记忆和业务工具
"""local：RAG / 记忆 / Excel / 报表 / 审批单 / 邮件 / 钉钉；cloud：通用问答。"""

import re

from backend.llm.cloud_llm import cloud_answer
from backend.llm.tool_agent import run_tool_agent
from backend.memory_vectors import search_memory
from backend.rag.knowledge import answer as local_answer
from backend.tools.pending import has_pending

PERSONAL_KEYWORDS = [
    "我叫什么", "我的名字", "我是谁",
    "我的手机号", "我的电话", "我的号码",
    "我在哪个部门", "我的部门", "我在什么部门",
    "我叫", "我的手机号是", "我的电话是",
    "手机号是", "电话是",
]

EXCEL_OBJECTS = (
    "excel", "xlsx", "工作簿", "工作表", "表格",
    "测试销售", "销售数据",
)
EXCEL_ACTIONS = (
    "读取", "写入", "追加", "汇总", "统计",
    "查看", "分析", "生成",
)

EMAIL_OBJECTS = ("邮件", "邮箱", "收件箱", "inbox", "email")
EMAIL_ACTIONS = (
    "查", "查看", "搜索", "读取", "读",
    "发", "发送", "发到", "发往", "发给", "回复",
)
EMAIL_ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REPORT_OBJECTS = ("报表", "报告", "汇总表", "统计表")
REPORT_ACTIONS = ("生成", "做", "创建", "导出", "发", "发送")
APPROVAL_OBJECTS = ("审批单", "申请单")
APPROVAL_ACTIONS = ("生成", "创建", "开一份", "开张", "做一份", "填写")
DINGTALK_OBJECTS = ("钉钉", "群机器人", "群通知")
DINGTALK_ACTIONS = ("发送", "发一条", "发个", "通知", "推送")
CONTROL_WORDS = ("确认", "确认执行", "执行", "取消", "放弃", "不要", "算了")


def _is_personal_question(question: str) -> bool:
    return any(k in question for k in PERSONAL_KEYWORDS)


def _is_excel_request(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    return (any(k in text for k in EXCEL_OBJECTS)
            and any(k in text for k in EXCEL_ACTIONS))


def _is_email_request(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    has_action = any(k in text for k in EMAIL_ACTIONS)
    if any(k in text for k in EMAIL_OBJECTS) and has_action:
        return True

    return bool(EMAIL_ADDRESS_RE.search(text)) and has_action


def _is_report_request(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    return (any(k in text for k in REPORT_OBJECTS)
            and any(k in text for k in REPORT_ACTIONS))


def _is_approval_request(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    return (any(k in text for k in APPROVAL_OBJECTS)
            and any(k in text for k in APPROVAL_ACTIONS))


def _is_dingtalk_request(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    return (any(k in text for k in DINGTALK_OBJECTS)
            and any(k in text for k in DINGTALK_ACTIONS))


def generate_answer(question: str, mode: str = "local",
                    history: list = None,
                    owner: str = "default") -> dict:
    """统一入口：个人问题、待确认操作、业务工具、RAG、云端"""
    mode = (mode or "local").lower()

    # 1. 个人问题：始终本地
    if _is_personal_question(question):
        answer = _answer_personal(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 2. 没有待办却说确认/取消：明确告知，不要编造
    if question.strip() in CONTROL_WORDS and not has_pending(owner):
        return {
            "mode": "local",
            "answer": "当前没有待确认的外发操作。",
            "citations": [],
        }

    # 3. 有邮件待确认：用户说“确认/取消”时优先处理
    if has_pending(owner):
        answer = run_tool_agent(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 4. 审批单工具：本地模式
    if _is_approval_request(question):
        if mode == "cloud":
            return {
                "mode": "local",
                "answer": "审批单工具操作需要切换到本地模式。",
                "citations": [],
            }
        print("[路由] 使用审批单工具")
        answer = run_tool_agent(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 5. 钉钉通知工具：本地模式
    if _is_dingtalk_request(question):
        if mode == "cloud":
            return {
                "mode": "local",
                "answer": "钉钉通知操作需要切换到本地模式。",
                "citations": [],
            }
        print("[路由] 使用钉钉通知工具")
        answer = run_tool_agent(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 6. Excel 工具：本地模式
    if _is_excel_request(question):
        if mode == "cloud":
            return {
                "mode": "local",
                "answer": "Excel 工具操作需要切换到本地模式。",
                "citations": [],
            }
        print("[路由] 使用 Excel 工具")
        answer = run_tool_agent(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 7. 报表工具：本地模式
    if _is_report_request(question):
        if mode == "cloud":
            return {
                "mode": "local",
                "answer": "报表工具操作需要切换到本地模式。",
                "citations": [],
            }
        print("[路由] 使用报表工具")
        answer = run_tool_agent(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 8. 邮件工具：本地模式
    if _is_email_request(question):
        if mode == "cloud":
            return {
                "mode": "local",
                "answer": "邮件工具操作需要切换到本地模式。",
                "citations": [],
            }
        print("[路由] 使用邮件工具")
        answer = run_tool_agent(question, history, owner)
        return {"mode": "local", "answer": answer, "citations": []}

    # 9. 云端通用问答
    if mode == "cloud":
        result = cloud_answer(question, history=history)
        return {
            "mode": "cloud",
            "answer": result["answer"],
            "citations": [],
            "sanitized": result.get("sanitized", ""),
        }

    # 10. 本地 RAG + 长期记忆
    memories = search_memory(question, owner, top_k=5)
    if memories:
        print(f"[记忆] 检索到 {len(memories)} 条长期记忆")

    result = local_answer(question, history=history, memories=memories)
    return {
        "mode": "local",
        "answer": result["answer"],
        "citations": result.get("citations", []),
    }


def _answer_personal(question: str, history: list,
                     owner: str = "default") -> str:
    from llama_index.core import Settings
    from backend.rag.knowledge import _setup_llm

    _setup_llm()
    memories = search_memory(question, owner, top_k=5)
    memory_lines = "\n".join(f"- {m['text']}" for m in memories)

    lines = []
    for m in (history or [])[-6:]:
        role = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{role}：{m.get('content', '')}")
    history_text = "\n".join(lines) or "（暂无历史）"

    prompt = (
        "你是个人助理。请只依据下面的长期记忆和历史对话回答用户问题。\n"
        "允许直接推断，例如用户说“在技术部”，就说明部门是技术部；\n"
        "两处都没有的信息就回答“根据现有信息无法回答”，不要编造。\n\n"
        f"长期记忆：\n{memory_lines or '（无）'}\n\n"
        f"历史对话：\n{history_text}\n\n"
        f"问题：{question}\n"
        "回答："
    )
    return str(Settings.llm.complete(prompt))
