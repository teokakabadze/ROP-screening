# Retinex Pi Zero 2W — Reflash & Restore Plan (Option 1)

**Target OS:** Raspberry Pi OS Lite **64-bit** (Trixie / Debian 13)
**Hardware:** Pi Zero 2W + Arducam OV64A40 64MP (CSI-2)
**Architecture:** CDC ACM serial + USB NCM networking. No UVC gadget.

---

## Why 64-bit? (CMA)

> **Short answer:** 64-bit allows the full 9248×6944 raw capture. 32-bit does not.

| | 32-bit PiOS | 64-bit PiOS |
|---|---|---|
| Physical CMA available | 320 MB (`cma=320M`) | 320 MB (same hardware limit) |
| Contiguous DMA limit | ~32–64 MB per allocation (kernel VA fragmentation) | No limit — 200+ MB allocations succeed |
| Max stable capture res | 3472×3472 (uses 4624×3472 sensor mode) | 9248×6944 (full sensor, 80 MB raw buffer) |
| Kernel overhead vs 32-bit | baseline | +15–25 MB |
| Net usable CMA at capture | ~224 MB | ~220 MB (slightly less, but allocation succeeds) |

The 32-bit contiguous DMA limit is a **kernel virtual address space** problem, not a physical RAM problem.
64-bit removes it. The 320 MB hardware cap applies equally to both — don't try `cma=400M`.

---

## New Architecture (vs old)

| Concern | Old (32-bit) | New (64-bit, Option 1) |
|---|---|---|
| Preview | UVC gadget → Windows Camera | MJPEG HTTP on port 8080 over USB NCM |
| Serial control | CDC ACM + `retinex_control.py` | CDC ACM (same protocol) inside `camera_daemon.py` |
| Capture | kill uvc-gadget → rpicam-still → nc → restart uvc | stop encoder → picamera2 still → TCP push to Windows |
| Windows USB drop | Yes (UDC rebind) | **No** — USB NCM stays up throughout |
| Preview gap on capture | 4–12 s | ~3–5 s (encoder pause only, frozen frame) |
| Max capture resolution | 3472×3472 | **9248×6944** (full 64 MP), sent as 6944×6944 square |
| Pi-side files | retinex_stream.py + retinex_control.py | **camera_daemon.py** (single file) |
| Gadget setup | setup_usb_gadget.sh (UVC+ACM) | setup_usb_gadget_ncm.sh (NCM+ACM) |

---

## Files Changed / Created

### Pi-side (deploy from `pi_src/`)

| Local file | Pi destination | Notes |
|---|---|---|
| `pi_src/camera_daemon.py` | `/usr/local/bin/camera_daemon.py` | NEW — replaces stream + control |
| `pi_src/setup_usb_gadget_ncm.sh` | `/usr/local/bin/setup_usb_gadget.sh` | Replaces old gadget script |

> Old files on Pi (`retinex_stream.py`, `retinex_control.py`, old `setup_usb_gadget.sh`) are superseded.
> Remove them after verifying new setup works.

### Windows-side (modify in-place, separate step)

| File | Change |
|---|---|
| `captures/receive_image.py` | Default `--width` changed 9248→6944; stride auto-detect in unpack_10bit; gamma in debayer; `COLOR_BayerRG2BGR` |
| `main.py` | Remove `CameraManager._ssh_capture()`; add TCP listener on port 9999 to receive pushed raw frames |
| QML preview component | Replace `Camera`/`VideoOutput` with MJPEG HTTP source (`WebEngineView` loading `http://192.168.7.1:8080/stream.mjpg`) |
| `main.py` constants | Remove `PI_USB_IP`/`PI_USER`/`PI_PASS` (no more SSH); keep `DeviceManager` serial as-is |

> **Control protocol unchanged:** Windows → Pi: `CMD:CAPTURE`, `CMD:BRIGHTNESS:N`
> Pi → Windows: `EVT:CAPTURED:WxH`, `EVT:BRIGHTNESS:N`, `EVT:BTN_PRESSED`, `EVT:STATUS:ready`

