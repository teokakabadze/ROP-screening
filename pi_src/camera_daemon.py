#!/usr/bin/env python3
"""
camera_daemon.py — Retinex Pi unified camera daemon (Option 1)
Replaces retinex_stream.py + retinex_control.py + uvc-gadget entirely.

Architecture:
  preview  — picamera2 → PIL JPEG → HTTP server on port 8080 (USB NCM)
  control  — CDC ACM serial /dev/ttyGS0 (same CMD:/EVT: protocol as before)
  capture  — lock camera → still mode → raw array → pack 10-bit → TCP push to Windows
  button   — GPIO17 physical trigger (same as before)
"""

import io
import os
import socket
import threading
import time
import logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from picamera2 import Picamera2
from PIL import Image
import simplejpeg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
log = logging.getLogger("camera_daemon")

# ---------- config ----------
SERIAL_DEV        = "/dev/ttyGS0"
PREVIEW_PORT      = 8080
CAPTURE_PORT      = 9999
BUTTON_PIN        = 17
BUTTON_DEBOUNCE_S = 0.3
JPEG_QUALITY      = 65

# Windows USB NCM adapter IP — set static 192.168.7.2 on Windows NCM adapter
WINDOWS_IP = "192.168.7.2"

# Preview resolution (lower = faster encode; ISP downscales from sensor)
PREVIEW_W = 1280
PREVIEW_H = 720


# ---------- MJPEG frame buffer ----------
class StreamOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def push(self, jpeg_bytes: bytes):
        with self.condition:
            self.frame = jpeg_bytes
            self.condition.notify_all()


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/capture":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"capture triggered\n")
            threading.Thread(target=do_capture, daemon=True).start()
            return
        if self.path not in ("/", "/stream.mjpg"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                with output.condition:
                    output.condition.wait(timeout=5.0)
                    frame = output.frame
                if frame is None:
                    continue
                self.wfile.write(b"--FRAME\r\n")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, *a):
        pass



# ---------- globals ----------
cam = None
video_config = None
still_config = None   # pre-created in main(); rebuilt by CMD:MODE
_capture_size = (6944, 6944)  # (w, h); updated by CMD:MODE:16MP/48MP
output = StreamOutput()
# Protects camera from concurrent access between preview thread and capture
_cam_lock = threading.Lock()
capture_lock = threading.Lock()
_serial_port = None
# True after _compact_cma_async() finishes; allows do_capture() to skip 0.25s sleep
_cma_clean = False


def _compact_cma_async():
    """Compact CMA in background; set _cma_clean when done."""
    global _cma_clean
    try:
        with open("/proc/sys/vm/compact_memory", "w") as f:
            f.write("1")
        time.sleep(0.35)   # wait for kernel async compaction
        _cma_clean = True
        log.info("CMA: pre-compaction done")
    except OSError:
        pass


def _rebuild_still_config():
    """Recreate still_config for the current _capture_size. Safe to call at runtime."""
    global still_config
    w, h = _capture_size
    still_config = cam.create_still_configuration(
        main={"size": (w, h), "format": "YUV420"},
        buffer_count=1,
    )
    log.info(f"Still config: {w}x{h} YUV420 buffer_count=1")


def _send_evt(text: str):
    port = _serial_port
    if port is not None:
        try:
            port.write(f"{text}\n".encode())
            port.flush()
        except OSError:
            pass


# ---------- preview thread ----------
def preview_loop():
    """
    Continuously captures RGB888 frames from camera and encodes to JPEG via PIL.
    Holds _cam_lock briefly per frame. Skips frames during capture (lock held).
    If the camera dies (frontend timeout), auto-recovers when no capture is running.
    """
    log.info("Preview loop started")
    consecutive_errors = 0
    RECOVER_AFTER = 15  # ~1.5s of failures

    while True:
        if not _cam_lock.acquire(timeout=0.05):
            time.sleep(0.05)
            continue
        if not cam.started:
            _cam_lock.release()
            time.sleep(0.05)
            continue
        try:
            frame = cam.capture_array("main")  # RGB888, shape (H, W, 3)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors == 1:
                log.warning(f"Preview: capture error: {e}")
            _cam_lock.release()

            # Auto-recover after sustained failure if no capture is in progress
            if consecutive_errors >= RECOVER_AFTER and capture_lock.acquire(blocking=False):
                log.warning(f"Preview: {consecutive_errors} errors — restarting camera...")
                try:
                    cam.stop()
                    try:
                        with open("/proc/sys/vm/compact_memory", "w") as f:
                            f.write("1")
                    except OSError:
                        pass
                    cam.configure(video_config)
                    cam.start()
                    cam.set_controls({"AfMode": 2, "AfSpeed": 1})
                    consecutive_errors = 0
                    log.info("Preview: camera restarted OK")
                except Exception as e2:
                    log.error(f"Preview: restart failed: {e2}")
                finally:
                    capture_lock.release()

            time.sleep(0.1)
            continue
        _cam_lock.release()

        try:
            img = Image.fromarray(frame)  # BGR888 = RGB bytes in memory — PIL reads correctly
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY)
            output.push(buf.getvalue())
        except Exception as e:
            log.debug(f"Preview encode error: {e}")

        time.sleep(0.05)  # cap at ~20fps; actual rate limited by encode time


