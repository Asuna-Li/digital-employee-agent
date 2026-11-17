# 本地优先数字化员工 Agent

这是一个 Windows 本地优先的数字化员工项目，包含本地知识库问答、语音交互、短期与长期记忆、Excel 处理、报表生成、审批单生成、QQ 邮件和钉钉群文本通知。

## 架构

```text
PySide6 桌面客户端
        │ WebSocket / REST
        ▼
FastAPI 后端（127.0.0.1:8765）
        ├─ Ollama + Qwen2.5 本地大模型
        ├─ LlamaIndex + bge-m3 + Chroma 本地知识库
        ├─ SQLite 短期会话记忆
        ├─ Chroma 长期任务与偏好记忆
        ├─ SenseVoice ASR + Piper TTS
        ├─ Excel / 报表 / 审批单工具
        ├─ QQ 邮件工具
        └─ 钉钉群机器人工具
```

敏感文档默认只在本地处理。云端模式只用于脱敏后的通用问答，不查询本地知识库。

## 目录

```text
backend/        FastAPI、RAG、记忆、路由和工具
client/         PySide6 桌面客户端与语音前端
docs/           本地知识库文档
data/excel/     Excel 源文件
data/reports/   自动生成的报表
data/approvals/ 自动生成的审批单
models/         本地模型，不提交 Git
storage/        向量库和索引，不提交 Git
tests/          分模块测试与系统自检
```

## 环境要求

- Windows 10/11
- Python 3.13
- NVIDIA 显卡驱动
- Ollama
- 本地模型：`qwen2.5:7b-instruct-q4_K_M`

本地模型目录应为：

```text
models/
├─ bge-m3/
├─ sensevoice/
├─ piper/
│  ├─ zh_CN-huayan-medium.onnx
│  └─ zh_CN-huayan-medium.onnx.json
└─ vosk-model-small-cn-0.22/
```

## 首次安装

在 VS Code 中打开项目根目录，然后执行：

```powershell
cd D:\my-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull qwen2.5:7b-instruct-q4_K_M
```

如果 PowerShell 禁止激活脚本，可仅对当前终端放开权限：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

## 环境变量

编辑项目根目录的 `.env`：

```dotenv
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
CLOUD_MODEL=deepseek-chat

QQ_EMAIL=你的QQ邮箱
QQ_AUTH_CODE=QQ邮箱授权码

DINGTALK_WEBHOOK_URL=你的钉钉机器人Webhook
DINGTALK_SECRET=你的钉钉机器人加签密钥
```

不要提交 `.env`，也不要将密钥发到聊天、截图或日志中。

## 启动

后端终端：

```powershell
cd D:\my-agent
.\.venv\Scripts\Activate.ps1
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

客户端另开一个终端：

```powershell
cd D:\my-agent
.\.venv\Scripts\Activate.ps1
python -m client.main
```

健康检查：

```text
http://127.0.0.1:8765/api/health
```

## 工具能力

当前注册 11 个模型工具：

```text
create_approval_form
dingtalk_send
email_search
email_read
email_send
generate_report
excel_sheets
excel_read
excel_write
excel_append
excel_summarize
```

邮件和钉钉属于外发操作，模型调用工具后只创建待确认操作；必须由用户回复“确认”才会执行。

## 测试

不触发外部发送的钉钉工具测试：

```powershell
python -m tests.dingtalk_tools_test
```

完整系统自检：

```powershell
python -m tests.system_acceptance_check
```

系统自检只读取本地配置和文件，不发送邮件、钉钉消息或云端请求。

## 当前边界

- 钉钉群机器人当前只发送文本，不支持 Word 文件附件。
- 本地模式只回答知识库能够支持的内容，不把常识问题发送到云端。
- 云端模式不能调用 Excel、邮件、审批单、钉钉等本地工具。
- 生成的索引、模型、数据库、审批单和报表不进入 Git。
