# voice_frontend.py —— 语音前端状态机：唤醒 -> 录音 -> 等待 -> 播报中打断
"""供桌面客户端调用；所有音频都在本机处理，不上传。"""
import numpy as np

import json
import os
import queue
import tempfile
import threading
import time
import wave

import sounddevice as sd
import webrtcvad
from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)


class VoiceFrontend:
    """语音前端：常听唤醒 + 自动录音 + 播报中打断检测"""

    STATE_WAKE = "待机"
    STATE_RECORDING = "正在录音"
    STATE_WAITING = "处理中"
    STATE_SPEAKING = "播报中"

    def __init__(self, model_dir: str, greeting=("你好", "您好"),
                 name="小莫", on_wake=None, on_record_done=None,
                 on_barge_in=None, on_state=None, on_error=None):
        self.model_dir = model_dir
        self.greetings = greeting
        self.name = name

        # 回调：由音频线程调用，客户端里应转发成 Qt 信号
        self.on_wake = on_wake or (lambda: None)
        self.on_record_done = on_record_done or (lambda path: None)
        self.on_barge_in = on_barge_in or (lambda: None)
        self.on_state = on_state or (lambda state: None)
        self.on_error = on_error or (lambda message: None)

        # 音频参数
        self.sample_rate = 16000
        self.frame_ms = 30
        self.frame_size = int(self.sample_rate * self.frame_ms / 1000)

        self.vad = webrtcvad.Vad(2)
        self.hangover_frames = int(500 / self.frame_ms)
        self.silence_reset_frames = int(1500 / self.frame_ms)
        self.end_silence_frames = int(800 / self.frame_ms)
        self.max_record_seconds = 15
        # 打断要求：连续 500ms 语音，且音量超过阈值
        self.barge_frames = max(1, int(500 / self.frame_ms))
        self.barge_rms_threshold = 500      # int16 音频 RMS 阈值，可按需调
        self.speaking_guard_frames = int(600 / self.frame_ms)  # 播报开始保护期
        self.current_guard = 0

        self.wake_cooldown_frames = int(500 / self.frame_ms)   # 唤醒后忽略 0.5 秒
        self.wait_speech_seconds = 6.0                         # 最多等 6 秒让你说话
        self.min_speech_frames = int(500 / self.frame_ms)      # 至少 500ms 有效语音
        self.speech_frames = 0
        self.cooldown_frames = 0
        
        # 模型与识别器
        self.model = Model(model_dir)
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.audio_queue = queue.Queue()

        # 线程与状态
        self._lock = threading.Lock()
        self._mode = "wake"
        self._running = False
        self._pending_start = False
        self._thread = None
        self._stream = None

        # 唤醒窗口状态
        self.greeting_time = 0.0
        self.cooldown_until = 0.0
        self.greeting_announced = False

        # 录音状态
        self.record_frames = []
        self.record_start = 0.0
        self.record_silence = 0
        self.speech_seen = False

        # 打断状态
        self.barge_run = 0
        self.output_wav = os.path.join(tempfile.gettempdir(),
                                       "voice_question.wav")

    def start(self):
        """启动常听唤醒循环"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止并释放音频流"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def trigger_manual(self):
        """手动触发录音（对应“按下说话”按钮）"""
        with self._lock:
            self._pending_start = True

    def set_speaking(self):
        """进入播报状态：先静默 600ms，避免播放起始音触发打断"""
        self.barge_run = 0
        self.current_guard = self.speaking_guard_frames
        self._set_mode(self.STATE_SPEAKING)   # 触发状态回调

    def set_idle(self):
        """回到待机：重新等待唤醒词"""
        with self._lock:
            self.recognizer.Reset()
            self.greeting_announced = False
            self.barge_run = 0
        self._set_mode(self.STATE_WAKE)       # 触发状态回调

    def _set_mode(self, mode: str):
        with self._lock:
            if self._mode == mode:
                return
            self._mode = mode
        self.on_state(mode)

    def _get_mode(self):
        with self._lock:
            return self._mode

    def _normalize(self, text: str) -> str:
        return (text.replace("您", "你")
                    .replace(" ", "")
                    .replace("，", "").replace(",", "")
                    .replace("。", "").replace("！", "").replace("!", ""))

    def _check_wake(self, text: str) -> bool:
        now = time.time()
        if now < self.cooldown_until:
            return False

        t = self._normalize(text)
        if not t:
            return False

        has_greeting = any(g in t for g in self.greetings)
        has_name = self.name in t

        if has_greeting and has_name:
            self.cooldown_until = now + 2.0
            self.greeting_announced = False
            return True

        if has_greeting:
            self.greeting_time = now
            if not self.greeting_announced:
                self.greeting_announced = True
            return False

        if has_name and (now - self.greeting_time) <= 3.0:
            self.cooldown_until = now + 2.0
            self.greeting_announced = False
            return True

        return False

    def _begin_recording(self, frame: bytes, speech_seen: bool,
                         after_wake: bool = False):
        self.record_frames = []
        self.record_start = time.time()
        self.record_silence = 0
        self.speech_seen = speech_seen
        self.speech_frames = 1 if speech_seen else 0
        # 唤醒后先忽略一小段，避免把唤醒词尾音录进去
        self.cooldown_frames = self.wake_cooldown_frames if after_wake else 0
        self._set_mode(VoiceFrontend.STATE_RECORDING)

    def _finish_recording(self):
        # 有效语音不足：判为误触发
        if self.speech_frames < self.min_speech_frames:
            self._abort_recording("没有检测到有效语音，请重试。")
            return

        try:
            with wave.open(self.output_wav, "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(self.sample_rate)
                f.writeframes(b"".join(self.record_frames))
        except Exception as e:
            self.on_error(f"保存录音失败：{e}")
            self.record_frames = []
            return

        self.record_frames = []
        # 先进入“处理中”，外部再根据需要调用 set_speaking / set_idle
        self._set_mode(VoiceFrontend.STATE_WAITING)
        self.on_record_done(self.output_wav)

    def _callback(self, indata, frames, time_info, status):
        self.audio_queue.put(bytes(indata))

    def _abort_recording(self, message: str):
        self.record_frames = []
        self.on_error(message)
        self._set_mode(VoiceFrontend.STATE_WAKE)

    def _loop(self):
        hangover = 0
        silence_frames = 0

        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                dtype="int16",
                channels=1,
                callback=self._callback,
            )
            self._stream.start()
            self.on_state(VoiceFrontend.STATE_WAKE)

            while self._running:
                frame = self.audio_queue.get()
                is_speech = self.vad.is_speech(frame, self.sample_rate)
                mode = self._get_mode()

                # 手动触发录音
                with self._lock:
                    pending = self._pending_start
                    self._pending_start = False
                if pending:
                    self._begin_recording(frame, speech_seen=False)
                    continue

                # 录音阶段
                if mode == VoiceFrontend.STATE_RECORDING:
                    # 唤醒后的冷却期：直接丢弃，不记录
                    if self.cooldown_frames > 0:
                        self.cooldown_frames -= 1
                        continue

                    self.record_frames.append(frame)

                    if is_speech:
                        self.speech_seen = True
                        self.speech_frames += 1
                        self.record_silence = 0
                    elif self.speech_seen:
                        self.record_silence += 1

                    now = time.time()

                    # 一直没说话：超时放弃，回到待机
                    if (not self.speech_seen
                            and now - self.record_start > self.wait_speech_seconds):
                        self._abort_recording("没有听到问题，请重试。")
                        continue

                    # 说话后停顿够长：结束录音
                    if (self.speech_seen
                            and self.record_silence >= self.end_silence_frames):
                        self._finish_recording()
                    elif now - self.record_start > self.max_record_seconds:
                        self._finish_recording()
                    continue

                # 播报阶段：检测打断
                if mode == VoiceFrontend.STATE_SPEAKING:
                    # 播报刚开始的保护期：忽略麦克风，防止扬声器起始音误触发
                    if self.current_guard > 0:
                        self.current_guard -= 1
                        self.barge_run = 0
                        continue

                    # 计算这一帧的音量，只有“VAD 认为是语音 + 音量够大”才算打断
                    samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt((samples ** 2).mean())) if samples.size else 0.0

                    if is_speech and rms >= self.barge_rms_threshold:
                        self.barge_run += 1
                    else:
                        self.barge_run = 0

                    if self.barge_run >= self.barge_frames:
                        self.on_barge_in()
                        self._begin_recording(frame, speech_seen=True)
                    continue

                # 处理中：忽略音频
                if mode == VoiceFrontend.STATE_WAITING:
                    continue

                # 待机阶段：VAD 门控 + 唤醒词识别
                if is_speech:
                    hangover = self.hangover_frames
                    silence_frames = 0
                else:
                    silence_frames += 1
                    if hangover > 0:
                        hangover -= 1
                    else:
                        if silence_frames == self.silence_reset_frames:
                            self.recognizer.Reset()
                            self.greeting_announced = False
                        continue

                if self.recognizer.AcceptWaveform(frame):
                    text = json.loads(self.recognizer.Result()).get("text", "")
                    if self._check_wake(text):
                        self.on_wake()
                        self._begin_recording(frame, speech_seen=False,
                                              after_wake=True)
                else:
                    partial = json.loads(
                        self.recognizer.PartialResult()).get("partial", "")
                    if self._check_wake(partial):
                        self.on_wake()
                        self._begin_recording(frame, speech_seen=False,
                                              after_wake=True)

        except Exception as e:
            self.on_error(f"语音前端异常：{e}")
        finally:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None