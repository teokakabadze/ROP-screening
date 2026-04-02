# Retinex Pi Zero 2W — Reflash & Restore Plan

Target OS: **Raspberry Pi OS Lite 32-bit** (Trixie / Debian 13 — PiOS now ships trixie by default; Bookworm is no longer the latest)
Hardware: Pi Zero 2W + Arducam OV64A40 64MP sensor (CSI-2)

---

## 1. Flash & First Boot

1. Flash PiOS Lite 32-bit with Raspberry Pi Imager
2. In Imager advanced settings:
   - Hostname: `retinex`
   - Username: `retinex`, Password: `retinopathy`
   - Enable SSH
   - WiFi: configure if needed (or use USB-shared network)
3. Boot Pi, find IP (USB-shared network will be `192.168.137.x`)

---

## 2. /boot/firmware/config.txt

Replace the `[all]` and add Pi Zero 2W section. Full relevant config:

```ini
# At top level / [all] section
camera_auto_detect=0
dtoverlay=vc4-kms-v3d,cma-320
arm_boost=1
enable_uart=1

[pi02]
dtoverlay=dwc2,dr_mode=host
dtoverlay=dwc2,dr_mode=peripheral
dtoverlay=ov64a40,link-frequency=360000000
gpu_mem=32
```

> **Critical notes:**
> - `link-frequency=360000000` — NOT 456000000 (causes Unicam timeout + corrupted image)
> - `gpu_mem=32` — minimum for camera firmware detection; don't go lower
> - `cma-320` — maximum stable CMA on Zero 2W; cma-400 falls back to 256MB due to physical RAM layout
> - Both `dwc2` overlays required for composite USB gadget (UVC + CDC ACM)
> - On 32-bit OS: remove `arm_64bit=1` (default is 0)

> **⏸ STOP — Reboot required.**
> Config.txt changes only take effect after reboot:
> ```bash
> sudo reboot
> ```
> Wait for Pi to come back up (SSH reconnect), then continue.

---

## 3. Install System Packages

> **⏸ STOP — Run this command separately and tell me when it finishes.**
> This can take 5–10 minutes. Do not continue to the next section until it completes.

```bash
sudo apt update && sudo apt install -y \
    python3-picamera2 \
    python3-opencv \
    python3-serial \
    python3-gpiozero \
    python3-pip \
    libcamera-tools \
    v4l-utils \
    netcat-openbsd
```

> If `python3-opencv` fails or gives import errors after install, fall back to:
> ```bash
> pip install opencv-python --break-system-packages
> ```

---

## 4. Deploy Pi Source Files

Copy from `H:\Projects\Retinex\pi_src\` to Pi:

| Local file | Pi destination |
|---|---|
| `pi_src/retinex_stream.py` | `/usr/local/bin/retinex_stream.py` |
| `pi_src/retinex_control.py` | `/usr/local/bin/retinex_control.py` |
| `pi_src/setup_usb_gadget.sh` | `/usr/local/bin/setup_usb_gadget.sh` |

> **Do NOT deploy `retinex_capture.py`** — capture is handled inside `retinex_stream.py`.
> There is no `retinex-capture.service` and none should be created.

```bash
chmod +x /usr/local/bin/setup_usb_gadget.sh
chmod +x /usr/local/bin/retinex_stream.py
chmod +x /usr/local/bin/retinex_control.py
mkdir -p /home/retinex/captures
```

> **Note:** `python3-v4l2` is not available on Bookworm/trixie. This is expected — `setup_usb_gadget.sh` uses raw configfs shell commands directly, which is correct and does not need the v4l2 Python library.

> **Note on retinex_stream.py architecture:**
> - Handles UVC events directly on `/dev/video1`
> - Pre-inits camera at service start (avoids 13s blank-frame timeout on first STREAMON)
> - Keeps camera alive across STREAMON/STREAMOFF cycles
> - Only releases camera for still capture, then restarts it
> - Handles CAPTURE + BRIGHTNESS commands via Unix socket `/tmp/retinex_ctrl.sock`
> - UVC MJPEG frame index: format=1, 480p=1, 720p=2, 1080p=3 (hardcoded in `_make_probe`)

---

## 5. Create systemd Services

### 5a. retinex-gadget.service
```bash
sudo tee /etc/systemd/system/retinex-gadget.service << 'EOF'
[Unit]
Description=Retinex USB Gadget Setup
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/setup_usb_gadget.sh

[Install]
WantedBy=multi-user.target
EOF
```

### 5b. retinex-stream.service
```bash
sudo tee /etc/systemd/system/retinex-stream.service << 'EOF'
[Unit]
Description=Retinex UVC Stream Daemon
After=retinex-gadget.service
Requires=retinex-gadget.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/retinex_stream.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 5c. retinex-control.service
```bash
sudo tee /etc/systemd/system/retinex-control.service << 'EOF'
[Unit]
Description=Retinex CDC ACM Control Daemon
After=retinex-gadget.service retinex-stream.service
Requires=retinex-gadget.service retinex-stream.service

[Service]
Type=simple
User=retinex
ExecStart=/usr/bin/python3 /usr/local/bin/retinex_control.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

> `Restart=always` on retinex-control — must restart on clean exit (USB HUP causes clean exit)

### 5d. Enable & Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable retinex-gadget retinex-stream retinex-control
sudo systemctl start retinex-gadget
```

