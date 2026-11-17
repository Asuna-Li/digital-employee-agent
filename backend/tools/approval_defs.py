# approval_defs.py —— 把审批单生成函数注册成模型可调用工具
from backend.tools.approval_tools import create_approval_form
from backend.tools.registry import register_tool


register_tool({
    "type": "function",
    "function": {
        "name": "create_approval_form",
        "description": (
            "生成 Word 审批单并保存到 data/approvals。"
            "当用户要求生成、创建或开一份请假、采购、用款、通用等审批单时调用。"
            "申请人必须填写；用户未提供的字段留空，禁止编造。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "form_type": {
                    "type": "string",
                    "description": "审批类型，例如通用、采购、请假、用款；默认通用",
                },
                "applicant": {
                    "type": "string",
                    "description": "申请人姓名，必填",
                },
                "department": {
                    "type": "string",
                    "description": "申请人部门；用户未提供则留空",
                },
                "amount": {
                    "type": "string",
                    "description": "申请金额，例如 5000；没有金额则留空",
                },
                "reason": {
                    "type": "string",
                    "description": "申请事由，整理成通顺说明；不得编造",
                },
                "date": {
                    "type": "string",
                    "description": "申请日期，格式 YYYY-MM-DD；留空使用当天日期",
                },
                "approver": {
                    "type": "string",
                    "description": "审批人姓名；不知道则留空",
                },
            },
            "required": ["applicant"],
        },
    },
})(create_approval_form)
