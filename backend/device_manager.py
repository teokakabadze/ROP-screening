"""
device_manager.py
Manages the USB CDC ACM serial connection to the Retinex Pi device.

Protocol (text lines, newline-terminated):
  Windows -> Pi:  CMD:CAPTURE
                  CMD:BRIGHTNESS:<0-100>
  Pi -> Windows:  EVT:CAPTURED:/path/to/image.jpg
                  EVT:BRIGHTNESS:<0-100>
                  EVT:BTN_PRESSED
                  EVT:STATUS:ready
"""

import threading
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo


# USB identifiers of the Retinex gadget (set in setup_usb_gadget.sh)
_GADGET_VID = 0x1D6B  # Linux Foundation
_GADGET_PID = 0x0104  # Composite Gadget


class DeviceManager(QObject):
    """
    Exposes Retinex Pi device controls to QML.

    Signals:
        deviceConnected(bool)   - true when serial port opened
        captureConfirmed(str)   - path on Pi where image was saved
        brightnessChanged(int)  - Pi confirmed brightness change (0-100)
        buttonPressed()         - physical button on Pi was pressed
        statusReceived(str)     - generic status string from Pi

    Slots (callable from QML):
        triggerCapture()
        setBrightness(int)
        reconnect()
    """

    deviceConnected  = Signal(bool)
    captureConfirmed = Signal(str)
    brightnessChanged = Signal(int)
    buttonPressed    = Signal()
    statusReceived   = Signal(str)
    captureModeChanged = Signal(str)
    _portFound       = Signal(str)   # internal: port name found in background thread

    def __init__(self, parent=None, mode="48mp"):
        super().__init__(parent)
        self._mode   = mode          # "16mp" or "48mp"; sent to Pi on every connect
        self._port   = QSerialPort(self)
        self._buffer = ""

        self._port.readyRead.connect(self._on_data)
        self._port.errorOccurred.connect(self._on_error)

        # Reconnect timer – polls every 3 s until device appears
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(3000)
        self._reconnect_timer.timeout.connect(self._try_connect)
        self._reconnect_timer.start()

        # _portFound routes the background scan result back to the main thread for safe port open
        self._portFound.connect(self._open_port)

        QTimer.singleShot(200, self._try_connect)

    # ── Connection ────────────────────────────────────────────────

    def _try_connect(self):
        if self._port.isOpen():
            return
        # Run port scan in a background thread — QSerialPortInfo.availablePorts()
        # blocks the main thread on Windows when USB CDC ACM devices are present
        threading.Thread(target=self._scan_ports, daemon=True).start()

    def _scan_ports(self):
        ports = QSerialPortInfo.availablePorts()
        for info in ports:
            if (info.vendorIdentifier()  == _GADGET_VID and
                    info.productIdentifier() == _GADGET_PID):
                self._portFound.emit(info.portName())
                return

    def _open_port(self, port_name: str):
        if self._port.isOpen():
            return
        self._port.setPortName(port_name)
        self._port.setBaudRate(QSerialPort.Baud115200)
        self._port.setDataBits(QSerialPort.Data8)
        self._port.setParity(QSerialPort.NoParity)
        self._port.setStopBits(QSerialPort.OneStop)
        if self._port.open(QSerialPort.ReadWrite):
            print(f"[DeviceManager] opened {port_name}")
            self._reconnect_timer.stop()
            self.deviceConnected.emit(True)
            self._write(f"CMD:MODE:{self._mode.upper()}")
        else:
            print(f"[DeviceManager] failed to open {port_name}: {self._port.errorString()}")

    @Slot()
    def reconnect(self):
        if self._port.isOpen():
            self._port.close()
            self.deviceConnected.emit(False)
        self._buffer = ""
        self._reconnect_timer.start()
        self._try_connect()

    def _on_error(self, error):
        if error != QSerialPort.NoError:
            self._port.close()
            self.deviceConnected.emit(False)
            self._buffer = ""
            self._reconnect_timer.start()

    # ── Outgoing commands ─────────────────────────────────────────

    @Slot()
    def triggerCapture(self):
        self._write("CMD:CAPTURE")

    @Slot(int)
    def setBrightness(self, value: int):
        self._write(f"CMD:BRIGHTNESS:{max(0, min(100, value))}")

    @Slot(str)
    def setMode(self, mode: str):
        """Switch capture resolution: '16mp' or '48mp'."""
        mode = mode.lower()
        if mode not in ("16mp", "48mp"):
            return
        self._mode = mode
        self._write(f"CMD:MODE:{mode.upper()}")
        self.captureModeChanged.emit(self._mode)

    @Property(str, notify=captureModeChanged)
    def captureMode(self):
        return self._mode

    def _write(self, cmd: str):
        if self._port.isOpen():
            print(f"[DeviceManager] sending: {cmd!r}")
            self._port.write((cmd + "\n").encode())
        else:
            print(f"[DeviceManager] port not open, dropping: {cmd!r}")

    # ── Incoming events ───────────────────────────────────────────

    def _on_data(self):
        self._buffer += self._port.readAll().data().decode(errors="replace")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._parse(line.strip())

    def _parse(self, line: str):
        if not line.startswith("EVT:"):
            return
        body = line[4:]

        if body.startswith("CAPTURED:"):
            self.captureConfirmed.emit(body[9:])

        elif body.startswith("BRIGHTNESS:"):
            try:
                self.brightnessChanged.emit(int(body[11:]))
            except ValueError:
                pass

        elif body == "BTN_PRESSED":
            self.buttonPressed.emit()

        elif body.startswith("STATUS:"):
            self.statusReceived.emit(body[7:])
