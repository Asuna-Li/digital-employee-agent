# system_acceptance_check.py —— 不触发邮件、钉钉或云端外发的系统自检
import importlib.util
import sys
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent.parent
failures = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[通过] {name}")
        return
    message = f"{name}：{detail}" if detail else name
    failures.append(message)
    print(f"[失败] {message}")


def package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


print("=" * 60)
print("数字化员工系统自检（不会执行任何外发操作）")
print("=" * 60)

check(
    "Python 版本",
    sys.version_info >= (3, 13),
    f"当前 {sys.version.split()[0]}",
)

for package in (
    "fastapi",
    "uvicorn",
    "PySide6",
    "requests",
    "dotenv",
    "openai",
    "llama_index",
    "chromadb",
    "pandas",
    "openpyxl",
    "docx",
    "sherpa_onnx",
    "piper",
    "vosk",
):
    check(f"Python 包 {package}", package_available(package))

env_path = BASE_DIR / ".env"
check(".env 文件存在", env_path.exists())
env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
for key in (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "QQ_EMAIL",
    "QQ_AUTH_CODE",
    "DINGTALK_WEBHOOK_URL",
    "DINGTALK_SECRET",
):
    configured = any(
        line.startswith(f"{key}=") and line.split("=", 1)[1].strip()
        for line in env_text.splitlines()
    )
    check(f"环境变量 {key}", configured, "未配置或值为空")

gitignore = BASE_DIR / ".gitignore"
gitignore_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
check(
    ".env 已加入 .gitignore",
    ".env" in gitignore_text.splitlines(),
)

model_checks = {
    "bge-m3 配置": BASE_DIR / "models" / "bge-m3" / "config.json",
    "bge-m3 权重": BASE_DIR / "models" / "bge-m3" / "pytorch_model.bin",
    "SenseVoice 模型": BASE_DIR / "models" / "sensevoice" / "model.onnx",
    "SenseVoice 词表": BASE_DIR / "models" / "sensevoice" / "tokens.txt",
    "Piper 语音模型": (
        BASE_DIR / "models" / "piper" / "zh_CN-huayan-medium.onnx"
    ),
    "Piper 配置": (
        BASE_DIR / "models" / "piper" / "zh_CN-huayan-medium.onnx.json"
    ),
    "Vosk 唤醒词模型": BASE_DIR / "models" / "vosk-model-small-cn-0.22",
}
for name, path in model_checks.items():
    check(name, path.exists(), str(path))

for relative in (
    "docs",
    "data/excel",
    "data/reports",
    "data/approvals",
    "storage",
):
    path = BASE_DIR / relative
    check(f"目录 {relative}", path.is_dir(), str(path))

try:
    from backend.llm import tool_agent  # noqa: F401
    from backend.llm.router import (
        _is_approval_request,
        _is_dingtalk_request,
        _is_email_request,
        _is_excel_request,
        _is_report_request,
    )
    from backend.tools.registry import REGISTRY

    required_tools = {
        "create_approval_form",
        "dingtalk_send",
        "email_search",
        "email_read",
        "email_send",
        "generate_report",
        "excel_sheets",
        "excel_read",
        "excel_write",
        "excel_append",
        "excel_summarize",
    }
    missing_tools = required_tools - set(REGISTRY)
    check(
        "11 个工具全部注册",
        not missing_tools,
        f"缺少 {sorted(missing_tools)}",
    )
    check("审批单路由", _is_approval_request("生成一份采购审批单"))
    check("报表路由", _is_report_request("生成部门销售报表"))
    check("Excel 路由", _is_excel_request("读取测试销售.xlsx"))
    check("邮件路由", _is_email_request("发送邮件给 test@example.com"))
    check("钉钉路由", _is_dingtalk_request("给钉钉群发送通知：测试"))
except Exception as exc:
    failures.append(f"工具和路由自检异常：{exc}")
    print(f"[失败] 工具和路由自检异常：{exc}")

try:
    response = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
    response.raise_for_status()
    check("Ollama 服务", True)
except Exception as exc:
    check("Ollama 服务", False, str(exc))

print("=" * 60)
if failures:
    print(f"自检完成：{len(failures)} 项失败")
    for item in failures:
        print(f"- {item}")
    raise SystemExit(1)

print("自检完成：全部通过，未执行邮件、钉钉或云端外发。")
