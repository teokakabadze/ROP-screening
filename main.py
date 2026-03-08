import sys
import os
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices

def main():
    app = QGuiApplication(sys.argv)
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
    
    root = engine.rootObjects()[0]
    video_output = root.findChild(QObject, "cameraFeed")
    
    capture_session.setVideoOutput(video_output)
    camera.start()
        
    print("ROP App Started successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()