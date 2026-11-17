# piper_test.py —— 适配不同 piper-tts 版本
import os
import wave

from piper.voice import PiperVoice

MODEL_PATH = r"D:\my-agent\models\piper\zh_CN-huayan-medium.onnx"
CONFIG_PATH = r"D:\my-agent\models\piper\zh_CN-huayan-medium.onnx.json"
OUT_PATH = "tests/piper_out.wav"
TEXT = "报销金额超过五千元需要部门经理审批。"


def synthesize(text: str, out_path: str):
    voice = PiperVoice.load(MODEL_PATH, config_path=CONFIG_PATH)

    with wave.open(out_path, "wb") as wav_file:
        # 先写 WAV 头
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(voice.config.sample_rate)

        if hasattr(voice, "synthesize_wav"):
            # 新版 API：直接写入 wave 文件
            voice.synthesize_wav(text, wav_file)
        elif hasattr(voice, "synthesize_stream_raw"):
            # 旧版 API：逐块写入 PCM
            for chunk in voice.synthesize_stream_raw(text):
                wav_file.writeframes(chunk)
        else:
            # 再退一步：某些版本 synthesize 直接接受 wave 文件
            voice.synthesize(text, wav_file)

    size = os.path.getsize(out_path)
    print(f"已生成：{out_path}，大小：{size} 字节")


if __name__ == "__main__":
    synthesize(TEXT, OUT_PATH)