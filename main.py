import sys
import os
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Slot, Signal
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QImageCapture
from PySide6.QtCore import QDateTime, QUrl


class CameraManager(QObject):
    imageSaved = Signal(str)
    
    def __init__(self, capture_session, image_capture):
        super().__init__()
        self._session = capture_session
        self._image_capture = image_capture
        
        self._image_capture.imageSaved.connect(self._on_image_saved)
        
    def _on_image_saved(self, id, path):
        url = QUrl.fromLocalFile(path).toString()
        print(f"Signal emitting: {url}")
        self.imageSaved.emit(url)
        
    @Slot()
    def capture(self):
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        filename = f"ROP_Capture_{timestamp}.jgp"
        
        save_path = os.path.join(os.getcwd(), "captures", filename)
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        self._image_capture.captureToFile(save_path)
        print(f"Saving to: {save_path}")
        

def main():
    app = QGuiApplication(sys.argv)
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    engine = QQmlApplicationEngine()

    qml_file = Path(__file__).parent / "ui" / "main.qml"
    engine.load(os.fspath(qml_file))

    if not engine.rootObjects():
        print("QML file failed to load.")
        sys.exit(-1)
    
    # find the default camera
    camera = QCamera(QMediaDevices.defaultVideoInput())
    capture_session = QMediaCaptureSession()
    capture_session.setCamera(camera)
    
    image_capture = QImageCapture()
    capture_session.setImageCapture(image_capture)
    
    camera_manager = CameraManager(capture_session, image_capture)
    engine.rootContext().setContextProperty("cameraManager", camera_manager)
    
    root = engine.rootObjects()[0]
    video_output = root.findChild(QObject, "cameraFeed")
    
    capture_session.setVideoOutput(video_output)
    camera.start()
        
    print("ROP App Started successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()