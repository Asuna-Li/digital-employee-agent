# report_tools.py —— 从 Excel 生成带汇总表和柱状图的报表
import os
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXCEL_DIR = os.path.join(BASE_DIR, "data", "excel")
REPORT_DIR = os.path.join(BASE_DIR, "data", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

AGG_LABELS = {
    "sum": "求和",
    "mean": "平均",
    "count": "计数",
    "max": "最大",
    "min": "最小",
}
SKIP_GROUPS = {"合计", "总计", "汇总", "小计", "总合计"}


def _resolve_source(file_name: str) -> str:
    safe = os.path.basename(str(file_name).replace("\\", "/"))
    if not safe.endswith((".xlsx", ".xlsm")):
        raise ValueError("仅支持 .xlsx / .xlsm 源文件")
    return os.path.join(EXCEL_DIR, safe)


def _safe_name(name: str) -> str:
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "报表"


def _fmt(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return f"{int(number):,}"
    return f"{number:,.2f}"


def _read_source(path: str, sheet_name: str = "") -> pd.DataFrame:
    """未指定工作表时，自动选择第一个有数据的表"""
    if sheet_name:
        return pd.read_excel(path, sheet_name=sheet_name)

    frames = pd.read_excel(path, sheet_name=None)
    for _, frame in frames.items():
        frame = frame.dropna(how="all")
        if not frame.empty and len(frame.columns) > 0:
            return frame
    return pd.DataFrame()


def generate_report(source_file: str, sheet_name: str = "",
                    group_by: str = "", aggregate: str = "sum",
                    columns: list = None, report_title: str = "") -> str:
    """读取 Excel -> pandas 汇总 -> 生成带图表的 xlsx 报表"""
    try:
        source_path = _resolve_source(source_file)
    except ValueError as e:
        return str(e)

    if not os.path.exists(source_path):
        return f"源文件不存在：{source_file}"

    try:
        df = _read_source(source_path, sheet_name)
    except Exception as e:
        return f"读取源文件失败：{e}"

    df = df.dropna(how="all")
    if df.empty:
        return "源文件没有可用的数据"

    aggregate = (aggregate or "sum").strip()
    if aggregate not in AGG_LABELS:
        return f"不支持的统计方式：{aggregate}"

    group_by = (group_by or "").strip()
    if group_by:
        if group_by not in df.columns:
            return f"分组列不存在：{group_by}；可用列：{list(df.columns)}"
        df = df[df[group_by].notna()]
        df = df[~df[group_by].astype(str).isin(SKIP_GROUPS)]
        if df.empty:
            return "排除合计行后没有数据"

    # 选出数值列
    numeric = df.select_dtypes(include="number").columns.tolist()
    if columns:
        target = [c for c in columns if c in numeric]
        if not target and len(numeric) == 1:
            target = numeric
    else:
        target = numeric
    if aggregate != "count" and not target:
        return f"没有可统计的数值列；可用数值列：{numeric}"

    label = AGG_LABELS[aggregate]

    # 计算汇总
    if group_by:
        if aggregate == "count":
            result = df.groupby(group_by, dropna=False).size().reset_index(name="记录数")
        else:
            result = df.groupby(group_by, dropna=False)[target].agg(aggregate).reset_index()
            result.insert(1, "记录数", df.groupby(group_by, dropna=False).size().values)
        result = result.rename(columns={
            c: f"{c}（{label}）" for c in target
        })
    else:
        if aggregate == "count":
            result = pd.DataFrame({"记录数": [len(df)]})
        else:
            result = df[target].agg(aggregate).to_frame().T
            result = result.rename(columns={
                c: f"{c}（{label}）" for c in target
            })

    # 合计行
    display = result.copy()
    if group_by:
        total = {group_by: "合计", "记录数": len(df)}
        if aggregate != "count":
            totals = df[target].agg(aggregate)
            for c in target:
                total[f"{c}（{label}）"] = totals[c]
        display = pd.concat([display, pd.DataFrame([total])], ignore_index=True)

    # 写 Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "统计报表"

    now = datetime.now()
    base = os.path.splitext(os.path.basename(source_path))[0]
    title_text = (report_title or "").strip() or f"{base}统计报表"

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    c = ws.cell(row=1, column=1, value=title_text)
    c.font = Font(name="微软雅黑", size=14, bold=True)
    c.alignment = Alignment(horizontal="center")

    meta = [
        ("数据来源", f"{source_file}｜工作表：{sheet_name or '自动选择'}"),
        ("统计口径", f"按「{group_by}」对 {', '.join(target)} 做「{label}」"
                     if group_by else f"对 {', '.join(target)} 做「{label}」"),
        ("生成时间", now.strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for i, (key, value) in enumerate(meta, start=3):
        a = ws.cell(row=i, column=1, value=f"{key}：")
        a.font = Font(name="微软雅黑", size=10, bold=True)
        a.alignment = Alignment(horizontal="right")
        ws.cell(row=i, column=2, value=value).font = Font(name="微软雅黑", size=10)

    start_row = 8
    headers = list(display.columns)
    for j, head in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=j, value=head)
        cell.font = Font(name="微软雅黑", size=10, bold=True)
        cell.fill = PatternFill("solid", fgColor="E8EEF5")
        cell.alignment = Alignment(horizontal="center")

    data_row_count = len(result)
    for i, row in display.iterrows():
        excel_row = start_row + 1 + i
        for j, head in enumerate(headers, start=1):
            value = row[head]
            cell = ws.cell(row=excel_row, column=j, value=value)
            cell.font = Font(name="微软雅黑", size=10)
            if isinstance(value, (int, float)):
                cell.number_format = "#,##0.00"

    for j, head in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(j)].width = max(len(str(head)) + 4, 10)

    # 柱状图（不包含合计行）
    if group_by and data_row_count > 0:
        agg_cols = [j + 1 for j, h in enumerate(headers) if "（" in str(h)]
        if agg_cols:
            chart = BarChart()
            chart.type = "col"
            chart.title = title_text
            chart.x_axis.title = group_by
            chart.y_axis.title = "、".join(target)
            chart_last_row = start_row + data_row_count
            data_ref = Reference(ws, min_col=min(agg_cols), min_row=start_row,
                                 max_col=max(agg_cols), max_row=chart_last_row)
            cats_ref = Reference(ws, min_col=1, min_row=start_row + 1,
                                 max_row=chart_last_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)
            ws.add_chart(chart, "H5")

    stamp = now.strftime("%Y%m%d_%H%M%S")
    out_name = f"报表_{_safe_name(title_text)}_{stamp}.xlsx"
    out_path = os.path.join(REPORT_DIR, out_name)
    wb.save(out_path)

    lines = [f"报表已生成：{os.path.abspath(out_path)}"]
    lines.append(f"统计口径：按「{group_by}」对 {', '.join(target)} 做「{label}」"
                 if group_by else f"统计口径：对 {', '.join(target)} 做「{label}」")
    for _, row in display.iterrows():
        parts = []
        if group_by:
            parts.append(f"{group_by}：{row[group_by]}")
        for h in headers:
            if h == group_by:
                continue
            parts.append(f"{h} = {_fmt(row[h])}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)