# ---------- capture ----------
def do_capture():
    """
    Full-resolution JPEG capture via simplejpeg (fastdct, YCbCr/420).

    Phase 1 (hold _cam_lock):
      - Lock AE, AWB, AF from running video frame
      - Stop video, switch to still mode
      - capture_request(flush=True) → make_array() → req.release()
      - Stop still, compact CMA, reconfigure video (don't start yet)
      - Release _cam_lock  ← released before encode; preview can recover sooner

    Phase 2 (parallel, no locks):
      - Restore thread: acquire _cam_lock → cam.start(video) + re-enable AF
      - Main thread: simplejpeg.encode_jpeg(arr, fastdct=True) → TCP push
      Both run concurrently; encode and video restore overlap.

    Windows receives RETINEX header with format=jpeg → saves directly, skips ISP.
    """
    if not capture_lock.acquire(blocking=False):
        log.warning("Capture already in progress — ignoring")
        return

    colour_gains = (2.278, 1.319)
    evt_to_send = None
    phase1_ok = False
    t0 = t1 = _t_req = t3 = 0.0
    jpeg_direct = None

    global _cma_clean
    _cma_clean_snapshot = _cma_clean
    _cma_clean = False

    # ── Phase 1: camera operations (hold _cam_lock) ──────────────────────────
    if not _cam_lock.acquire(timeout=10.0):
        log.error("Capture: could not acquire camera lock within 10s — aborting")
        capture_lock.release()
        return

    try:
        t0 = time.perf_counter()

        # Snapshot and lock AE/AWB/AF from the current video frame.
        meta = None
        lens_pos = 0.0
        try:
            meta = cam.capture_metadata()
            cg = meta.get("ColourGains")
            if cg and len(cg) >= 2:
                colour_gains = (float(cg[0]), float(cg[1]))
            lens_pos = float(meta.get("LensPosition", 0.0))
            cam.set_controls({
                "AeEnable":     False,
                "ExposureTime": meta["ExposureTime"],
                "AnalogueGain": meta["AnalogueGain"],
                "AfMode":       0,       # manual — freezes VCM lens position
                "LensPosition": lens_pos,
                "AwbEnable":    False,
                "ColourGains":  colour_gains,
            })
            log.info(
                f"Capture: locked ET={meta['ExposureTime']} "
                f"AG={meta['AnalogueGain']:.2f} "
                f"Lens={lens_pos:.3f} "
                f"ColourGains=({colour_gains[0]:.3f},{colour_gains[1]:.3f})"
            )
        except Exception as e:
            log.warning(f"Capture: could not lock settings ({e}), using AE auto")

        log.info("Capture: switching to still mode...")
        cam.stop()
        if not _cma_clean_snapshot:
            try:
                with open("/proc/sys/vm/compact_memory", "w") as _f:
                    _f.write("1")
            except OSError:
                pass
            time.sleep(0.25)

        # Build still config controls — all baked in so they apply from frame 1.
        # For 48MP (6944×6944): ScalerCrop squares the sensor.
        # For 16MP (4624×3472): 2×2 binned mode, no crop needed.
        _still_cfg = still_config.copy()
        _sw, _sh = cam.sensor_resolution
        min_fd, _, _ = cam.camera_controls.get("FrameDurationLimits", (100_000, 10_000_000, 100_000))
        _ctrl = {
            "NoiseReductionMode":   0,          # disable ISP NR — reduces req_wait
            "FrameDurationLimits":  (min_fd, min_fd),  # run sensor as fast as possible
        }
        if _capture_size == (6944, 6944):
            _crop_x = (_sw - _sh) // 2   # = (9248-6944)//2 = 1152
            _ctrl["ScalerCrop"] = (_crop_x, 0, _sh, _sh)
        if meta is not None:
            _ctrl["AeEnable"]    = False
            _ctrl["ExposureTime"] = meta["ExposureTime"]
            _ctrl["AnalogueGain"] = meta["AnalogueGain"]
            _ctrl["AwbEnable"]   = False
            _ctrl["ColourGains"] = colour_gains
        _still_cfg["controls"] = _ctrl
        cam.configure(_still_cfg)
        cam.start()

        t1 = time.perf_counter()

        # Capture one fresh frame and encode to JPEG in-place (zero-copy via MappedArray).
        # fastdct=True skips the precise DCT (~15% speedup, imperceptible on clinical images).
        # Encode happens here in Phase 1, serialised with camera ops but contention-free
        # (no competing threads). Wind-down follows immediately after.
        from picamera2.encoders import JpegEncoder as _JpegEncoder
        _enc = _JpegEncoder(q=75)
        _enc.fastdct = True
        _req = cam.capture_request(flush=True)
        _t_req = time.perf_counter()
        try:
            jpeg_direct = _enc.encode_func(_req, "main")
        finally:
            _req.release()
        _t_enc = time.perf_counter()

        cam.stop()
        try:
            with open("/proc/sys/vm/compact_memory", "w") as f:
                f.write("1")
        except OSError:
            pass
        cam.configure(video_config)   # configure only — cam.start() in Phase 2 thread
        t3 = time.perf_counter()
        phase1_ok = True

    except Exception as e:
        log.error(f"Capture failed (camera phase): {e}", exc_info=True)
        try:
            cam.stop()
            cam.configure(video_config)
            cam.start()
            cam.set_controls({"AfMode": 2, "AfSpeed": 1})
        except Exception as e2:
            log.error(f"Failed to restore video mode: {e2}")
        evt_to_send = "EVT:STATUS:capture_error"
    finally:
        _cam_lock.release()   # released before encode; restore thread and preview can proceed

    if not phase1_ok:
        capture_lock.release()
        if evt_to_send:
            _send_evt(evt_to_send)
        return

    log.info(
        f"Capture: mode_switch={t1-t0:.2f}s  "
        f"req_wait={_t_req-t1:.2f}s  "
        f"enc={_t_enc-_t_req:.2f}s  "
        f"wind_down={t3-_t_enc:.2f}s  "
        f"size={len(jpeg_direct)//1024}kB"
    )

    # ── Phase 2: restore video ‖ encode + send (parallel) ────────────────────
    def _restore_video():
        if not _cam_lock.acquire(timeout=5.0):
            log.error("Restore: camera lock timeout — preview may be stuck")
            return
        try:
            cam.start()
            cam.set_controls({"AfMode": 2, "AfSpeed": 1})
            log.info("Capture: video mode restored")
            threading.Thread(target=_compact_cma_async, daemon=True).start()
        except Exception as e:
            log.error(f"Restore failed: {e}", exc_info=True)
        finally:
            _cam_lock.release()

    restore_thread = threading.Thread(target=_restore_video, daemon=True)
    restore_thread.start()

    try:
        header = (
            f"RETINEX:r_gain={colour_gains[0]:.4f},b_gain={colour_gains[1]:.4f},format=jpeg\n"
        ).encode()
        _MAX_SEND_ATTEMPTS = 3
        for _attempt in range(_MAX_SEND_ATTEMPTS):
            try:
                with socket.create_connection((WINDOWS_IP, CAPTURE_PORT), timeout=60) as s:
                    s.sendall(header)
                    s.sendall(jpeg_direct)
                break
            except ConnectionResetError as _e:
                if _attempt < _MAX_SEND_ATTEMPTS - 1:
                    log.warning(f"Capture: send reset (attempt {_attempt + 1}/{_MAX_SEND_ATTEMPTS}), retrying in 1.5s...")
                    time.sleep(1.5)
                else:
                    raise
        t5 = time.perf_counter()
        log.info(
            f"Capture done: total={t5-t0:.2f}s "
            f"(cam+enc={t3-t0:.2f}s send={t5-t3:.2f}s)"
        )
        evt_to_send = f"EVT:CAPTURED:{_capture_size[0]}x{_capture_size[1]}"
    except Exception as e:
        log.error(f"Capture failed (encode/send phase): {e}", exc_info=True)
        evt_to_send = "EVT:STATUS:capture_error"

    restore_thread.join()
    capture_lock.release()

    # Send event after all locks released — serial write() has no write_timeout.
    if evt_to_send:
        _send_evt(evt_to_send)


