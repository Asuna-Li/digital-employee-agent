# tool_agent.py —— 本地 Qwen 的工具调用循环（Excel、报表、审批单、邮件）
import json
import os
import re

from openai import OpenAI
from backend.tools import (
    approval_defs,
    dingtalk_defs,
    email_defs,
    report_defs,
    tool_defs,
)
from backend.tools.pending import (
    clear_pending, get_pending, set_pending,
)
from backend.tools.email_tools import _resolve_attachment
from backend.tools.registry import call_tool, get_tool_schemas
from backend.rag.knowledge import LLM_MODEL

_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

WORKFLOW_VERSION = "B5C-dingtalk-forced-v1"

SYSTEM_PROMPT = (
    "你是企业数字化员工。可以使用 Excel、报表、审批单、QQ 邮件和钉钉工具。\n"
    "规则：\n"
    "1. 查邮件前先用 email_search；读取详情必须用返回的 uid 调用 email_read。\n"
    "2. 发送邮件必须调用 email_send；系统会暂停等待用户确认，"
    "在用户确认前绝不能声称已发送。\n"
    "用户说“作为附件发送到 xxx@xxx.com”也属于发送邮件请求。\n"
    "即使历史对话中有相似的成功发送记录，新的发送请求也必须重新调用 email_send；"
    "不得复述历史声称已发送。\n"
    "3. 生成报表必须调用 generate_report；需要附件时使用工具返回的报表文件路径。\n"
    "4. 生成审批单必须调用 create_approval_form；申请人未知时先询问，不得代替用户编造。\n"
    "5. 禁止编造报表、审批单的文件名、时间戳或路径；"
    "附件必须使用对应生成工具返回的实际文件路径。\n"
    "6. 只能依据工具真实返回的内容回答，不得编造表格、报表、审批单或邮件内容。\n"
    "7. 同一个工具和相同参数最多执行一次；成功生成后不得重复生成。\n"
    "8. 发送钉钉通知必须调用 dingtalk_send；系统会暂停等待用户确认，"
    "确认前绝不能声称通知已发送。\n"
    "9. 文件/邮件不存在或工具报错时，如实告诉用户。\n"
    "10. 回答简洁，给出关键结果。"
)

CONFIRM_WORDS = ("确认", "确认执行", "执行", "发送", "可以", "好的", "好")
CANCEL_WORDS = ("取消", "不要", "不用了", "放弃", "算了")
EMAIL_ADDRESS_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)


def _is_confirm(text: str) -> bool:
    return text.strip() in CONFIRM_WORDS


def _is_cancel(text: str) -> bool:
    return text.strip() in CANCEL_WORDS


def _is_send_request(text: str) -> bool:
    """判断用户是否明确要求发送邮件"""
    text = text or ""
    if any(k in text for k in (
        "发邮件", "发送邮件", "发一封邮件", "发送一封邮件", "邮件给",
    )):
        return True


    return (
        "@" in text
        and any(k in text for k in ("发送", "发到", "发往", "发给", "附件"))
    )


def _is_report_request(text: str) -> bool:
    """判断用户是否明确要求生成报表"""
    text = text or ""
    return ("报表" in text or "报告" in text) and any(
        k in text for k in ("生成", "做", "创建", "导出")
    )


def _is_approval_request(text: str) -> bool:
    """判断用户是否明确要求生成审批单。"""
    text = text or ""
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    return (
        ("审批单" in text or "申请单" in text)
        and any(k in text for k in ("生成", "创建", "开一份", "开张", "做一份", "填写"))
    )


def _is_dingtalk_request(text: str) -> bool:
    """判断用户是否明确要求发送钉钉通知。"""
    text = text or ""
    if any(k in text for k in ("怎么", "如何", "什么是", "是什么")):
        return False
    return (
        any(k in text for k in ("钉钉", "群机器人", "群通知"))
        and any(k in text for k in ("发送", "发一条", "发个", "通知", "推送"))
    )


