# tool_defs.py —— 把 Excel 函数注册成模型可调用的工具
from backend.tools.registry import register_tool
from backend.tools.excel_tools import (
    excel_sheets, excel_read, excel_write, excel_append, excel_summarize,
)

register_tool({
    "type": "function",
    "function": {
        "name": "excel_sheets",
        "description": "查看 Excel 文件里有哪些工作表",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "Excel 文件名，例如 测试销售.xlsx",
                },
            },
            "required": ["file_name"],
        },
    },
})(excel_sheets)

register_tool({
    "type": "function",
    "function": {
        "name": "excel_read",
        "description": "读取 Excel 指定工作表的前若干行",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Excel 文件名"},
                "sheet_name": {
                    "type": "string",
                    "description": "工作表名，留空用第一个",
                },
                "max_rows": {
                    "type": "integer",
                    "description": "最多读多少行，默认 30",
                },
            },
            "required": ["file_name"],
        },
    },
})(excel_read)

register_tool({
    "type": "function",
    "function": {
        "name": "excel_write",
        "description": "新建或覆盖 Excel 工作表，写入表头和数据行",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Excel 文件名"},
                "sheet_name": {"type": "string", "description": "工作表名"},
                "headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "表头，例如 [\"姓名\",\"部门\",\"金额\"]",
                },
                "rows": {
                    "type": "array",
                    "items": {"type": "array", "items": {}},
                    "description": "数据行，例如 [[\"张三\",\"市场部\",1200]]",
                },
            },
            "required": ["file_name", "headers", "rows"],
        },
    },
})(excel_write)

register_tool({
    "type": "function",
    "function": {
        "name": "excel_append",
        "description": "在 Excel 现有工作表末尾追加数据行",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Excel 文件名"},
                "sheet_name": {"type": "string", "description": "工作表名"},
                "headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "表不存在时才需要的表头",
                },
                "rows": {
                    "type": "array",
                    "items": {"type": "array", "items": {}},
                    "description": "要追加的数据行",
                },
            },
            "required": ["file_name", "rows"],
        },
    },
})(excel_append)

register_tool({
    "type": "function",
    "function": {
        "name": "excel_summarize",
        "description": "对 Excel 做分组汇总：求和/平均/计数/最大/最小",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Excel 文件名"},
                "sheet_name": {"type": "string", "description": "工作表名"},
                "group_by": {
                    "type": "string",
                    "description": "按哪列分组，例如 部门",
                },
                "aggregate": {
                    "type": "string",
                    "description": "sum/mean/count/max/min",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要统计的数值列，例如 [\"金额\"]",
                },
            },
            "required": ["file_name"],
        },
    },
})(excel_summarize)
