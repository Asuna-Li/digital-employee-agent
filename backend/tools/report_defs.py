# report_defs.py —— 把报表生成函数注册成模型工具
from backend.tools.registry import register_tool
from backend.tools.report_tools import generate_report

register_tool({
    "type": "function",
    "function": {
        "name": "generate_report",
        "description": "读取 Excel 生成带汇总表和柱状图的报表文件，保存到 data/reports",
        "parameters": {
            "type": "object",
            "properties": {
                "source_file": {
                    "type": "string",
                    "description": "源 Excel 文件名，例如 测试销售.xlsx",
                },
                "sheet_name": {
                    "type": "string",
                    "description": "源工作表名；留空自动选第一个有数据的表",
                },
                "group_by": {
                    "type": "string",
                    "description": "按哪列分组，例如 部门",
                },
                "aggregate": {
                    "type": "string",
                    "description": "sum/mean/count/max/min，默认 sum",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要统计的数值列，例如 [\"金额\"]",
                },
                "report_title": {
                    "type": "string",
                    "description": "报表标题，例如 部门销售汇总",
                },
            },
            "required": ["source_file"],
        },
    },
})(generate_report)
