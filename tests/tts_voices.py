# tts_voices.py —— 列出系统可用的 TTS 语音
import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty("voices")

for i, voice in enumerate(voices):
    print(i, "|", voice.name, "|", voice.languages)