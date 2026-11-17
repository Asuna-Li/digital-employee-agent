# voice_api_test.py —— 用已录好的 wav 测试语音接口
import json

import requests

URL = "http://127.0.0.1:8765/api/voice/ask"

with open("tests/record.wav", "rb") as f:
    response = requests.post(
        URL,
        files={"file": ("record.wav", f, "audio/wav")},
        data={"mode": "local"},
        timeout=300,
    )

print("HTTP 状态：", response.status_code)
print(json.dumps(response.json(), ensure_ascii=False, indent=2))