# tool_agent_email_test.py —— 验证邮件工具与发送确认
import os

from backend.llm.tool_agent import run_tool_agent

OWNER = "email-test"

print("=== 查看最近邮件 ===")
print(run_tool_agent("查看最近 3 封邮件", owner=OWNER))

qq_email = os.getenv("QQ_EMAIL", "")
if qq_email:
    print("\n=== 请求发送（应暂停等待确认） ===")
    request_result = run_tool_agent(
        f"发送一封测试邮件给 {qq_email}，"
        "主题：邮件工具确认测试，正文：这是一封测试邮件。",
        owner=OWNER,
    )
    print(request_result)

    # 关键：只有你手动输入“确认”，才真正发送
    command = input(
        "\n请输入“确认”才会真正发送，输入其他内容则取消："
    ).strip()
    if command == "确认":
        print("\n=== 确认发送 ===")
        print(run_tool_agent("确认", owner=OWNER))
    else:
        print("\n=== 取消发送 ===")
        print(run_tool_agent("取消", owner=OWNER))
else:
    print("未配置 QQ_EMAIL，跳过发送测试")