---

## Step 1 — Flash & First Boot ✅ DONE

1. Flashed PiOS Lite **64-bit** (Trixie) — confirmed `uname -m` = `aarch64`
2. Hostname: `retinex`, User: `retinex`, Password: `retinopathy`, SSH enabled
3. WiFi SSH: `192.168.137.163` (during setup; superseded by USB NCM once gadget started)

---

## Step 2 — /boot/firmware/config.txt ✅ DONE

```ini
# [all] section
camera_auto_detect=0
dtoverlay=vc4-kms-v3d,cma-320
arm_boost=1
enable_uart=1
arm_64bit=1

[pi02]
dtoverlay=dwc2,dr_mode=peripheral
dtoverlay=ov64a40,link-frequency=360000000
gpu_mem=32
```

> **Critical notes:**
> - `arm_64bit=1` — enables 64-bit kernel. Required.
> - `link-frequency=360000000` — NOT 456000000 (Unicam timeout + corrupted image)
> - `cma-320` — max stable CMA on Zero 2W (cma-400 falls back to 256 MB due to physical RAM layout)
> - `dwc2,dr_mode=peripheral` only — no host mode needed (no UVC gadget, no V4L2 host path)
> - `gpu_mem=32` — minimum for camera firmware; don't go lower

---

## Step 3 — Install System Packages ✅ DONE

```bash
sudo apt update && sudo apt install -y \
    python3-picamera2 \
    python3-numpy \
    python3-serial \
    python3-gpiozero \
    v4l-utils \
    netcat-openbsd
```

> No `python3-opencv` on Pi side — `camera_daemon.py` uses PIL (already installed with picamera2).

---

## Step 4 — Deploy Pi Source Files ✅ DONE

Deploy via paramiko (WiFi SSH unreachable after NCM gadget starts; use USB NCM 192.168.7.1):

```python
import paramiko, pathlib
src = pathlib.Path('pi_src/camera_daemon.py').read_bytes()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.7.1', username='retinex', password='retinopathy', timeout=10)
sftp = c.open_sftp()
with sftp.open('/tmp/camera_daemon.py', 'wb') as f:
    f.write(src)
sftp.close()
stdin, stdout, stderr = c.exec_command(
    'sudo cp /tmp/camera_daemon.py /usr/local/bin/camera_daemon.py '
    '&& sudo systemctl restart retinex-camera && echo OK'
)
print(stdout.read().decode())
c.close()
```

Or via WiFi during initial setup:
```bash
scp pi_src/camera_daemon.py     retinex@192.168.137.X:/tmp/
scp pi_src/setup_usb_gadget_ncm.sh retinex@192.168.137.X:/tmp/
```

On Pi:
```bash
sudo cp /tmp/camera_daemon.py       /usr/local/bin/camera_daemon.py
sudo cp /tmp/setup_usb_gadget_ncm.sh /usr/local/bin/setup_usb_gadget.sh
sudo chmod +x /usr/local/bin/camera_daemon.py
sudo chmod +x /usr/local/bin/setup_usb_gadget.sh
```

---

## Step 5 — Create systemd Services ✅ DONE

### 5a. retinex-gadget.service

```bash
sudo tee /etc/systemd/system/retinex-gadget.service << 'EOF'
[Unit]
Description=Retinex USB Gadget Setup (NCM + ACM)
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/setup_usb_gadget.sh

[Install]
WantedBy=multi-user.target
EOF
```

### 5b. retinex-camera.service

