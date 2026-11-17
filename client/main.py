#桌面客户端：文字问答 + 按键说话 + 本地播报
"""依赖：PySide6、sounddevice、numpy、requests、piper-tts。"""

import json
import sys
import threading
import time

import os
import tempfile
import wave
import winsound
import requests


from voice_frontend import VoiceFrontend
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QPushButton, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_HOST = os.getenv("AGENT_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.getenv("AGENT_BACKEND_PORT", "8765")

_PIPER_VOICE = None
PIPER_MODEL = os.path.join(
    BASE_DIR, "models", "piper", "zh_CN-huayan-medium.onnx"
)
PIPER_CONFIG = f"{PIPER_MODEL}.json"
TTS_WAV = os.path.join(tempfile.gettempdir(), "agent_tts.wav")

MODEL_DIR = os.path.join(BASE_DIR, "models", "vosk-model-small-cn-0.22")
WS_URL = f"ws://{BACKEND_HOST}:{BACKEND_PORT}/ws"
VOICE_API = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/voice/ask"
RECORD_RATE = 16000

def get_piper_voice():
    """Piper 模型只加载一次，后续复用"""
    global _PIPER_VOICE
    if _PIPER_VOICE is None:
        from piper.voice import PiperVoice
        _PIPER_VOICE = PiperVoice.load(PIPER_MODEL, config_path=PIPER_CONFIG)
    return _PIPER_VOICE

class VoiceSignals(QObject):
    """后台线程 -> 界面线程的安全信号"""
    result = Signal(dict)        # 语音接口返回
    error = Signal(str)          # 出错信息
    spoken = Signal()            # TTS 播报完成
    wake = Signal()              # 唤醒成功
    record_done = Signal(str)    # 录音完成，参数是 wav 路径
    barge_in = Signal()          # 播报中检测到打断
    voice_state = Signal(str)    # 语音前端状态变化


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("个人知识问答 Agent")
        self.resize(1100, 720)

        self.streaming = False       # 是否正在接收流式回答
        self.recording = False       # 是否正在“说话”
        self.assistant_started = False   # 本轮 Agent 回答是否已经输出了开头

        self.signals = VoiceSignals()
        self.signals.result.connect(self.on_voice_result)
        self.signals.error.connect(self.on_voice_error)
        self.signals.spoken.connect(self.on_spoken)
        # TTS 并发控制：每次播报分配一个唯一 token
        self.tts_lock = threading.Lock()
        self.tts_token = 0

        # 语音前端：常听唤醒 + 自动录音 + 播报中打断
        self.voice = VoiceFrontend(
            MODEL_DIR,
            on_wake=lambda: self.signals.wake.emit(),
            on_record_done=lambda path: self.signals.record_done.emit(path),
            on_barge_in=lambda: self.signals.barge_in.emit(),
            on_state=lambda state: self.signals.voice_state.emit(state),
            on_error=lambda message: self.signals.error.emit(message),
        )

        self.signals.wake.connect(self.on_wake)
        self.signals.record_done.connect(self.on_record_done)
        self.signals.barge_in.connect(self.on_barge_in)
        self.signals.voice_state.connect(self.on_voice_state)


        self._build_ui()

        # WebSocket 客户端：与本地服务通信
        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_connected)
        self.ws.disconnected.connect(self.on_disconnected)
        self.ws.textMessageReceived.connect(self.on_message)
        self.ws.errorOccurred.connect(self.on_ws_error)
        self.ws.open(QUrl(WS_URL))

        self.voice.start()

    # ---------- 界面搭建 ----------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        # 顶部状态栏：模式、麦克风、取消、状态文本
        top = QHBoxLayout()
        top.addWidget(QLabel("模式："))
        self.mode_box = QComboBox()
        self.mode_box.addItems(["本地隐私", "云端增强"])
        self.mode_box.currentIndexChanged.connect(self.on_mode_changed)
        top.addWidget(self.mode_box)

        self.mic_btn = QPushButton("按下说话")
        self.mic_btn.clicked.connect(self.toggle_mic)
        top.addWidget(self.mic_btn)

        self.cancel_btn = QPushButton("打断/停止")
        self.cancel_btn.clicked.connect(self.cancel_current)
        top.addWidget(self.cancel_btn)

                # 四个独立状态标签，互不覆盖
        self.conn_status = QLabel("服务：未连接")
        top.addWidget(self.conn_status)

        self.voice_status = QLabel("语音：IDLE")
        top.addWidget(self.voice_status)

        self.model_status = QLabel("模型：未加载")
        top.addWidget(self.model_status)

        self.tool_status = QLabel("工具：无")
        top.addWidget(self.tool_status, stretch=1)
        outer.addLayout(top)

        # 中间：左侧聊天，右侧引用来源
        splitter = QSplitter()
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        splitter.addWidget(self.chat)

        self.citations = QListWidget()
        splitter.addWidget(self.citations)
        splitter.setSizes([760, 320])
        outer.addWidget(splitter, stretch=1)

        # 底部输入栏
        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入问题后回车或点击发送……")
        self.input.returnPressed.connect(self.send_text)
        bottom.addWidget(self.input, stretch=1)
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self.send_text)
        bottom.addWidget(send_btn)
        outer.addLayout(bottom)

    # ---------- 事件发送 ----------
    def _send_event(self, event: str, **fields):
        """把事件打包成 JSON 发给本地服务"""
        payload = {"event": event}
        payload.update(fields)
        self.ws.sendTextMessage(json.dumps(payload, ensure_ascii=False))

    def _mode(self) -> str:
        return "local" if self.mode_box.currentIndex() == 0 else "cloud"
    def _session_id(self) -> str:
        """本地和云端使用不同会话，避免本地记忆泄露到云端会话"""
        return f"default-{self._mode()}"

    # ---------- 文字问答 ----------
    def send_text(self):
        text = self.input.text().strip()
        if not text:
            return
        self.chat.append(f"我：{text}")
        self.chat.append("")                 # 空行分隔
        self.assistant_started = False        # 新一轮回答还没开始
        self.input.clear()
        self._send_event("user_text", text=text, mode=self._mode(),
                         session_id=self._session_id(),
                         user_id="default")  # 暂时固定用户 ID


    def toggle_mic(self):
            """手动触发一次录音（唤醒词之外的后备方式）"""
            self.voice.trigger_manual()
            self.voice_status.setText("语音：手动录音中")


    def _upload_voice(self, wav_path: str, mode: str):
        """后台线程：把 wav 发给本地服务"""
        try:
            with open(wav_path, "rb") as f:
                resp = requests.post(
                    VOICE_API,
                    files={"file": ("voice.wav", f, "audio/wav")},
                    data={"mode": mode, "session_id": f"default-{mode}", "user_id": "default"},
                    timeout=300,
                )
            self.signals.result.emit(resp.json())
        except Exception as e:
            self.signals.error.emit(str(e))


    def on_wake(self):
        self.voice_status.setText("语音：已唤醒，录音中")

    def on_voice_state(self, state: str):
        self.voice_status.setText(f"语音：{state}")

    def on_record_done(self, wav_path: str):
        """录音结束：上传给后端做识别和问答"""
        self.voice_status.setText("语音：识别中")
        threading.Thread(
            target=self._upload_voice,
            args=(wav_path, self._mode()),
            daemon=True,
        ).start()

    def on_barge_in(self):
        """播报中检测到用户说话：停止播报，前端已开始重新录音"""
        self.stop_tts()
        self.voice_status.setText("语音：已打断，重新录音")


    def on_voice_result(self, data: dict):
        """收到语音接口结果：显示文字、引用，并本地播报"""
        if data.get("error"):
            self.on_voice_error(data["error"])
            return

        transcript = data.get("transcript", "")
        answer = data.get("answer", "")

        self.chat.append(f"我（语音）：{transcript}")
        self.chat.append("")
        self.chat.append("Agent：")
        self.chat.append(answer)

        for item in data.get("citations", []):
            text = (f"{item.get('file_name')} | 部门：{item.get('department')} "
                    f"| 第{item.get('page')}页 | 相关度：{item.get('score')}\n"
                    f"{item.get('snippet')}")
            self.citations.addItem(QListWidgetItem(text))


        self.voice_status.setText("语音：播报中")
        self.speak_text(answer)


    def on_voice_error(self, message: str):
        self.chat.append(f"语音处理失败：{message}")
        self.voice_status.setText("语音：IDLE")
        self.voice.set_idle()


    def on_spoken(self):
        self.voice_status.setText("语音：IDLE")
        self.voice.set_idle()              # 回到唤醒待机

    def speak_text(self, text: str):
        """Piper 合成 + 异步播放；每次播报有唯一 token，可被安全打断"""
        with self.tts_lock:
            self.tts_token += 1
            token = self.tts_token

        def run():
            try:
                # 1. 合成语音
                t0 = time.time()
                self._piper_synthesize(text, TTS_WAV)
                print(f"[计时] Piper 合成：{time.time() - t0:.2f}s")

                # 2. 合成期间如果被新播报取代，直接退出
                with self.tts_lock:
                    if token != self.tts_token:
                        return

                # 3. 异步播放，边播边检查是否被打断
                duration = self._wav_duration(TTS_WAV)

                # 关键：合成完成、真正要播放时才进入播报状态
                self.voice.set_speaking()

                winsound.PlaySound(
                    TTS_WAV,
                    winsound.SND_FILENAME | winsound.SND_ASYNC,
                )

                end_time = time.time() + duration
                while time.time() < end_time:
                    with self.tts_lock:
                        if token != self.tts_token:
                            break
                    time.sleep(0.05)
            except Exception as e:
                self.signals.error.emit(f"TTS 失败：{e}")
            finally:
                winsound.PlaySound(None, winsound.SND_PURGE)
                self.signals.spoken.emit()

        threading.Thread(target=run, daemon=True).start()
    def _wav_duration(self, path: str) -> float:
        with wave.open(path, "rb") as f:
            return f.getnframes() / float(f.getframerate())

    def stop_tts(self):
        """打断播报：token 自增让旧线程失效，并停止 winsound"""
        with self.tts_lock:
            self.tts_token += 1
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def _piper_synthesize(self, text: str, out_path: str):
        """适配不同 piper-tts 版本的合成函数"""
        import wave

        voice = get_piper_voice()

        with wave.open(out_path, "wb") as wav_file:
            # 先写 WAV 头，避免 channels not specified
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(voice.config.sample_rate)

            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(text, wav_file)
            elif hasattr(voice, "synthesize_stream_raw"):
                for chunk in voice.synthesize_stream_raw(text):
                    wav_file.writeframes(chunk)
            else:
                voice.synthesize(text, wav_file)

        if os.path.getsize(out_path) < 1000:
            raise RuntimeError("Piper 没有生成有效音频")


    def cancel_current(self):
        self._send_event("cancel")
        self.stop_tts()
        self.voice.set_idle()
        self.voice_status.setText("语音：IDLE")

    def on_mode_changed(self):
        self._send_event("mode_switch", mode=self._mode())
        if self.mode_box.currentIndex() == 1:
            self.chat.append("提示：云端模式只做通用问答，不查询本地知识库。")


    # ---------- WebSocket 回调 ----------
    def on_connected(self):
        self.conn_status.setText("已连接本地服务")

    def on_disconnected(self):
        self.conn_status.setText("连接已断开")

    def on_ws_error(self, error):
        self.conn_status.setText(f"连接错误：{error}")

    def on_message(self, raw: str):
        """处理服务端事件"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        event = data.get("event")

        if event == "assistant_delta":
            # 本轮第一次收到片段时，先输出“Agent：”并换行
            if not self.assistant_started:
                self.chat.append("Agent：")
                self.assistant_started = True
            # 流式追加：移动光标到末尾再插入文本
            self.chat.moveCursor(QTextCursor.End)
            self.chat.insertPlainText(data.get("text", ""))
            self.streaming = True

        elif event == "assistant_done":
            self.chat.append("")          # 换行，结束本轮
            self.streaming = False
            self.assistant_started = False  # 重置回答状态

        elif event == "citation":
            for item in data.get("items", []):
                text = (f"{item.get('file_name')} | 部门：{item.get('department', '未知')} "
                        f"| 第{item.get('page')}页 | 相关度：{item.get('score')}\n"
                        f"{item.get('snippet')}")
                self.citations.addItem(QListWidgetItem(text))

        elif event == "voice_state":
            self.voice_status.setText(f"语音状态：{data.get('state')}")

        elif event == "model_status":
            self.model_status.setText(
                f"模型：{data.get('model')} {data.get('state')} "
                f"显存：{data.get('vram_gb')}GB")

        elif event == "tool_status":
            self.tool_status.setText(
                f"工具：{data.get('tool')} {data.get('state')}")

        elif event == "error":
            self.chat.append(f"错误：{data.get('message')}")

    def closeEvent(self, event):
        """关闭窗口时释放资源"""
        try:
            self.ws.close()
        except Exception:
            pass
        self.stop_tts()
        try:
            self.voice.stop()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
