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
still_config = None   # pre-created in main(); used by do_capture()
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
    Full-resolution JPEG capture via hardware encoder (bcm2835_codec MJPEGEncoder).

    Phase 1 (hold _cam_lock):
      - Lock AE, AWB, and AF position from running video frame
      - Stop video, switch to still mode, capture_file() → hardware JPEG
      - Stop still, compact CMA, reconfigure video (don't start yet)
      - Release _cam_lock

    Phase 2 (parallel, no locks):
      - Restore thread: acquire _cam_lock → cam.start(video) + re-enable AF
      - Main thread: read JPEG from /tmp → TCP send to Windows
      Both run concurrently; main waits for restore before releasing capture_lock.

    Windows receives RETINEX header with format=jpeg → saves directly, skips ISP.
    """
    if not capture_lock.acquire(blocking=False):
        log.warning("Capture already in progress — ignoring")
        return

    colour_gains = (2.278, 1.319)
    evt_to_send = None
    phase1_ok = False
    t0 = t1 = t2 = t3 = 0.0

    # Snapshot CMA state before acquiring lock; reset flag so next capture re-checks
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
        # Locking in video mode means controls propagate before we stop,
        # so no extra sleep is needed after starting still mode.
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
            # CMA not pre-compacted — trigger and wait (fallback path)
            try:
                with open("/proc/sys/vm/compact_memory", "w") as _f:
                    _f.write("1")
            except OSError:
                pass
            time.sleep(0.25)  # wait for async CMA compaction to complete
        # Embed AE-lock + ScalerCrop controls so they apply from frame 1.
        # ScalerCrop: center 6944×6944 from 9248×6944 sensor (x_off=1152, aligns to 4-px boundary).
        _still_cfg = still_config.copy()
        _sw, _sh = cam.sensor_resolution
        _crop_x = (_sw - _sh) // 2  # = (9248-6944)//2 = 1152 for OV64A40
        _ctrl = {"ScalerCrop": (_crop_x, 0, _sh, _sh), "NoiseReductionMode": 0}
        if meta is not None:
            _ctrl["AeEnable"] = False
            _ctrl["ExposureTime"] = meta["ExposureTime"]
            _ctrl["AnalogueGain"] = meta["AnalogueGain"]
        _still_cfg["controls"] = _ctrl
        cam.configure(_still_cfg)
        cam.start()

        t1 = time.perf_counter()
        from picamera2.encoders import JpegEncoder as _JEnc
        _enc = _JEnc(num_threads=4, q=75)
        _req = cam.capture_request()
        _t_req = time.perf_counter()
        try:
            jpeg_direct = _enc.encode_func(_req, "main")
        finally:
            _req.release()
        _t_enc = time.perf_counter()
        with open("/tmp/retinex_cap.jpg", "wb") as _jf:
            _jf.write(jpeg_direct)
        t2 = time.perf_counter()
        log.info(f"Capture: mode_switch={t1-t0:.2f}s  req_wait={_t_req-t1:.2f}s  enc={_t_enc-_t_req:.2f}s  total_jpeg={t2-t1:.2f}s  size={len(jpeg_direct)//1024}kB")

        cam.stop()
        try:
            with open("/proc/sys/vm/compact_memory", "w") as f:
                f.write("1")
        except OSError:
            pass
        cam.configure(video_config)   # configure only — start happens in Phase 2 thread
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
        _cam_lock.release()   # preview loop resumes; will get errors until cam.start() in Phase 2

    if not phase1_ok:
        capture_lock.release()
        if evt_to_send:
            _send_evt(evt_to_send)
        return

    # ── Phase 2: restore video ‖ read JPEG + send (parallel) ─────────────────
    def _restore_video():
        if not _cam_lock.acquire(timeout=5.0):
            log.error("Restore: camera lock timeout — preview may be stuck")
            return
        try:
            cam.start()
            cam.set_controls({"AfMode": 2, "AfSpeed": 1})
            log.info("Capture: video mode restored")
            # Pre-compact CMA now so next capture can skip the 0.25s wait
            threading.Thread(target=_compact_cma_async, daemon=True).start()
        except Exception as e:
            log.error(f"Restore failed: {e}", exc_info=True)
        finally:
            _cam_lock.release()

    restore_thread = threading.Thread(target=_restore_video, daemon=True)
    restore_thread.start()

    try:
        with open("/tmp/retinex_cap.jpg", "rb") as f:
            jpeg_bytes = f.read()
        t4 = time.perf_counter()
        log.info(
            f"Capture: compact+reconf={t3-t2:.2f}s  "
            f"read={t4-t3:.2f}s  {len(jpeg_bytes)/1e6:.1f}MB — sending..."
        )
        header = (
            f"RETINEX:r_gain={colour_gains[0]:.4f},b_gain={colour_gains[1]:.4f},format=jpeg\n"
        ).encode()
        with socket.create_connection((WINDOWS_IP, CAPTURE_PORT), timeout=60) as s:
            s.sendall(header)
            s.sendall(jpeg_bytes)
        t5 = time.perf_counter()
        log.info(
            f"Capture done: total={t5-t0:.2f}s "
            f"(lock+switch={t1-t0:.2f}s encode={t2-t1:.2f}s "
            f"compact={t3-t2:.2f}s read={t4-t3:.2f}s send={t5-t4:.2f}s)"
        )
        evt_to_send = "EVT:CAPTURED:6944x6944"
    except Exception as e:
        log.error(f"Capture failed (send phase): {e}", exc_info=True)
        evt_to_send = "EVT:STATUS:capture_error"

    restore_thread.join()
    capture_lock.release()

    # Send event after all locks released — serial write() has no write_timeout.
    if evt_to_send:
        _send_evt(evt_to_send)


# ---------- command dispatch ----------
def handle_cmd(cmd: str):
    log.info(f"CMD: {cmd!r}")
    if cmd == "CMD:CAPTURE":
        threading.Thread(target=do_capture, daemon=True).start()
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

    # Pre-create still config for 1:1 square crop at full sensor height (6944×6944).
    # ScalerCrop is applied per-capture in the control dict (can't be baked into config).
    _cap_size = sensor_h  # 6944 — square side; sensor is 9248×6944
    still_config = cam.create_still_configuration(
        main={"size": (_cap_size, _cap_size), "format": "YUV420"},
        buffer_count=1,
    )
    log.info(f"Still config: {_cap_size}x{_cap_size} YUV420 (1:1 square crop) buffer_count=1")

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