# ---------- command dispatch ----------
def handle_cmd(cmd: str):
    global _capture_size
    log.info(f"CMD: {cmd!r}")
    if cmd == "CMD:CAPTURE":
        threading.Thread(target=do_capture, daemon=True).start()
    elif cmd == "CMD:MODE:16MP":
        _capture_size = (4624, 3472)
        _rebuild_still_config()
        _send_evt("EVT:STATUS:mode_16mp")
    elif cmd == "CMD:MODE:48MP":
        _capture_size = (6944, 6944)
        _rebuild_still_config()
        _send_evt("EVT:STATUS:mode_48mp")
    elif cmd.startswith("CMD:BRIGHTNESS:"):
        try:
            val = int(cmd[15:])       # 0–100
            ev = (val - 50) / 25.0   # map 0–100 to -2.0 to +2.0 EV
            cam.set_controls({"ExposureValue": ev})
            _send_evt(f"EVT:BRIGHTNESS:{val}")
        except Exception as e:
            log.warning(f"Brightness cmd failed: {e}")
    elif cmd == "CMD:PING":
        _send_evt("EVT:STATUS:ready")


# ---------- serial loop ----------
def serial_loop():
    global _serial_port
    import serial as pyserial

    log.info(f"Serial: waiting for {SERIAL_DEV}...")
    while True:
        try:
            with pyserial.Serial(SERIAL_DEV, 115200, timeout=1) as ser:
                _serial_port = ser
                log.info(f"Serial: opened {SERIAL_DEV}")
                _send_evt("EVT:STATUS:ready")
                buf = ""
                while True:
                    data = ser.read(64)
                    if not data:
                        continue
                    for c in data.decode(errors="ignore"):
                        if c == "\n":
                            line = buf.strip()
                            buf = ""
                            if line:
                                handle_cmd(line)
                        elif c != "\r":
                            buf += c
        except Exception as e:
            log.warning(f"Serial: {e} — retrying in 3s")
            _serial_port = None
            time.sleep(3)


