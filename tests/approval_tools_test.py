# approval_tools_test.py —— 验证审批单工具能够生成 Word 文件
from backend.tools.approval_tools import create_approval_form


result = create_approval_form(
    form_type="通用",
    applicant="张三",
    department="技术部",
    amount="5000",
    reason="申请采购开发用显示器",
    date="2026-10-20",
    approver="王经理",
)

print(result)
