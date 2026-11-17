# tool_agent_report_test.py —— 验证报表生成与报表附件邮件
import os

from backend.llm.tool_agent import run_tool_agent

OWNER = "report-test"
qq_email = os.getenv("QQ_EMAIL", "")

if qq_email:
    prompt = (
        "用 测试销售.xlsx 的销售数据，按部门汇总金额，"
        "生成一份部门销售汇总报表；然后先生成报表，再把该报表作为附件"
        f"发到 {qq_email}，主题：部门销售汇总。"
    )
else:
    prompt = (
        "用 测试销售.xlsx 的销售数据，按部门汇总金额，"
        "生成一份部门销售汇总报表。"
    )

print("=== 请求 ===")
result = run_tool_agent(prompt, owner=OWNER)
print(result)

# 只有出现待确认提示时，才让用户手动确认
if "请回复“确认”" in result:
    command = input("\n输入“确认”才会发送邮件，输入其他内容取消：").strip()
    if command == "确认":
        print(run_tool_agent("确认", owner=OWNER))
    else:
        print(run_tool_agent("取消", owner=OWNER))
