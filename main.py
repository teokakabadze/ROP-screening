import sys
import os
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

def main():
    # 1. Create the Application instance
    app = QGuiApplication(sys.argv)

    # 2. Create the QML Engine (the thing that reads your .qml files)
    engine = QQmlApplicationEngine()

    # 3. Get the path to your main.qml file
    # This logic finds 'ui/main.qml' relative to where this script is saved
    qml_file = Path(__file__).parent / "ui" / "main.qml"

    # 4. Load the file into the engine
    engine.load(os.fspath(qml_file))

    # 5. Safety Check: If the engine failed to load (typo in QML), close the app
    if not engine.rootObjects():
        print("Error: QML file failed to load! Check your QML code for typos.")
        sys.exit(-1)

    # 6. Start the app and keep it running until the window is closed
    print("ROP App Started successfully...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()