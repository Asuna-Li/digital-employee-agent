# asr_sensevoice_test.py —— 用 SenseVoice 识别已有 wav
import os
import wave

import numpy as np
import sherpa_onnx

MODEL_DIR = r"D:\my-agent\models\sensevoice"


def read_wav(path: str) -> np.ndarray:
    """读取 16kHz 单声道 16bit wav，转成 float32"""
    with wave.open(path, "rb") as f:
        assert f.getframerate() == 16000, "采样率必须是 16000"
        assert f.getnchannels() == 1, "必须是单声道"
        assert f.getsampwidth() == 2, "必须是 16bit"
        data = f.readframes(f.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=os.path.join(MODEL_DIR, "model.onnx"),
        tokens=os.path.join(MODEL_DIR, "tokens.txt"),
        num_threads=4,
        use_itn=True,        # 数字、标点更自然
        debug=False,
    )

    samples = read_wav("tests/record.wav")
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, samples)
    recognizer.decode_stream(stream)

    print("识别结果：", stream.result.text.strip())


if __name__ == "__main__":
    main()