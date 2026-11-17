# asr.py —— 本地语音识别（SenseVoice + sherpa-onnx）
import os
import re
import wave

import numpy as np
import sherpa_onnx

# 项目根目录：D:\my-agent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(BASE_DIR, "models", "sensevoice")

# 常见同音字纠错，可按需补充
CORRECTIONS = {
    "爆销": "报销",
    "省批": "审批",
    "审请": "申请",
    "部门经里": "部门经理",
    "总经里": "总经理",
}

# 至少要有 2 个汉字，才认为是有效中文语音
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")

# 进程内只加载一次模型
_MODEL = None


def _get_model():
    """首次调用时加载 SenseVoice，之后复用"""
    global _MODEL
    if _MODEL is None:
        _MODEL = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=os.path.join(MODEL_DIR, "model.onnx"),
            tokens=os.path.join(MODEL_DIR, "tokens.txt"),
            num_threads=4,
            use_itn=True,
            debug=False,
        )
    return _MODEL


def _read_wav(path: str) -> np.ndarray:
    """读取 16kHz 单声道 16bit wav，转成 float32"""
    with wave.open(path, "rb") as f:
        if f.getframerate() != 16000:
            raise ValueError("只支持 16kHz 采样率的 wav")
        if f.getnchannels() != 1:
            raise ValueError("只支持单声道 wav")
        if f.getsampwidth() != 2:
            raise ValueError("只支持 16bit wav")
        data = f.readframes(f.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def _correct(text: str) -> str:
    """修正常见同音字错误"""
    for wrong, right in CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def transcribe_file(path: str) -> str:
    """识别一个 wav 文件；过滤噪声和英文误识别"""
    samples = _read_wav(path)
    recognizer = _get_model()

    stream = recognizer.create_stream()
    stream.accept_waveform(16000, samples)
    recognizer.decode_stream(stream)

    text = _correct(stream.result.text.strip())

    # 少于 2 个汉字，视为噪声/误识别（例如 "The."）
    if len(CJK_PATTERN.findall(text)) < 2:
        return ""

    return text