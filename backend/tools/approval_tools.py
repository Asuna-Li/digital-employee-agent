# approval_tools.py —— 生成审批单 Word 文件的工具

import os
from datetime import datetime

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


# 项目根目录：backend/tools/approval_tools.py 向上三层，即 D:\my-agent
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# 所有审批单统一保存到此目录，避免散落在项目根目录。
APPROVAL_DIR = os.path.join(BASE_DIR, "data", "approvals")
os.makedirs(APPROVAL_DIR, exist_ok=True)


def _set_run(run, size: int = 12, bold: bool = False) -> None:
    """统一设置一段文字的字体、字号和加粗状态。"""
    run.font.name = "宋体"
    run.font.size = Pt(size)
    run.bold = bold

    # python-docx 只设置 font.name 时，中文仍可能回退到其他字体。
    # eastAsia 才能明确指定 Word 中的中文字体。
    run_properties = run._element.get_or_add_rPr()
    run_fonts = run_properties.get_or_add_rFonts()
    run_fonts.set(qn("w:eastAsia"), "宋体")


def _fill_cell(
    cell,
    text: str,
    *,
    bold: bool = False,
    center: bool = False,
) -> None:
    """向表格单元格写入并格式化文字。"""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
        if center
        else WD_ALIGN_PARAGRAPH.LEFT
    )

    # 单元格可能已有空 run；直接添加新 run 更稳定。
    run = paragraph.add_run(str(text))
    _set_run(run, bold=bold)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _safe_filename_part(value: str, fallback: str) -> str:
    """清理 Windows 文件名不允许的字符。"""
    value = str(value or "").strip()
    for character in '\\/:*?"<>|':
        value = value.replace(character, "_")
    return value.strip() or fallback


def _normalize_form_type(form_type: str) -> str:
    """把“通用审批单”“采购申请”等输入统一成简短类型名。"""
    form_type = str(form_type or "通用").strip() or "通用"

    # 防止最终标题变成“通用审批单审批单”。
    if form_type.endswith("审批单"):
        form_type = form_type[:-3].strip()
    elif form_type.endswith("申请"):
        form_type = form_type[:-2].strip()

    return form_type or "通用"


def _normalize_date(date: str) -> str:
    """未提供日期时使用当天日期。"""
    return str(date or "").strip() or datetime.now().strftime("%Y-%m-%d")


