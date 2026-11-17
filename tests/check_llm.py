# check_llm.py —— 验证 LlamaIndex 能调用本地 Ollama 模型
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama

MODEL_NAME = "qwen2.5:7b-instruct-q4_K_M"   # 如果你用的是其他 tag，改这里

# 关键：context_window 设大一点，否则长文档会被截断
Settings.llm = Ollama(
    model=MODEL_NAME,
    base_url="http://localhost:11434",
    request_timeout=120.0,
    context_window=8192,
    keep_alive="5m",          # 空闲 5 分钟卸载；设 "0" 表示用完立即卸载
    # 如果回答被截断，再加这行：
    # additional_kwargs={"num_ctx": 8192},
)

response = Settings.llm.complete("请用一句中文介绍你自己。")
print("模型回答：", response)