# ---------- button ----------
def button_monitor():
    try:
        from gpiozero import Button
        btn = Button(BUTTON_PIN, pull_up=True, bounce_time=BUTTON_DEBOUNCE_S)
        log.info(f"Button: monitoring GPIO{BUTTON_PIN}")
        while True:
            btn.wait_for_press()
            log.info("Button: pressed")
            _send_evt("EVT:BTN_PRESSED")
            threading.Thread(target=do_capture, daemon=True).start()
    except Exception as e:
        log.warning(f"Button monitor unavailable: {e}")


# ---------- main ----------
def main():
    global cam, video_config, still_config

    log.info("Initializing picamera2...")
    cam = Picamera2()

    sensor_w, sensor_h = cam.sensor_resolution
    cfa = cam.camera_properties.get("ColorFilterArrangement", "unknown")
    log.info(f"Sensor: {sensor_w}x{sensor_h}  CFA={cfa} (0=RGGB 1=GRBG 2=BGGR 3=GBRG)")

    # Pre-create still config for default mode (48MP, 6944×6944 square crop).
    # CMD:MODE:16MP / CMD:MODE:48MP reconfigure this at runtime.
    _rebuild_still_config()

    video_config = cam.create_video_configuration(
        main={"size": (PREVIEW_W, PREVIEW_H), "format": "BGR888"},  # BGR888=RGB bytes in memory; RGB888=BGR bytes
        controls={
            "FrameRate": 20,
            "AeEnable": True,
            "AwbEnable": True,
            "AfMode": 2,   # Continuous AF
            "AfSpeed": 1,  # Fast AF
        },
        buffer_count=2,
    )
    cam.configure(video_config)
    cam.start()
    cam.set_controls({"AfMode": 2, "AfSpeed": 1})
    log.info(f"Camera started: {PREVIEW_W}x{PREVIEW_H} RGB888")
    # Pre-compact CMA now so the first capture can skip the 0.25s wait
    threading.Thread(target=_compact_cma_async, daemon=True).start()

    # Set CPU governor to performance so encode runs at full clock speed.
    # Pi Zero 2W defaults to powersave (600MHz); performance pins all cores to 1GHz.
    for _cpu in range(4):
        try:
            with open(f"/sys/devices/system/cpu/cpu{_cpu}/cpufreq/scaling_governor", "w") as _f:
                _f.write("performance")
        except OSError:
            pass
    log.info("CPU: performance governor set")

    # Load hardware JPEG codec AFTER camera pipeline is running.
    # bcm2835_codec conflicts with Unicam init if loaded at boot (hence blacklisted);
    # loading here is safe and enables picamera2's MJPEGEncoder for capture_file().
    import subprocess as _sp
    _r = _sp.run(["modprobe", "bcm2835_codec"], capture_output=True)
    if _r.returncode == 0:
        log.info("bcm2835_codec loaded — hardware JPEG encoder available")
    else:
        log.warning(f"bcm2835_codec modprobe failed: {_r.stderr.decode().strip()} — will use software JPEG")

    # Start software JPEG preview thread
    threading.Thread(target=preview_loop, daemon=True).start()

    # HTTP MJPEG server
    server = ThreadingHTTPServer(("0.0.0.0", PREVIEW_PORT), MJPEGHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info(f"MJPEG: http://0.0.0.0:{PREVIEW_PORT}/stream.mjpg")

    # Serial and button
    threading.Thread(target=serial_loop, daemon=True).start()
    threading.Thread(target=button_monitor, daemon=True).start()

    log.info("Daemon running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        cam.stop()


if __name__ == "__main__":
    main()
