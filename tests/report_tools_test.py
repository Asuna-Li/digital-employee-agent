# report_tools_test.py —— 验证报表生成
from backend.tools.report_tools import generate_report

result = generate_report(
    source_file="测试销售.xlsx",
    sheet_name="销售数据",
    group_by="部门",
    aggregate="sum",
    columns=["金额"],
    report_title="部门销售汇总",
)
print(result)