> **⏸ STOP — Run the above three commands, then tell me when done** before starting the stream service.

```bash
sudo systemctl start retinex-stream
```

> **⏸ STOP — Camera takes ~15 seconds to initialize.** Run this and watch the log:
> ```bash
> journalctl -u retinex-stream -f
> ```
> Wait until you see `Camera started at 1920x1080` followed by `Camera stopped` / `Camera closed successfully.`
> **This is normal** — the stream daemon pre-inits the camera then idles it, waiting for UVC STREAMON.
> Press Ctrl+C and continue once you see those lines (no more errors scrolling).

```bash
sudo systemctl start retinex-control
```

---

## 6. Verify UVC Device Node

**Critical on 32-bit** — the UVC gadget device node number may differ:

> **⏸ STOP — Run this and paste me the output before continuing:**
```bash
v4l2-ctl --list-devices
```
> Look for the entry under `3f980000.usb (gadget.0)` — that is the UVC gadget device.
> On both 64-bit and 32-bit (trixie) it has been `/dev/video1` (unicam takes `/dev/video0`).
> Verify anyway in case a kernel update changes the assignment.

If the node is different from `/dev/video1`, update `UVC_DEVICE` in `/usr/local/bin/retinex_stream.py` before starting the service.

## 7. Verify Services & Pipeline

> **⏸ STOP — Run each block separately and paste results before continuing.**

```bash
# All three should print "active"
systemctl is-active retinex-gadget retinex-stream retinex-control

# CMA: should be 327680 kB (320MB)
grep CmaTotal /proc/meminfo
```

```bash
# Test capture via socket — may take a few seconds to respond
echo CAPTURE | nc -U /tmp/retinex_ctrl.sock
# Expected: CAPTURED:/home/retinex/captures/ROP_YYYYMMDD_HHMMSS.jpg
# If it hangs, camera may not be ready — check: journalctl -u retinex-stream --no-pager | tail -20
```

```bash
# Verify 3472x3472
python3 -c "
import glob
from PIL import Image
f = sorted(glob.glob('/home/retinex/captures/ROP_*.jpg'))[-1]
img = Image.open(f)
print(img.size)
"
```

### Windows Camera Name
- After plugging in USB, Windows should show **"Retinex Camera"** (set via `function_name` in gadget script)
- If it shows **"UVC Camera"** (cached old name): Device Manager → Cameras → right-click → Uninstall device → replug
- The QML app's `_find_retinex_camera()` also matches "ROP" and falls back to any non-integrated camera

---

## 8. Windows App (no changes needed)

`H:\Projects\Retinex\main.py` is already configured:
- `PI_HOST = "192.168.137.248"` — update if IP changes
- Scans for COM port VID=0x1D6B PID=0x0104
- On `captureConfirmed`: SFTP downloads from Pi to `captures/` folder
- Gallery in sidebar shows thumbnails via `cameraManager.imageSaved` signal

Run: `python main.py`

---

## 9. Key Architecture Notes

### Why Python stream (not C uvc-gadget)?
The C `uvc-gadget` binary exits on `systemctl stop`, causing the entire USB composite device to re-enumerate. This drops the CDC ACM serial (COM port) and loses the `EVT:CAPTURED` response. The Python daemon keeps the UVC fd open throughout, so USB stays connected during capture.

### Why 3472×3472 max?
- Any output height > 3472px triggers the 8000×6000 sensor mode
- That mode requires 4 × 57MB = 228MB Unicam DMA buffers
- Only ~224MB CMA is free at capture time → OOM
- 3472×3472 uses 4624×3472 sensor mode (4 × 23.7MB Unicam) → fits in 320MB CMA

### Control protocol
```
Windows → Pi (CMD):   CMD:CAPTURE  |  CMD:BRIGHTNESS:0-100
Pi → Windows (EVT):   EVT:CAPTURED:/path  |  EVT:BRIGHTNESS:N  |  EVT:BTN_PRESSED  |  EVT:STATUS:ready
```

### 32-bit specific
- Remove `arm_64bit=1` from config.txt (or set to 0)
- Verify `python3-opencv` installs correctly (may need `pip install opencv-python` if apt version is broken)
- UVC device node: **verify with `v4l2-ctl --list-devices`** — was `/dev/video1` on 64-bit; update `UVC_DEVICE` in retinex_stream.py if different
- `retinex_stream.py` uses BGR888 picamera2 format (cv2 expects BGR natively)

### Linux 6.12 UVC configfs
- Frame intervals use `dwFrameInterval` attribute (discrete list), NOT separate min/max attributes
- `streaming_maxpacket=2048` (set in gadget script)
- YUYV format omitted from descriptor intentionally — forces Windows to negotiate MJPEG only, avoids stride/format artifacts

### UVC camera fps expectations
- DirectShow (OpenCV `VideoCapture`) shows ~0.7fps for MJPEG — this is a codec limitation, **not real throughput**
- Qt Media Foundation (what the QML app uses) handles MJPEG natively — actual streaming fps is normal
- Python stream in retinex_stream.py does software JPEG encoding via cv2 on the Pi Zero 2W CPU
