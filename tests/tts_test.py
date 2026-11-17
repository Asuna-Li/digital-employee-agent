# tts_test.py —— 本地 TTS：朗读文本并保存 wav
import pyttsx3

TEXT = "报销金额超过五千元需要部门经理审批。"
VOICE_INDEX = 0          # 换成你上面查到的中文语音编号
WAV_PATH = "tests/tts_out.wav"


def main():
    engine = pyttsx3.init()

    # 选择中文语音
    voices = engine.getProperty("voices")
    if VOICE_INDEX < len(voices):
        engine.setProperty("voice", voices[VOICE_INDEX].id)

    # 语速和音量
    engine.setProperty("rate", 180)      # 语速，默认约 200
    engine.setProperty("volume", 1.0)    # 音量 0~1

    # 1. 直接朗读
    engine.say(TEXT)
    engine.runAndWait()

    # 2. 保存为 wav 文件（供客户端播放/测试）
    engine.save_to_file(TEXT, WAV_PATH)
    engine.runAndWait()
    print("已保存：", WAV_PATH)


if __name__ == "__main__":
    main()