def _repair_attachment_argument(arguments: dict,
                                generated_attachments: list) -> None:
    """
    修正模型传错的附件参数。

    模型有时能正确生成文件，却在下一步调用 email_send 时把文件名写错。
    只要本次已经真实生成附件，而模型提供的附件缺失或无法解析，
    就自动改用本次生成工具返回的真实路径。
    """
    if not generated_attachments:
        return

    requested = str(arguments.get("attachment_file") or "").strip()
    if requested:
        try:
            _resolve_attachment(requested)
            return
        except Exception:
            pass

    actual = generated_attachments[-1]
    arguments["attachment_file"] = actual
    print(
        f"[工具] email_send | 附件参数已自动修正为刚生成的文件：{actual}"
    )


def _queue_email_confirmation(owner: str, arguments: dict) -> str:
    """保存模型已经返回的 email_send 调用，等待用户确认。"""
    summary = (
        f"收件人：{arguments.get('to')}｜"
        f"主题：{arguments.get('subject')}｜"
        f"附件：{arguments.get('attachment_file') or '无'}"
    )
    set_pending(owner, "email_send", arguments, summary)
    print(
        f"[工具] email_send | 参数：{arguments} | "
        "状态：等待用户确认"
    )
    return (
        f"检测到发送邮件操作：{summary}\n"
        "请回复“确认”执行，或“取消”放弃。"
    )


def _run_focused_email_turn(question: str,
                            attachment_path: str,
                            generated_result: str,
                            generated_arguments: dict) -> dict:
    """
    使用独立的、最小上下文的邮件回合，强制模型返回 email_send 工具调用。

    这里不替模型填写邮件参数；只有模型真实返回 email_send，且关键字段
    通过校验后，才把参数交给待确认逻辑。
    """
    email_schemas = [
        schema for schema in get_tool_schemas()
        if schema.get("function", {}).get("name") == "email_send"
    ]
    if not email_schemas:
        raise ValueError("email_send 工具未注册")

    messages = [
        {
            "role": "system",
            "content": (
                "你当前只负责把已经生成的文件作为附件发送邮件。"
                "必须调用 email_send 工具，不要输出普通文本。"
                "收件人从用户原始请求中提取；主题和正文应简洁、准确。"
                "attachment_file 必须使用提供的真实文件路径，禁止改写。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"用户原始请求：{question}\n"
                f"真实附件路径：{attachment_path}\n"
                f"文件生成参数：{json.dumps(generated_arguments, ensure_ascii=False)}\n"
                f"文件生成结果：{generated_result}\n"
                "现在调用 email_send。"
            ),
        },
    ]

    last_error = "模型没有返回 email_send 工具调用"
    for attempt in range(1, 3):
        response = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=email_schemas,
            tool_choice={
                "type": "function",
                "function": {"name": "email_send"},
            },
            temperature=0,
        )
        message = response.choices[0].message
        email_calls = [
            call for call in (message.tool_calls or [])
            if call.function.name == "email_send"
        ]
        if not email_calls:
            last_error = (
                f"第 {attempt} 次聚焦邮件回合未返回 email_send 工具调用"
            )
            continue

        try:
            arguments = json.loads(email_calls[0].function.arguments or "{}")
        except Exception as exc:
            last_error = f"email_send 参数解析失败：{exc}"
            continue
        if not isinstance(arguments, dict):
            last_error = "email_send 参数不是 JSON 对象"
            continue

        # 附件路径由应用层写成刚生成的真实路径，避免模型抄错文件名。
        arguments["attachment_file"] = attachment_path
        to = str(arguments.get("to") or "").strip().strip("<>")
        subject = str(arguments.get("subject") or "").strip()
        body = str(arguments.get("body") or "").strip()
        arguments["to"] = to
        arguments["subject"] = subject
        arguments["body"] = body

        if not EMAIL_ADDRESS_RE.fullmatch(to):
            last_error = f"收件人邮箱格式无效：{to or '空'}"
            continue
        if not subject:
            last_error = "邮件主题为空"
            continue
        if not body:
            last_error = "邮件正文为空"
            continue
        try:
            _resolve_attachment(attachment_path)
        except Exception as exc:
            last_error = f"附件校验失败：{exc}"
            continue

        return arguments

    raise ValueError(last_error)


def _tool_calls_to_dict(msg):
    return [{
        "id": tc.id,
        "type": tc.type,
        "function": {
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        },
    } for tc in msg.tool_calls]