```bash
sudo tee /etc/systemd/system/retinex-camera.service << 'EOF'
[Unit]
Description=Retinex Camera Daemon (MJPEG preview + capture)
After=retinex-gadget.service
Requires=retinex-gadget.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /usr/local/bin/camera_daemon.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 5c. Enable & start

```bash
sudo systemctl daemon-reload
sudo systemctl enable retinex-gadget retinex-camera
sudo systemctl start retinex-gadget
sudo systemctl start retinex-camera
```

---

## Step 6 — Windows NCM Network Setup ✅ DONE

Pi USB NCM up at `192.168.7.1/24`. Windows NCM adapter set to static IP:
- IP address: `192.168.7.2`
- Subnet mask: `255.255.255.0`
- Default gateway: *(blank)*

Verify:
```
ping 192.168.7.1
curl http://192.168.7.1:8080/stream.mjpg
```

SSH via USB NCM (WiFi address 192.168.137.x no longer reachable once gadget starts):
```bash
ssh retinex@192.168.7.1
# password: retinopathy
```

---

## Step 7 — Start Camera Daemon ✅ DONE

```bash
sudo systemctl start retinex-camera
```

Expected startup log:
```
Sensor: 9248x6944  CFA=3 (0=RGGB 1=GRBG 2=BGGR 3=GBRG)
Camera started: 1280x720 RGB888
Preview loop started
MJPEG: http://0.0.0.0:8080/stream.mjpg
Serial: opened /dev/ttyGS0
Button: monitoring GPIO17
```

> **CFA=3 = GBRG** from picamera2. Despite this, the correct debayer constant is
> `COLOR_BayerRG2BGR` (not BayerGB). This was confirmed by testing all 4 options —
> BayerGB/BayerGR produced checkerboard (1-pixel Bayer phase error).

---

## Step 8 — Verify Preview ✅ DONE

Browser → `http://192.168.7.1:8080/stream.mjpg` shows live MJPEG at 1280×720 ~20fps.

Preview auto-recovers after camera frontend timeouts (sustained error counter triggers
camera stop/restart while holding capture_lock to prevent concurrent access).

---

## Step 9 — Verify Capture ✅ DONE

On Windows, run receiver:
```bash
python captures/receive_image.py --port 9999 --loop --timestamp
```

Trigger capture (Pi serial):
```bash
echo "CMD:CAPTURE" > /dev/ttyGS0
```

Or trigger from Windows QML app capture button (sends `CMD:CAPTURE` via `DeviceManager` serial).

Expected:
- Pi: `Capture: 9248x6944 — stopping preview...` → `crop=6944x6944 ... 60.3MB` → `Capture done: total=Xs`
- Windows: `[recv] 60.3 MB received` → `[+] Saved: frame_TIMESTAMP.png`
- Pi serial: `EVT:CAPTURED:6944x6944`

Transfer size: **~60 MB** (6944×6944 square crop, down from ~80 MB full-width 9248×6944).

---

## Step 10 — Verify CMA ✅ DONE

```bash
grep -E "Cma|MemTotal|MemFree" /proc/meminfo
```

Expected:
- `CmaTotal: 327680 kB` (320 MB)
- `CmaFree` ≥ 100 MB when daemon is idle

---

## Step 11 — Windows App Changes ⏸ NEXT SESSION

### 11a. receive_image.py ✅ DONE (standalone use)
- Default `--width` changed 9248→6944
- `unpack_10bit()`: stride auto-detection (strip row padding if total > expected_tight)
- `debayer()`: gamma correction `x^(1/2.2)` added; `COLOR_BayerRG2BGR` confirmed correct
- Receive loop: `while True:` break on EOF (was `while len(data) < expected` — stopped early)

### 11b. Integrate TCP receiver into main.py ⏸ TODO
`main.py::CameraManager`:
- Remove `_ssh_capture()` and all paramiko/SSH imports
- Replace with a background TCP listener thread on port 9999 (logic from `receive_image.py`)
- When frame arrives: debayer → save → emit `imageSaved` signal
- `triggerCapture()` just sends `CMD:CAPTURE` via `DeviceManager` — no SSH needed

### 11c. QML preview ⏸ TODO
Replace the `Camera`/`VideoOutput` block with a `WebEngineView`:
```qml
import QtWebEngine

WebEngineView {
    url: "http://192.168.7.1:8080/stream.mjpg"
}
```
Add `python3-pyqt6-webengine` or `QtWebEngineWidgets` to Windows dependencies.

---

## Key Architecture Notes

### camera_daemon.py lock design (critical)
Two locks: `_cam_lock` (camera hardware access) and `capture_lock` (single capture at a time).

