import sys
import os
import time
import threading
os.environ["QT_MEDIA_BACKEND"] = "windows"  # must be set before any Qt imports
sys.stdout.reconfigure(line_buffering=True)
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Slot, Signal, QSize
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QImageCapture, QVideoFrameFormat
from PySide6.QtCore import QUrl

from backend.device_manager import DeviceManager

PI_HOST = "192.168.137.248"
PI_USER = "retinex"
PI_PASS = "retinopathy"


class CameraManager(QObject):
    imageSaved = Signal(str)

    def __init__(self, capture_session, image_capture):
        super().__init__()
        self._session = capture_session
        self._image_capture = image_capture

    @Slot(str)
    def download_capture(self, pi_path: str):
        """Receive Pi-side path from captureConfirmed, fetch via SFTP, emit imageSaved."""
        threading.Thread(target=self._sftp_download, args=(pi_path,), daemon=True).start()

    def _sftp_download(self, pi_path: str):
        try:
            import paramiko
            filename = f"ROP_Capture_{time.strftime("%Y%m%d_%H%M%S")}.jpg"
            local_path = os.path.join(os.getcwd(), "captures", filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=15)
            sftp = ssh.open_sftp()
            sftp.get(pi_path, local_path)
            sftp.close()
            ssh.close()

            url = QUrl.fromLocalFile(local_path).toString()
            print(f"Downloaded capture: {local_path}")
            self.imageSaved.emit(url)
        except Exception as e:
            print(f"SFTP download failed: {e}")


def _find_retinex_camera():
    cameras = QMediaDevices.videoInputs()
    for info in cameras:
        if "Retinex" in info.description() or "ROP" in info.description():
            return info
    integrated = ("integrated", "internal", "built-in", "facetime", "ir camera")
    for info in cameras:
        if not any(k in info.description().lower() for k in integrated):
            return info
    return QMediaDevices.defaultVideoInput()


def main():
    app = QGuiApplication(sys.argv)
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    engine = QQmlApplicationEngine()

    device_manager = DeviceManager()
    engine.rootContext().setContextProperty("deviceManager", device_manager)

    cam_info = _find_retinex_camera()
    print(f"Using camera: {cam_info.description()}")
    camera = QCamera(cam_info)
    formats = cam_info.videoFormats()
    print(f"Camera formats ({len(formats)}):")
    for fmt in formats:
        print(f"  {fmt.resolution().width()}x{fmt.resolution().height()} "
              f"{fmt.maxFrameRate():.1f}fps {fmt.pixelFormat()}")
    best = None
    for fmt in formats:
        r = fmt.resolution()
        if r.width() == 1920 and r.height() == 1080 and fmt.maxFrameRate() >= 14.0:
            best = fmt
            break
    if best is None and formats:
        # Fallback: pick highest-resolution format
        best = max(formats, key=lambda f: f.resolution().width() * f.resolution().height())
    if best:
        camera.setCameraFormat(best)
        r = best.resolution()
        print(f"Set camera format: {r.width()}x{r.height()} {best.maxFrameRate():.0f}fps")
    capture_session = QMediaCaptureSession()
    capture_session.setCamera(camera)
    image_capture = QImageCapture()
    capture_session.setImageCapture(image_capture)
    camera_manager = CameraManager(capture_session, image_capture)
    engine.rootContext().setContextProperty("cameraManager", camera_manager)
    qml_file = Path(__file__).parent / "ui" / "main.qml"
    engine.load(os.fspath(qml_file))

    if not engine.rootObjects():
        print("QML file failed to load.")
        sys.exit(-1)

    device_manager.buttonPressed.connect(device_manager.triggerCapture)
    device_manager.captureConfirmed.connect(camera_manager.download_capture)

    root = engine.rootObjects()[0]
    video_output = root.findChild(QObject, "cameraFeed")

    capture_session.setVideoOutput(video_output)
    camera.start()

    print("ROP App Started successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
