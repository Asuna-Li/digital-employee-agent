import threading

from client.voice_frontend import VoiceFrontend

MODEL_DIR = r"D:\my-agent\models\vosk-model-small-cn-0.22"

_idle_timer = None


def on_record_done(frontend, path: str):
    global _idle_timer
    print("[事件] 录音完成：", path)

    # 模拟后端处理 + TTS 播报：进入播报状态，8 秒后回到待机
    frontend.set_speaking()
    if _idle_timer:
        _idle_timer.cancel()
    _idle_timer = threading.Timer(8.0, frontend.set_idle)
    _idle_timer.start()


def main():
    frontend = VoiceFrontend(
        MODEL_DIR,
        on_wake=lambda: print("[事件] 已唤醒"),
        on_record_done=lambda path: on_record_done(frontend, path),
        on_barge_in=lambda: print("[事件] 检测到打断"),
        on_state=lambda state: print("[状态]", state),
        on_error=lambda message: print("[错误]", message),
    )

    print("请说：你好小莫，然后提问；播报阶段再说一句话测试打断。")
    frontend.start()
    input("按回车退出。\n")
    frontend.stop()


if __name__ == "__main__":
    main()