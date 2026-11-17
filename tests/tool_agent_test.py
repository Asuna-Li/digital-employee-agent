# tool_agent_test.py —— 验证 Qwen 能否主动调用 Excel 工具
from backend.llm.tool_agent import run_tool_agent

questions = [
    "读取 测试销售.xlsx 的 销售数据 工作表",
    "按部门汇总 测试销售.xlsx 的销售金额",
]

for q in questions:
    print("=" * 60)
    print("问题：", q)
    print("回答：", run_tool_agent(q))
