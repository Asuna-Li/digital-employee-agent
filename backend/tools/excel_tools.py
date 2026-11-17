# excel_tools.py —— Excel 工具：读取、写入、追加、汇总
import os

import pandas as pd
from openpyxl import Workbook, load_workbook

# 项目根目录：D:\my-agent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXCEL_DIR = os.path.join(BASE_DIR, "data", "excel")
os.makedirs(EXCEL_DIR, exist_ok=True)


def _resolve(file_name: str) -> str:
    """只允许访问 data/excel 下的文件，防止路径穿越"""
    safe = os.path.basename(str(file_name).replace("\\", "/"))
    if not safe.endswith((".xlsx", ".xlsm")):
        raise ValueError("仅支持 .xlsx / .xlsm 文件")
    return os.path.join(EXCEL_DIR, safe)


def _pick_worksheet(wb, sheet_name: str = ""):
    """指定了工作表就用指定的；否则选第一个有内容的表"""
    if sheet_name and sheet_name in wb.sheetnames:
        return wb[sheet_name]

    for ws in wb.worksheets:
        # 空表通常只有 A1，且 A1 为空；用行列数做快速判断
        if ws.max_row > 1 or ws.max_column > 1:
            return ws
    return wb.active


def excel_sheets(file_name: str) -> str:
    """列出 Excel 里的工作表"""
    path = _resolve(file_name)
    if not os.path.exists(path):
        return f"文件不存在：{file_name}"
    wb = load_workbook(path, read_only=True)
    return "工作表：" + "、".join(wb.sheetnames)


def excel_read(file_name: str, sheet_name: str = "",
               max_rows: int = 30) -> str:
    """读取指定工作表的前 N 行"""
    path = _resolve(file_name)
    if not os.path.exists(path):
        return f"文件不存在：{file_name}"

    wb = load_workbook(path, data_only=True, read_only=True)
    ws = _pick_worksheet(wb, sheet_name)

    lines = [
        f"文件：{file_name}｜工作表：{ws.title}｜"
        f"共 {ws.max_row} 行 {ws.max_column} 列"
    ]
    max_rows = max(1, min(int(max_rows), ws.max_row))
    for idx, row in enumerate(
            ws.iter_rows(min_row=1, max_row=max_rows, values_only=True),
            start=1):
        cells = ["" if v is None else str(v) for v in row]
        if any(cells):
            lines.append(f"{idx}: " + " | ".join(cells))
    return "\n".join(lines)


def excel_write(file_name: str, sheet_name: str = "Sheet1",
                headers: list = None, rows: list = None) -> str:
    """新建/覆盖一个工作表并写入表头和数据"""
    headers = headers or []
    rows = rows or []
    path = _resolve(file_name)

    wb = Workbook() if not os.path.exists(path) else load_workbook(path)
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)

    if headers:
        ws.append([str(h) for h in headers])
    for row in rows:
        ws.append(list(row))

    wb.save(path)
    return (f"已写入 {file_name} 的「{sheet_name}」："
            f"表头 {len(headers)} 列，数据 {len(rows)} 行")


def excel_append(file_name: str, sheet_name: str = "Sheet1",
                 headers: list = None, rows: list = None) -> str:
    """在现有工作表末尾追加数据；表不存在时按表头新建"""
    rows = rows or []
    headers = headers or []
    path = _resolve(file_name)
    if not os.path.exists(path):
        return f"文件不存在：{file_name}，请先 excel_write"

    wb = load_workbook(path)
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(sheet_name)
        if headers:
            ws.append([str(h) for h in headers])

    for row in rows:
        ws.append(list(row))

    wb.save(path)
    return (f"已在 {file_name} 的「{sheet_name}」追加 {len(rows)} 行，"
            f"当前共 {ws.max_row} 行")


def _fmt(value) -> str:
    """数字格式化"""
    if isinstance(value, float):
        return f"{value:.2f}" if value != int(value) else str(int(value))
    return str(value)


def _read_dataframe(path: str, sheet_name: str = ""):
    """读取 DataFrame：未指定表名时自动跳过空表"""
    if sheet_name:
        return pd.read_excel(path, sheet_name=sheet_name)

    sheets = pd.read_excel(path, sheet_name=None)
    for _, frame in sheets.items():
        frame = frame.dropna(how="all")
        if not frame.empty and len(frame.columns) > 0:
            return frame
    return pd.DataFrame()


def excel_summarize(file_name: str, sheet_name: str = "",
                    group_by: str = "", aggregate: str = "sum",
                    columns: list = None) -> str:
    """按列分组汇总：sum/mean/count/max/min"""
    path = _resolve(file_name)
    if not os.path.exists(path):
        return f"文件不存在：{file_name}"

    df = _read_dataframe(path, sheet_name)
    df = df.dropna(how="all")
    if df.empty:
        return "表格是空的"

    agg_map = {"sum": "求和", "mean": "平均", "count": "计数",
               "max": "最大", "min": "最小"}
    if aggregate not in agg_map:
        return f"不支持的统计方式：{aggregate}"

    # 排除合计行
    if group_by:
        if group_by not in df.columns:
            return f"分组列不存在：{group_by}，可用列：{list(df.columns)}"
        df = df[df[group_by].notna()]
        df = df[~df[group_by].astype(str).isin(
            ["合计", "总计", "汇总", "小计", "总合计"])]
        if df.empty:
            return "排除合计行后没有数据"

    # 选出数值列
    numeric = df.select_dtypes(include="number").columns.tolist()
    if columns:
        target = [c for c in columns if c in numeric]
        # 容错：只有一个数值列时，允许模型用“销售金额”指代“金额”
        if not target and len(numeric) == 1:
            target = numeric
        if not target:
            return (f"指定的统计列不存在或不是数值列：{columns}；"
                    f"可用数值列：{numeric}")
    else:
        target = numeric
    if not target:
        return "没有可统计的数值列"

    lines = [f"文件：{file_name}｜统计：{agg_map[aggregate]}｜共 {len(df)} 行"]

    if group_by:
        result = df.groupby(group_by)[target].agg(aggregate).reset_index()
        for _, row in result.iterrows():
            parts = [f"{group_by}：{row[group_by]}"]
            for col in target:
                parts.append(f"{col} = {_fmt(row[col])}")
            lines.append(" | ".join(parts))
    else:
        for col in target:
            lines.append(f"{col}：{_fmt(df[col].agg(aggregate))}")

    return "\n".join(lines)