**Phase 1** (hold `_cam_lock`): snapshot AE/AG metadata → `cam.stop()` → `compact_memory`
(while stopped, no DMA) → `cam.configure(still)` → `cam.start()` → `cam.capture_array("raw")`
→ `cam.stop()` → `compact_memory` (defrag for next capture) → `cam.configure(video)` → `cam.start()`

**Phase 2** (no locks): numpy crop → `socket.sendall()` → `_send_evt()`

> `_send_evt()` MUST be called after all locks released — pyserial has no write_timeout,
> so a blocked CDC ACM port would deadlock the camera indefinitely.
>
> `_cam_lock` MUST be released before TCP send — otherwise preview_loop can't dequeue
> Unicam frames → buffer fills → V4L2 1-second frontend timeout fires.

### 1:1 square crop (Phase 2)
Crop center 6944×6944 pixels from 9248×6944 sensor output.
- `start_px = 1152` — aligns to 4-px CSI-2P boundary (1152 / 4 = 288 ✓)
- `end_px = 8096` — aligns (8096 / 4 = 2024 ✓)
- `start_byte = 288 * 5 = 1440`, `end_byte = 2024 * 5 = 10120` per row
- Transfer: 6944 × 8680 bytes = **60.3 MB** (vs 80.3 MB full-width)
- `receive_image.py` receives tight-packed data (no stride padding); `unpack_10bit` handles it.

### Bayer demosaicing
OV64A40 SRGGB10_CSI2P format = RGGB Bayer pattern.
Despite picamera2 reporting `ColorFilterArrangement=3` (GBRG), the correct OpenCV constant is
`COLOR_BayerRG2BGR`. All 4 were tested; BayerGB/BayerGR produced checkerboard artifacts.
Gamma correction `x^(1/2.2)` required before display (raw is linear, sensor values 0–1023).

### CMA compact_memory timing
`/proc/sys/vm/compact_memory` triggers synchronous CMA defragmentation.
- Call AFTER `cam.stop()` (no active DMA → safe)
- Do NOT call before `cam.configure()` (adds 1–3s lag and runs while DMA is inactive anyway)
- Call once after still capture to defragment for next video alloc
- Call once after video restore to prepare CMA for next capture cycle

### Why no UVC gadget?
The C `uvc-gadget` process holds `/dev/video0` exclusively. Any kill/restart causes UDC
rebind → full USB re-enumeration → Windows drops both the camera AND the CDC ACM COM port
(4–12 s gap). New approach: preview over HTTP (no V4L2), capture via picamera2 direct
stop/reconfigure — USB NCM never restarts.

### Capture timing (measured)
| Stage | Time |
|---|---|
| AE/AG snapshot + cam.stop() | ~0.1 s |
| compact_memory (while stopped) | ~0.5–1.5 s |
| cam.configure(still) + cam.start() | ~0.5–1 s |
| `capture_array("raw")` (sensor readout) | ~0.5–1.5 s |
| cam.stop() + compact_memory + cam.configure(video) + cam.start() | ~1–2 s |
| numpy center crop (6944×6944) | ~0.1 s |
| TCP send ~60 MB @ ~35 MB/s | ~1.7 s |
| `receive_image.py` unpack + debayer | ~1–2 s |
| **Total command-to-file** | **~6–9 s** |
| Preview gap (frozen frame, no re-enum) | **~3–5 s** |

### USB NCM vs ECM
NCM preferred — better throughput on Windows 10/11.
If `usb_f_ncm` module missing: replace `ncm` with `ecm` in `setup_usb_gadget_ncm.sh`.

### WINDOWS_IP in camera_daemon.py
Default `192.168.7.2`. Verify from Pi: `arp -n` or `ip neigh show dev usb0`.

### SSH after NCM gadget starts
WiFi address (`192.168.137.x`) becomes unreachable once USB NCM gadget is active.
Use `ssh retinex@192.168.7.1` (USB NCM). For file upload, use paramiko SFTP directly
(`rtk sshx exec` can't pipe stdin for file transfer).
