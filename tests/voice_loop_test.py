# voice_loop_test.py —— 唤醒 -> 自动录音 -> 静音自动结束
# 只输出状态变化，不打印识别文本。

import json
import queue
import time
import wave

import sounddevice as sd
import webrtcvad
from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)

# ---------- 配置 ----------
MODEL_DIR = r"D:\my-agent\models\vosk-model-small-cn-0.22"
OUTPUT_WAV = "tests/voice_loop.wav"

GREETINGS = ("你好", "您好")
NAME = "小莫"
WINDOW_SECONDS = 3.0
COOLDOWN_SECONDS = 2.0

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480
VAD_LEVEL = 2
HANGOVER_FRAMES = int(500 / FRAME_MS)             # 唤醒阶段尾音 0.5 秒
SILENCE_RESET_FRAMES = int(1500 / FRAME_MS)       # 静音 1.5 秒重置识别器

# 录音阶段：说话后静音多久算说完
END_SILENCE_MS = 1200
END_SILENCE_FRAMES = int(END_SILENCE_MS / FRAME_MS)
MAX_RECORD_SECONDS = 15                            # 最长录音时间

# ---------- 状态 ----------
STATE_IDLE = "IDLE"
STATE_RECORDING = "RECORDING"
STATE_LABELS = {
    STATE_IDLE: "待机",
    STATE_RECORDING: "正在录音",
}
_current_state = None

# 唤醒窗口状态
greeting_time = 0.0
cooldown_until = 0.0
greeting_announced = False

# 初始化模型
model = Model(MODEL_DIR)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)
vad = webrtcvad.Vad(VAD_LEVEL)
audio_queue = queue.Queue()


def set_state(state: str):
    global _current_state
    if state != _current_state:
        _current_state = state
        print(f"[状态] {STATE_LABELS.get(state, state)}")


def callback(indata, frames, time_info, status):
    audio_queue.put(bytes(indata))


def normalize(text: str) -> str:
    return (text.replace("您", "你")
                .replace(" ", "")
                .replace("，", "").replace(",", "")
                .replace("。", "").replace("！", "").replace("!", ""))


def check_wake(text: str) -> bool:
    """检测唤醒词；返回 True 表示唤醒"""
    global greeting_time, cooldown_until, greeting_announced

    now = time.time()
    if now < cooldown_until:
        return False

    t = normalize(text)
    if not t:
        return False

    has_greeting = any(g in t for g in GREETINGS)
    has_name = NAME in t

    if has_greeting and has_name:
        cooldown_until = now + COOLDOWN_SECONDS
        greeting_announced = False
        return True

    if has_greeting:
        greeting_time = now
        greeting_announced = True
        return False

    if has_name and (now - greeting_time) <= WINDOW_SECONDS:
        cooldown_until = now + COOLDOWN_SECONDS
        greeting_announced = False
        return True

    return False


def save_wav(frames: list):
    """把收集到的音频帧写成一个 wav 文件"""
    with wave.open(OUTPUT_WAV, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(b"".join(frames))
    print(f"[状态] 录音结束，已保存 {OUTPUT_WAV}")


def main():
    hangover = 0
    silence_frames = 0

    recording = False
    record_frames = []
    record_start_time = 0.0
    record_silence = 0
    speech_seen = False

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
            frame = audio_queue.get()
            is_speech = vad.is_speech(frame, SAMPLE_RATE)
            now = time.time()

            # ---------------- 待机阶段：唤醒检测 ----------------
            if not recording:
                if is_speech:
                    hangover = HANGOVER_FRAMES
                    silence_frames = 0
                else:
                    silence_frames += 1
                    if hangover > 0:
                        hangover -= 1
                    else:
                        if silence_frames == SILENCE_RESET_FRAMES:
                            recognizer.Reset()
                            greeting_announced = False
                            set_state(STATE_IDLE)
                        continue

                if recognizer.AcceptWaveform(frame):
                    text = json.loads(recognizer.Result()).get("text", "")
                    if check_wake(text):
                        recording = True
                        record_frames = [frame]      # 从当前帧开始录
                        record_start_time = now
                        record_silence = 0
                        speech_seen = True
                        set_state(STATE_RECORDING)
                else:
                    partial = json.loads(
                        recognizer.PartialResult()).get("partial", "")
                    if check_wake(partial):
                        recording = True
                        record_frames = [frame]
                        record_start_time = now
                        record_silence = 0
                        speech_seen = True
                        set_state(STATE_RECORDING)
                continue

            # ---------------- 录音阶段：收集 + 静音判断 ----------------
            record_frames.append(frame)

            if is_speech:
                speech_seen = True
                record_silence = 0
            else:
                if speech_seen:
                    record_silence += 1

            # 说完了：静音达到阈值
            if speech_seen and record_silence >= END_SILENCE_FRAMES:
                save_wav(record_frames)
                break

            # 超时保护
            if now - record_start_time > MAX_RECORD_SECONDS:
                save_wav(record_frames)
                break

    print("已退出语音循环。")


if __name__ == "__main__":
    main()