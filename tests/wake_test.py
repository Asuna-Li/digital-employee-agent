# wake_test.py —— VAD 门控 + 自由识别 + 问候-名字窗口唤醒
# 默认只输出状态变化，不打印每一帧的识别文本。

import json
import queue
import time

import sounddevice as sd
import webrtcvad
from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)          # 关闭 Vosk 内部日志

# ---------- 配置 ----------
MODEL_DIR = r"D:\my-agent\models\vosk-model-small-cn-0.22"

GREETINGS = ("你好", "您好")       # 问候词
NAME = "小莫"                      # 唤醒名字
WINDOW_SECONDS = 3.0               # 问候后等待名字的窗口
COOLDOWN_SECONDS = 2.0             # 唤醒后的冷却时间

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)   # 480 个采样点
VAD_LEVEL = 2                      # 0~3，越大越严格
HANGOVER_FRAMES = int(500 / FRAME_MS)        # 语音结束后继续送 0.5 秒
SILENCE_RESET_FRAMES = int(1500 / FRAME_MS)  # 静音 1.5 秒后重置识别器

SHOW_TEXT = False                  # True 时才打印识别文本，调试用

# ---------- 初始化 ----------
model = Model(MODEL_DIR)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)   # 自由识别，不用 grammar
vad = webrtcvad.Vad(VAD_LEVEL)
audio_queue = queue.Queue()

# 状态定义
STATE_IDLE = "IDLE"
STATE_GREETING = "GREETING"
STATE_WAKE = "WAKE"

STATE_LABELS = {
    STATE_IDLE: "待机",
    STATE_GREETING: "听到问候，等待名字",
    STATE_WAKE: "唤醒成功",
}

_current_state = None
greeting_time = 0.0
cooldown_until = 0.0
greeting_announced = False


def set_state(new_state: str):
    """只在状态变化时输出，避免刷屏"""
    global _current_state
    if new_state != _current_state:
        _current_state = new_state
        print(f"[状态] {STATE_LABELS.get(new_state, new_state)}")


def callback(indata, frames, time_info, status):
    """麦克风回调：把原始音频放入队列"""
    audio_queue.put(bytes(indata))


def normalize(text: str) -> str:
    """去掉空格和标点，把“您”统一成“你”"""
    return (
        text.replace("您", "你")
        .replace(" ", "")
        .replace("，", "")
        .replace(",", "")
        .replace("。", "")
        .replace("！", "")
        .replace("!", "")
    )


def check_wake(text: str) -> bool:
    """检查是否唤醒；返回 True 表示唤醒成功"""
    global greeting_time, cooldown_until, greeting_announced

    now = time.time()
    if now < cooldown_until:
        return False

    t = normalize(text)
    if not t:
        return False

    has_greeting = any(g in t for g in GREETINGS)
    has_name = NAME in t

    # 1) 一句话里同时出现问候和名字，例如“你好小莫”
    if has_greeting and has_name:
        cooldown_until = now + COOLDOWN_SECONDS
        greeting_announced = False
        set_state(STATE_WAKE)
        return True

    # 2) 只听到问候：打开等待窗口
    if has_greeting:
        greeting_time = now
        if not greeting_announced:
            greeting_announced = True
            set_state(STATE_GREETING)
        return False

    # 3) 窗口期内听到名字
    if has_name and (now - greeting_time) <= WINDOW_SECONDS:
        cooldown_until = now + COOLDOWN_SECONDS
        greeting_announced = False
        set_state(STATE_WAKE)
        return True

    # 4) 窗口过期，回到待机
    if (_current_state == STATE_GREETING
            and (now - greeting_time) > WINDOW_SECONDS):
        greeting_announced = False
        set_state(STATE_IDLE)

    return False


def main():
    hangover = 0          # 语音结束后剩余的尾音帧数
    silence_frames = 0    # 连续静音帧数

    set_state(STATE_IDLE)
    print(f"请说“{GREETINGS[0]}”，然后说“{NAME}”；也可以直接说“{GREETINGS[0]}{NAME}”。")

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_SIZE,
        dtype="int16",
        channels=1,
        callback=callback,
    ):
        while True:
            frame = audio_queue.get()                # 30ms 一帧
            is_speech = vad.is_speech(frame, SAMPLE_RATE)

            if is_speech:
                hangover = HANGOVER_FRAMES
                silence_frames = 0
            else:
                silence_frames += 1
                if hangover > 0:
                    hangover -= 1                    # 尾音保护
                else:
                    # 长时间静音：重置识别器，清掉残留
                    if silence_frames == SILENCE_RESET_FRAMES:
                        recognizer.Reset()
                        greeting_announced = False
                        set_state(STATE_IDLE)
                    continue                         # 静音帧不送识别

            # 只把语音帧（含尾音）送给 Vosk
            if recognizer.AcceptWaveform(frame):
                text = json.loads(recognizer.Result()).get("text", "")
                if SHOW_TEXT and text:
                    print("最终结果：", text)
                if check_wake(text):
                    break
            else:
                partial = json.loads(
                    recognizer.PartialResult()).get("partial", "")
                if SHOW_TEXT and partial:
                    print("临时结果：", partial)
                if check_wake(partial):
                    break

    print("已退出待机。")


if __name__ == "__main__":
    main()