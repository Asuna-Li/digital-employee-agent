# vad_test.py —— 实时检测有没有人在说话
import collections

import sounddevice as sd
import webrtcvad

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)   # 30ms = 480 个采样点
VAD_LEVEL = 2                                     # 0~3，越大越严格

vad = webrtcvad.Vad(VAD_LEVEL)
ring = collections.deque(maxlen=20)               # 保存最近 20 帧


def callback(indata, frames, time_info, status):
    """每 30ms 回调一次，判断这一帧是不是语音"""
    pcm = (indata[:, 0] * 32767).astype("int16").tobytes()
    is_speech = vad.is_speech(pcm, SAMPLE_RATE)
    ring.append(is_speech)
    print("语音" if is_speech else "静音", end="", flush=True)


def main():
    print("开始监听，按 Ctrl+C 结束……")
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=FRAME_SIZE,
        callback=callback,
    ):
        while True:
            sd.sleep(1000)


if __name__ == "__main__":
    main()