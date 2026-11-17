# ws_smoke.py —— 不启动客户端，直接测试后端 WebSocket 事件链路
import asyncio
import json

import websockets


async def main():
    uri = "ws://127.0.0.1:8765/ws"
    async with websockets.connect(uri) as ws:
        print("已连接")
        # 后端连接后会先发两条状态事件
        for _ in range(2):
            print("收到:", await ws.recv())

        # 模拟客户端发送一条文字请求
        await ws.send(json.dumps({
            "event": "user_text",
            "text": "报销流程是什么？",
            "mode": "local",
        }, ensure_ascii=False))

        # 持续接收，直到回答结束
        while True:
            msg = json.loads(await ws.recv())
            print("事件:", msg.get("event"), "|", msg.get("text", ""))
            if msg.get("event") == "assistant_done":
                break


asyncio.run(main())