def run_tool_agent(question: str, history: list = None,
                   owner: str = "default", max_turns: int = 5) -> str:
    """让本地 Qwen 自主选择工具；邮件发送前进入待确认状态"""
    # 先处理上一条待确认操作
    pending = get_pending(owner)
    if pending:
        if _is_confirm(question):
            try:
                result = call_tool(pending["tool_name"],
                                   pending["arguments"])
            except Exception as e:
                result = f"执行失败：{e}"
            clear_pending(owner)
            return f"已确认执行。\n{result}"

        if _is_cancel(question):
            clear_pending(owner)
            return "已取消该操作，没有执行发送。"

        # 用户说了别的内容：放弃旧待办，继续正常处理
        clear_pending(owner)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in (history or [])[-6:]:
        role = "user" if m.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": m.get("content", "")})
    messages.append({"role": "user", "content": question})

    executed_calls = {}
    successful_results = []
    approval_generated = False
    report_generated = False
    generated_attachments = []
    send_requested = _is_send_request(question)
    approval_requested = _is_approval_request(question)
    report_requested = _is_report_request(question)
    dingtalk_requested = _is_dingtalk_request(question)
    print(f"[工作流] version={WORKFLOW_VERSION}")


    send_workflow_generator = None
    if send_requested:
        if approval_requested:
            send_workflow_generator = "create_approval_form"
        elif report_requested:
            send_workflow_generator = "generate_report"

    for _ in range(max_turns):
        forced_tool = None
        if dingtalk_requested and not send_workflow_generator:
            forced_tool = "dingtalk_send"
        elif send_workflow_generator == "create_approval_form" and not approval_generated:
            forced_tool = "create_approval_form"
        elif send_workflow_generator == "generate_report" and not report_generated:
            forced_tool = "generate_report"
        request_arguments = {
            "model": LLM_MODEL,
            "messages": messages,
            "tools": get_tool_schemas(),
            "temperature": 0.1,
        }
        if forced_tool:
            print(f"[工作流] 强制工具={forced_tool}")
            request_arguments["tool_choice"] = {
                "type": "function",
                "function": {"name": forced_tool},
            }

        response = _client.chat.completions.create(
            **request_arguments
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            # 审批单尚未生成时，禁止模型不调用工具就直接声称已生成。
            if approval_requested and not approval_generated:
                messages.append({
                    "role": "user",
                    "content": (
                        "系统提示：你刚才没有调用 create_approval_form 工具，"
                        "不能声称审批单已生成。请先调用 create_approval_form，"
                        "然后使用工具返回的真实文件路径；"
                        "申请人未知时先询问，禁止编造文件名或路径。"
                    ),
                })
                continue

            # 报表尚未生成时，禁止模型不调用工具就直接声称已生成。
            if report_requested and not report_generated:
                messages.append({
                    "role": "user",
                    "content": (
                        "系统提示：你刚才没有调用 generate_report 工具，"
                        "不能声称报表已生成。请先调用 generate_report，"
                        "然后使用工具返回的真实文件路径；"
                        "禁止编造文件名、时间戳或 data/reports 路径。"
                    ),
                })
                continue

            # 用户要求发送邮件，但模型没有调用工具：禁止假成功
            if send_requested:
                messages.append({
                    "role": "user",
                    "content": (
                        "系统提示：你刚才没有调用 email_send 工具，"
                        "不能声称邮件已发送。请立即调用 email_send，"
                        "提供 to、subject、body；不要复述历史中的发送结果。"
                    ),
                })
                continue

            # 用户要求发送钉钉通知，但模型没有调用工具：禁止假成功
            if dingtalk_requested:
                messages.append({
                    "role": "user",
                    "content": (
                        "系统提示：你刚才没有调用 dingtalk_send 工具，"
                        "不能声称钉钉通知已发送。请立即调用 dingtalk_send，"
                        "提供 text；需要 @ 时填写 at_mobiles 或 at_all。"
                    ),
                })
                continue

            return msg.content or "我没有得到有效结果。"

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": _tool_calls_to_dict(msg),
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            arguments = {}
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except Exception as e:
                result = f"工具参数解析失败：{e}"
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": result,
                })
                continue


            call_key = (
                name,
                json.dumps(
                    arguments,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
            if call_key in executed_calls:
                result = (
                    "该操作已用相同参数成功执行，系统没有重复执行。\n"
                    f"原工具结果：\n{executed_calls[call_key]}"
                )
                print(f"[工具] {name} | 检测到重复调用，已跳过")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "系统提示：上一步工具已经成功执行，禁止再用相同参数调用。"
                        "请根据已有工具结果直接回答用户；如果用户还要求发送邮件，"
                        "请继续处理发送确认。"
                    ),
                })
                continue

            # 邮件发送：暂停等待确认，不立即执行
            if name == "email_send":
                _repair_attachment_argument(arguments, generated_attachments)
                attachment = arguments.get("attachment_file", "")
                # 附件必须先真实存在；不存在时把错误交回模型，让它先生成报表
                try:
                    _resolve_attachment(attachment)
                except Exception as e:
                    result = (
                        f"邮件附件无效：{e}。请先调用 generate_report 或 "
                        "create_approval_form，并使用对应工具返回的实际文件路径，"
                        "不要编造文件名。"
                    )
                    print(
                        f"[工具] {name} | 附件校验失败：{result} | "
                        f"参数：{arguments}"
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                    continue

                return _queue_email_confirmation(owner, arguments)

            # 钉钉通知：暂停等待确认，不立即执行
            if name == "dingtalk_send":
                text = str(arguments.get("text") or "").strip()
                if not text:
                    result = "钉钉通知内容为空，请向用户确认通知正文。"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                    continue

                summary = text.replace("\r", " ").replace("\n", " ")[:120]
                at_all = bool(arguments.get("at_all"))
                mobiles = arguments.get("at_mobiles") or []
                target = "@所有人" if at_all else (
                    f"@{'、'.join(str(x) for x in mobiles)}"
                    if mobiles else "群消息"
                )
                set_pending(owner, name, arguments, summary)
                print(
                    f"[工具] dingtalk_send | 参数：{arguments} | "
                    "状态：等待用户确认"
                )
                return (
                    f"检测到钉钉通知操作：{target}｜内容：{summary}\n"
                    "请回复“确认”执行，或“取消”放弃。"
                )

            try:
                result = call_tool(name, arguments)
            except Exception as e:
                result = f"工具执行失败：{e}"

            executed_calls[call_key] = str(result)
            if not str(result).startswith(("工具执行失败：", "缺少必填字段：")):
                successful_results.append(str(result))

            if name == "create_approval_form" and str(result).startswith(
                "审批单已生成："
            ):
                approval_generated = True
                generated_path = str(result).splitlines()[0].partition("：")[2].strip()
                if generated_path and os.path.exists(generated_path):
                    generated_attachments.append(generated_path)
            elif name == "generate_report" and str(result).startswith(
                "报表已生成："
            ):
                report_generated = True
                generated_path = str(result).splitlines()[0].partition("：")[2].strip()
                if generated_path and os.path.exists(generated_path):
                    generated_attachments.append(generated_path)

            print(f"[工具] {name} | 参数：{arguments} | "
                  f"结果：{str(result)[:120]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })


            if (
                send_requested
                and (
                    (name == "create_approval_form" and approval_generated)
                    or (name == "generate_report" and report_generated)
                )
            ):
                try:
                    email_arguments = _run_focused_email_turn(
                        question=question,
                        attachment_path=generated_attachments[-1],
                        generated_result=str(result),
                        generated_arguments=arguments,
                    )
                except Exception as exc:
                    return (
                        f"{result}\n"
                        f"邮件工具调用失败：{exc}\n"
                        "审批单或报表已保留，但没有创建邮件待确认操作。"
                    )

                pending_message = _queue_email_confirmation(
                    owner,
                    email_arguments,
                )
                return f"{result}\n{pending_message}"

    # 即使模型后续陷入重复调用，也不能把已经真实完成的操作误报为失败。
    if successful_results:
        return successful_results[-1]
    if dingtalk_requested:
        return (
            "钉钉通知工具调用失败：模型没有返回 dingtalk_send 工具调用，"
            "系统已阻止普通文本冒充发送结果。"
        )
    return "工具调用次数过多，任务未完成。"
