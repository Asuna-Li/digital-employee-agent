# asr_test.py —— 按回车录音 5 秒，然后用本地 faster-whisper 识别
import time
import wave
import os

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000      # 16kHz，语音识别常用采样率
DURATION = 5             # 录音 5 秒
WAV_PATH = "tests/record.wav"
# 指向本地模型目录，彻底离线
MODEL_DIR = r"D:\my-agent\models\faster-whisper-small"


def record():
    """录 5 秒音频并存成 wav 文件"""
    print(f"开始录音 {DURATION} 秒，请说话……")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,                 # 单声道
        dtype="float32",
    )
    sd.wait()                       # 等待录音结束
    print("录音结束")

    # 浮点转 16 位整数，再写入 wav
    pcm = (audio * 32767).astype("int16")
    with wave.open(WAV_PATH, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())
    print("已保存：", WAV_PATH)


# 领域纠错词典：语音识别常见的同音字错误
CORRECTIONS = {
    "爆销": "报销",
    "省批": "审批",
    "审请": "申请",
    "部门经里": "部门经理",
    "总经里": "总经理",
}


def correct(text: str) -> str:
    """本地纠错：把常见同音字错误替换成正确词"""
    for wrong, right in CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def transcribe():
    """用本地模型识别 wav；首次运行会自动下载模型"""
    print("加载 faster-whisper 模型……")
    model = WhisperModel(
        MODEL_DIR,
        device="cpu",
        compute_type="int8",
    )

    # 关键：segments 和 info 在这里接收返回值，后面必须用到
    segments, info = model.transcribe(
        WAV_PATH,
        language="zh",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
        temperature=0.0,
        initial_prompt=(
            "以下是中文企业知识库内容，可能涉及："
            "报销、审批、金额、部门经理、总经理、年假、"
            "知识库、向量数据库、钉钉通知。"
        ),
    )

    # 1) 使用 segments：把每段文字拼起来
    text = "".join(seg.text for seg in segments)

    # 2) 本地纠错
    text = correct(text)

    # 3) 使用 info：打印识别语言
    print("识别语言：", info.language)
    print("识别结果：", text.strip())


if __name__ == "__main__":
    input("按回车开始录音……")
    record()
    transcribe()