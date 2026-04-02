import sys
import os
import time
import socket
import threading
import base64
import urllib.request
import subprocess
sys.stdout.reconfigure(line_buffering=True)
from pathlib import Path
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Slot, Signal, Property, QUrl, QSize
from PySide6.QtQuick import QQuickImageProvider

from backend.device_manager import DeviceManager

PI_HTTP      = "http://192.168.7.1:8080"
CAPTURE_PORT = 9999
CAPTURE_W    = 6944
CAPTURE_H    = 6944


# ── MJPEG image provider + stream reader ─────────────────────────────────────

class MjpegImageProvider(QQuickImageProvider):
    """Stores the latest JPEG frame; QML pulls it synchronously — no blank flash."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._image = QImage(1280, 720, QImage.Format.Format_RGB888)
        self._image.fill(0)
        self._lock = threading.Lock()

    def update(self, jpeg_bytes: bytes):
        img = QImage()
        img.loadFromData(jpeg_bytes, "JPEG")
        if not img.isNull():
            with self._lock:
                self._image = img

    def requestImage(self, id: str, size: QSize, requested: QSize):
        with self._lock:
            return self._image.copy()


class MjpegStream(QObject):
    """Reads MJPEG stream from camera_daemon; increments frameCount so QML refreshes."""

    frameChanged = Signal()

    def __init__(self, provider: MjpegImageProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._count = 0

    @Property(int, notify=frameChanged)
    def frameCount(self):
        return self._count

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                self._read_stream()
            except Exception as e:
                print(f"Stream error: {e} — retrying in 2s", flush=True)
                time.sleep(2)

    def _read_stream(self):
        response = urllib.request.urlopen(f"{PI_HTTP}/stream.mjpg", timeout=10)
        buf = b""
        MAX_BUF = 1_000_000
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            buf += chunk
            if len(buf) > MAX_BUF:
                buf = buf[-MAX_BUF:]
            while True:
                start = buf.find(b'\xff\xd8')
                if start == -1:
                    break
                end = buf.find(b'\xff\xd9', start + 2)
                if end == -1:
                    break
                jpeg = buf[start:end + 2]
                buf = buf[end + 2:]
                self._provider.update(jpeg)
                self._count += 1
                self.frameChanged.emit()


# ── receive_image.py subprocess ───────────────────────────────────────────────

class ReceiveImageProcess:
    """
    Runs receive_image.py --loop as a persistent subprocess.
    The TCP listener is always ready — no race with the HTTP trigger.
    Stdout is forwarded to main.py's console; saved-file paths are parsed
    and forwarded to CameraManager.imageSaved.
    """

    def __init__(self, camera_manager: "CameraManager"):
        self._cm = camera_manager
        self._proc = None

    def start(self):
        captures_dir = Path(__file__).parent / "captures"
        captures_dir.mkdir(exist_ok=True)
        script = captures_dir / "receive_image.py"
        out_template = captures_dir / "ROP_Capture.jpg"
        self._proc = subprocess.Popen(
            [
                sys.executable, str(script),
                "--loop", "--timestamp",
                "--port",   str(CAPTURE_PORT),
                "--width",  str(CAPTURE_W),
                "--height", str(CAPTURE_H),
                "--out",    str(out_template),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        threading.Thread(target=self._read_output, daemon=True).start()
        print(f"[receive_image] started (PID {self._proc.pid})", flush=True)

    def _read_output(self):
        last_was_progress = False
        for line in self._proc.stdout:
            line = line.rstrip()
            if line.lstrip().startswith("[recv]"):
                print(f"\r[receive_image] {line:<90}", end="", flush=True)
                last_was_progress = True
            else:
                if last_was_progress:
                    print()  # move past the progress line
                    last_was_progress = False
                print(f"[receive_image] {line}", flush=True)
                if line.startswith("[+] Saved:"):
                    path_part = line[10:].strip().split("  ")[0].strip()
                    elapsed = time.perf_counter() - self._cm._capture_start
                    print(f"[receive_image] Total time (button → saved): {elapsed:.1f}s", flush=True)
                    url = QUrl.fromLocalFile(path_part).toString()
                    self._cm.imageSaved.emit(url)
        if last_was_progress:
            print()
        print("[receive_image] process exited", flush=True)


# ── Capture manager ───────────────────────────────────────────────────────────

class CameraManager(QObject):
    imageSaved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capture_start: float = 0.0

    @Slot()
    def triggerCapture(self):
        self._capture_start = time.perf_counter()
        print("triggerCapture called", flush=True)
        threading.Thread(target=self._trigger_http, daemon=True).start()

    def _trigger_http(self):
        try:
            urllib.request.urlopen(f"{PI_HTTP}/capture", timeout=10)
            print("Capture: HTTP trigger sent", flush=True)
        except Exception as e:
            print(f"Capture: HTTP trigger failed: {e}", flush=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QGuiApplication(sys.argv)
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    engine = QQmlApplicationEngine()

    device_manager = DeviceManager()
    engine.rootContext().setContextProperty("deviceManager", device_manager)

    mjpeg_provider = MjpegImageProvider()
    engine.addImageProvider("stream", mjpeg_provider)

    mjpeg_stream = MjpegStream(mjpeg_provider)
    engine.rootContext().setContextProperty("mjpegStream", mjpeg_stream)

    camera_manager = CameraManager()
    engine.rootContext().setContextProperty("cameraManager", camera_manager)

    receive_proc = ReceiveImageProcess(camera_manager)

    qml_file = Path(__file__).parent / "ui" / "main.qml"
    engine.load(os.fspath(qml_file))

    if not engine.rootObjects():
        print("QML file failed to load.")
        sys.exit(-1)

    device_manager.buttonPressed.connect(camera_manager.triggerCapture)

    mjpeg_stream.start()
    receive_proc.start()

    print("ROP App started.", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
