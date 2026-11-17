# excel_tools_test.py —— 验证 Excel 读写、追加、汇总
from backend.tools.excel_tools import (
    excel_append, excel_read, excel_sheets, excel_summarize, excel_write,
)

FILE = "测试销售.xlsx"

print("=== 写入 ===")
print(excel_write(
    FILE, "销售数据",
    ["姓名", "部门", "金额"],
    [
        ["张三", "市场部", 1200],
        ["李四", "技术部", 800],
        ["王五", "销售部", 1500],
        ["赵六", "财务部", 900],
    ],
))

print("=== 追加 ===")
print(excel_append(
    FILE, "销售数据",
    rows=[["孙七", "销售部", 600]],
))

print("=== 工作表 ===")
print(excel_sheets(FILE))

print("=== 读取 ===")
print(excel_read(FILE, "销售数据", max_rows=10))

print("=== 按部门汇总金额 ===")
print(excel_summarize(FILE, "销售数据", group_by="部门",
                      aggregate="sum", columns=["金额"]))