def create_approval_form(
    form_type: str = "通用",
    applicant: str = "",
    department: str = "",
    amount: str = "",
    reason: str = "",
    date: str = "",
    approver: str = "",
) -> str:
    """
    生成审批单并返回文字结果。

    参数：
        form_type：审批类型，例如通用、采购、请假、用款。
        applicant：申请人，必填。
        department：申请人部门。
        amount：金额，可以是数字或带单位的字符串。
        reason：申请事由。
        date：申请日期；留空时使用当天日期。
        approver：审批人；不知道时写“待指定”。

    返回：
        包含生成文件绝对路径和审批单摘要的字符串。
    """
    applicant = str(applicant or "").strip()
    if not applicant:
        return "缺少必填字段：申请人。请先确认申请人姓名。"

    department = str(department or "").strip()
    amount = str(amount or "").strip()
    reason = (
        str(reason or "")
        .strip()
        .replace("\r\n", " ")
        .replace("\n", " ")
    )
    approver = str(approver or "").strip()
    form_type = _normalize_form_type(form_type)
    apply_date = _normalize_date(date)

    now = datetime.now()
    document_no = f"AP{now.strftime('%Y%m%d%H%M%S')}"

    document = Document()

    # 页面设置为 A4，左右页边距 2 厘米，整体视觉更接近正式审批单。
    section = document.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

    # 设置 Normal 样式，避免正文出现风格不一致。
    normal_style = document.styles["Normal"]
    normal_style.font.name = "宋体"
    normal_style.font.size = Pt(12)
    normal_style_rpr = normal_style.element.get_or_add_rPr()
    normal_style_fonts = normal_style_rpr.get_or_add_rFonts()
    normal_style_fonts.set(qn("w:eastAsia"), "宋体")

    # 标题。
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(12)
    _set_run(title.add_run(f"{form_type}审批单"), size=18, bold=True)

    # 主信息表。
    info_rows = [
        ("审批单编号", document_no),
        ("申请人", applicant),
        ("部门", department or "未填写"),
        ("申请日期", apply_date),
        ("审批类型", form_type),
        ("金额（元）", amount or "——"),
        ("事由说明", reason or "（未填写）"),
        ("审批人", approver or "（待指定）"),
    ]

    info_table = document.add_table(rows=len(info_rows), cols=2)
    info_table.style = "Table Grid"
    info_table.autofit = False

    label_width = Cm(4.0)
    value_width = Cm(13.0)
    for row_index, (label, value) in enumerate(info_rows):
        row = info_table.rows[row_index]
        row.cells[0].width = label_width
        row.cells[1].width = value_width
        _fill_cell(row.cells[0], label, bold=True, center=True)
        _fill_cell(row.cells[1], value)

    # 审批意见书写区。
    opinion = document.add_paragraph()
    opinion.paragraph_format.space_before = Pt(18)
    opinion.paragraph_format.space_after = Pt(8)
    _set_run(opinion.add_run("审批人意见："), bold=True)

    opinion_tip = document.add_paragraph()
    _set_run(opinion_tip.add_run("（本区域留空，由审批人填写）"), size=11)

    # 底部签字区使用无边框两列表格：
    # 第一行左侧放申请人签字，右侧放审批人签字；
    # 第二行只在右侧放日期，从而让日期靠右并位于审批人签字下方。
    document.add_paragraph()
    signature_table = document.add_table(rows=2, cols=2)
    signature_table.autofit = False

    left_width = Cm(7.0)
    right_width = Cm(10.0)
    for row in signature_table.rows:
        row.cells[0].width = left_width
        row.cells[1].width = right_width

    applicant_label = "申请人签字："
    approver_label = "审批人签字："
    date_label = "日期："

    _fill_cell(
        signature_table.rows[0].cells[0],
        f"{applicant_label}____________",
    )
    _fill_cell(
        signature_table.rows[0].cells[1],
        f"{approver_label}____________",
    )

    # “日期：”比“审批人签字：”短。补全角空格后两行冒号处于同一水平位置。
    # 日期紧跟冒号显示，不再使用制表位，避免冒号和日期之间出现大段空白。
    padding = "\u3000" * max(0, len(approver_label) - len(date_label))
    date_cell = signature_table.rows[1].cells[1]
    date_paragraph = date_cell.paragraphs[0]
    _set_run(date_paragraph.add_run(f"{padding}{date_label}{apply_date}"))
    date_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    # 文件名包含类型、申请人和精确到秒的时间，避免覆盖旧文件。
    safe_type = _safe_filename_part(form_type, "通用")
    safe_applicant = _safe_filename_part(applicant, "未填写")
    file_name = (
        f"审批单_{safe_type}_{safe_applicant}_"
        f"{now.strftime('%Y%m%d_%H%M%S')}.docx"
    )
    output_path = os.path.join(APPROVAL_DIR, file_name)
    document.save(output_path)

    missing_fields = []
    if not department:
        missing_fields.append("部门")
    if not amount:
        missing_fields.append("金额")
    if not reason:
        missing_fields.append("事由说明")
    if not approver:
        missing_fields.append("审批人")

    missing_hint = (
        f"\n未填写字段：{'、'.join(missing_fields)}"
        if missing_fields
        else ""
    )

    return (
        f"审批单已生成：{os.path.abspath(output_path)}\n"
        f"申请人：{applicant}｜部门：{department or '未填写'}｜"
        f"类型：{form_type}｜金额：{amount or '无'}｜"
        f"日期：{apply_date}｜审批人：{approver or '待指定'}"
        f"{missing_hint}"
    )
