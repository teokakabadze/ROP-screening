#!/usr/bin/env python3
"""
retinex_stream.py
UVC streaming daemon for Retinex ROP Camera.
Bridges Arducam OWLSight 64MP (picamera2) to the UVC gadget device.
Handles UVC events, MJPEG frame streaming, full-res capture, and
brightness control via a Unix socket (used by retinex_control.py).
"""

import os
import sys
import fcntl
import mmap
import select
import ctypes
import threading
import socket
import time
import logging
import struct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("retinex_stream")

# ── Configuration ────────────────────────────────────────────────
UVC_DEVICE  = "/dev/video1"           # UVC gadget output device
CTRL_SOCK   = "/tmp/retinex_ctrl.sock"
STREAM_W    = 1920
STREAM_H    = 1080
CAPTURE_W   = 3472
CAPTURE_H   = 3472
CAPTURE_DIR = "/home/retinex/captures"
NUM_BUFS    = 4
JPEG_QUALITY = 70

# ── V4L2 ctypes structures (arm64 / Linux 6.x) ──────────────────

class _Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_longlong), ("tv_usec", ctypes.c_longlong)]


class _Timecode(ctypes.Structure):
    _fields_ = [
        ("type",     ctypes.c_uint32),
        ("flags",    ctypes.c_uint32),
        ("frames",   ctypes.c_uint8),
        ("seconds",  ctypes.c_uint8),
        ("minutes",  ctypes.c_uint8),
        ("hours",    ctypes.c_uint8),
        ("userbits", ctypes.c_uint8 * 4),
    ]


class _BufM(ctypes.Union):
    _fields_ = [
        ("offset",  ctypes.c_uint32),
        ("userptr", ctypes.c_ulong),
        ("fd",      ctypes.c_int32),
    ]


class V4L2Buffer(ctypes.Structure):
    _fields_ = [
        ("index",      ctypes.c_uint32),
        ("type",       ctypes.c_uint32),
        ("bytesused",  ctypes.c_uint32),
        ("flags",      ctypes.c_uint32),
        ("field",      ctypes.c_uint32),
        ("timestamp",  _Timeval),
        ("timecode",   _Timecode),
        ("sequence",   ctypes.c_uint32),
        ("memory",     ctypes.c_uint32),
        ("m",          _BufM),
        ("length",     ctypes.c_uint32),
        ("reserved2",  ctypes.c_uint32),
        ("request_fd", ctypes.c_int32),
    ]


class V4L2ReqBufs(ctypes.Structure):
    _fields_ = [
        ("count",        ctypes.c_uint32),
        ("type",         ctypes.c_uint32),
        ("memory",       ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("flags",        ctypes.c_uint8),
        ("reserved",     ctypes.c_uint8 * 3),
    ]


class V4L2EventSub(ctypes.Structure):
    _fields_ = [
        ("type",     ctypes.c_uint32),
        ("id",       ctypes.c_uint32),
        ("flags",    ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 5),
    ]


class V4L2Event(ctypes.Structure):
    _fields_ = [
        ("type",     ctypes.c_uint32),
        ("data",     ctypes.c_uint8 * 64),
        ("pending",  ctypes.c_uint32),
        ("sequence", ctypes.c_uint32),
        ("ts_sec",   ctypes.c_longlong),
        ("ts_nsec",  ctypes.c_longlong),
        ("id",       ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 8),
    ]


class UvcRequestData(ctypes.Structure):
    _fields_ = [("length", ctypes.c_int32), ("data", ctypes.c_uint8 * 60)]


# ── ioctl codes (verified on Pi Zero 2W arm64, Linux 6.12) ──────
def _IOC(d, t, n, s):
    return (d << 30) | (ord(t) << 8) | n | (s << 16)


V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_MEMORY_MMAP           = 1

VIDIOC_REQBUFS         = _IOC(3, "V",  8, ctypes.sizeof(V4L2ReqBufs))   # 0xc0145608
VIDIOC_QUERYBUF        = _IOC(3, "V",  9, ctypes.sizeof(V4L2Buffer))    # 0xc0585609
VIDIOC_QBUF            = _IOC(3, "V", 15, ctypes.sizeof(V4L2Buffer))    # 0xc058560f
VIDIOC_DQBUF           = _IOC(3, "V", 17, ctypes.sizeof(V4L2Buffer))    # 0xc0585611
VIDIOC_STREAMON        = _IOC(1, "V", 18, 4)                            # 0x40045612
VIDIOC_STREAMOFF       = _IOC(1, "V", 19, 4)                            # 0x40045613
VIDIOC_SUBSCRIBE_EVENT = _IOC(1, "V", 90, ctypes.sizeof(V4L2EventSub))  # 0x4020565a
VIDIOC_DQEVENT         = _IOC(2, "V", 89, ctypes.sizeof(V4L2Event))     # 0x80805659
UVCIOC_SEND_RESPONSE   = _IOC(1, "U",  1, ctypes.sizeof(UvcRequestData))# 0x40405501

# UVC event types
_EVT = 0x08000000
UVC_EVENT_CONNECT    = _EVT + 0
UVC_EVENT_DISCONNECT = _EVT + 1
UVC_EVENT_STREAMON   = _EVT + 2
UVC_EVENT_STREAMOFF  = _EVT + 3
UVC_EVENT_SETUP      = _EVT + 4
UVC_EVENT_DATA       = _EVT + 5

# UVC setup request codes
UVC_GET_CUR = 0x81
UVC_GET_MIN = 0x82
UVC_GET_MAX = 0x83
UVC_GET_DEF = 0x87
UVC_SET_CUR = 0x01
VS_PROBE_CONTROL  = 0x01
VS_COMMIT_CONTROL = 0x02


def _make_probe(frame_interval=333333):
    """Build a 34-byte UVC 1.1 VS_PROBE/COMMIT response."""
    max_frame_size = STREAM_W * STREAM_H * 2  # upper bound; kernel uses descriptor's dwMaxVideoFrameBufferSize
    return struct.pack(
        "<HBBIHHHHHIIIBBBB",
        0x0000,          # bmHint
        1,               # bFormatIndex  (MJPEG format, index 1 in gadget descriptor)
        3,               # bFrameIndex   (1080p = index 3; 720p=2, 480p=1 — configfs assigns in CREATION ORDER)
        frame_interval,  # dwFrameInterval (100 ns units, 333333 = 30fps)
        0, 0, 0, 0,      # wKeyFrameRate, wPFrameRate, wCompQuality, wCompWindowSize
        0,               # wDelay
        max_frame_size,  # dwMaxVideoFrameSize
        2048,            # dwMaxPayloadTransferSize — must match streaming_maxpacket in gadget script
        48000000,        # dwClockFrequency
        0x00,            # bmFramingInfo: 0 = JPEG SOI/EOI marker-based framing; no FID/EOF bits needed
        1,               # bPreferedVersion
        1,               # bMinVersion
        1,               # bMaxVersion
    )


# ── Streamer class ───────────────────────────────────────────────

class RetinexStreamer:
    def __init__(self):
        self.fd         = None      # UVC gadget file descriptor
        self.bufs       = []        # list of (mmap, length)
        self.streaming  = False
        self.cam        = None
        self._lock      = threading.Lock()
        self._brightness = 50       # 0..100
        self._stop_evt  = threading.Event()
        os.makedirs(CAPTURE_DIR, exist_ok=True)

    # ── Camera helpers ───────────────────────────────────────────

    def _start_camera(self):
        from picamera2 import Picamera2
        self.cam = Picamera2()
        brightness_norm = (self._brightness - 50) / 50.0
        cfg = self.cam.create_video_configuration(
            main={"size": (STREAM_W, STREAM_H), "format": "BGR888"},
            raw=None,
            buffer_count=2,
            controls={"FrameRate": 30, "Brightness": brightness_norm},
        )
        self.cam.configure(cfg)
        self.cam.start()
        log.info("Camera started at %dx%d", STREAM_W, STREAM_H)

    def _stop_camera(self):
        if self.cam:
            try:
                self.cam.stop()
                self.cam.close()
            except Exception as e:
                log.warning("Camera stop error: %s", e)
            self.cam = None
        log.info("Camera stopped")

    def _start_camera_bg(self):
        """Initialize camera in background; _frame_loop sends blank frames until it's ready."""
        try:
            self._start_camera()
        except Exception as e:
            log.error("Background camera start failed: %s", e)
            with self._lock:
                self._stop_camera()
            return

        with self._lock:
            if not self.streaming:
                # STREAMOFF fired while camera was initializing — don't leave it running
                self._stop_camera()
                return

        log.info("Camera ready — real frames will start")

    def set_brightness(self, value: int):
        self._brightness = max(0, min(100, value))
        if self.cam:
            norm = (self._brightness - 50) / 50.0
            self.cam.set_controls({"Brightness": norm})
            log.info("Brightness set to %d", self._brightness)

    def capture_full_res(self) -> str:
        """Capture at full 64MP resolution. Returns saved path or ''."""
        from picamera2 import Picamera2

        with self._lock:
            was_streaming = self.streaming
            if was_streaming:
                self._stop_streaming_locked()
            self._stop_camera()  # release camera for exclusive still access

        try:
            cam = Picamera2()
            cfg = cam.create_still_configuration(
                main={"size": (CAPTURE_W, CAPTURE_H)},
                raw=None,
                buffer_count=2,
            )
            cam.configure(cfg)
            cam.start()
            time.sleep(0.8)  # let AEC/AWB settle
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = f"{CAPTURE_DIR}/ROP_{ts}.jpg"
            cam.options["quality"] = 95
            cam.capture_file(path)
            cam.stop()
            cam.close()
            log.info("Full-res capture saved: %s", path)
        except Exception as e:
            log.error("Full-res capture failed: %s", e)
            path = ""

        # Restart streaming camera then resume UVC stream if it was active
        self._start_camera()
        if was_streaming:
            with self._lock:
                self._start_streaming_locked()

        return path

    # ── V4L2 buffer management ───────────────────────────────────

    def _alloc_buffers(self):
        req = V4L2ReqBufs()
        req.count  = NUM_BUFS
        req.type   = V4L2_BUF_TYPE_VIDEO_OUTPUT
        req.memory = V4L2_MEMORY_MMAP
        fcntl.ioctl(self.fd, VIDIOC_REQBUFS, req)

        self.bufs = []
        for i in range(req.count):
            qb = V4L2Buffer()
            qb.index  = i
            qb.type   = V4L2_BUF_TYPE_VIDEO_OUTPUT
            qb.memory = V4L2_MEMORY_MMAP
            fcntl.ioctl(self.fd, VIDIOC_QUERYBUF, qb)
            mm = mmap.mmap(self.fd.fileno(), qb.length,
                           mmap.MAP_SHARED, mmap.PROT_WRITE,
                           offset=qb.m.offset)
            self.bufs.append((mm, qb.length))

        log.info("Allocated %d V4L2 buffers", req.count)

    def _free_buffers(self):
        try:
            buf_type = ctypes.c_uint32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
            fcntl.ioctl(self.fd, VIDIOC_STREAMOFF, buf_type)
        except Exception:
            pass
        for mm, _ in self.bufs:
            try:
                mm.close()
            except Exception:
                pass
        self.bufs = []
        req = V4L2ReqBufs()
        req.count  = 0
        req.type   = V4L2_BUF_TYPE_VIDEO_OUTPUT
        req.memory = V4L2_MEMORY_MMAP
        try:
            fcntl.ioctl(self.fd, VIDIOC_REQBUFS, req)
        except Exception:
            pass

    def _qbuf(self, idx: int, bytesused: int):
        qb = V4L2Buffer()
        qb.index     = idx
        qb.type      = V4L2_BUF_TYPE_VIDEO_OUTPUT
        qb.memory    = V4L2_MEMORY_MMAP
        qb.bytesused = bytesused
        fcntl.ioctl(self.fd, VIDIOC_QBUF, qb)

    def _dqbuf(self) -> int:
        qb = V4L2Buffer()
        qb.type   = V4L2_BUF_TYPE_VIDEO_OUTPUT
        qb.memory = V4L2_MEMORY_MMAP
        fcntl.ioctl(self.fd, VIDIOC_DQBUF, qb)
        return qb.index

    # ── Streaming start/stop ─────────────────────────────────────

    def _start_streaming_locked(self):
        self._stop_evt.clear()
        self._alloc_buffers()

        # Seed all buffers with a blank UVC payload so Windows gets an immediate response
        blank = b"\xff\xd8\xff\xd9"
        for i in range(len(self.bufs)):
            mm, sz = self.bufs[i]
            mm.seek(0)
            mm.write(blank)
            self._qbuf(i, len(blank))

        buf_type = ctypes.c_uint32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
        fcntl.ioctl(self.fd, VIDIOC_STREAMON, buf_type)
        self.streaming = True

        if self.cam is None:
            # Camera not ready — init it in background; frame loop sends blanks until it's up
            threading.Thread(target=self._start_camera_bg, daemon=True).start()

        threading.Thread(target=self._frame_loop, daemon=True).start()
        log.info("Streaming started")

    def _stop_streaming_locked(self):
        self.streaming = False
        self._stop_evt.set()
        time.sleep(0.3)
        self._free_buffers()
        # Camera kept alive — avoids 13s re-init on next STREAMON
        log.info("Streaming stopped")

    # ── Frame loop ───────────────────────────────────────────────

    def _frame_loop(self):
        import cv2
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        blank = b"\xff\xd8\xff\xd9"
        frame_count = 0
        cam_errors = 0

        while self.streaming and not self._stop_evt.is_set():
            payload = blank

            if self.cam is not None:
                try:
                    frame = self.cam.capture_array("main")  # BGR888 numpy array
                    ret, jpeg_arr = cv2.imencode(".jpg", frame, encode_params)
                    if ret:
                        payload = jpeg_arr.tobytes()
                        frame_count += 1
                        cam_errors = 0
                        if frame_count % 60 == 0:
                            log.info("Frame %d sent (%d bytes JPEG)", frame_count, len(jpeg_arr))
                except Exception as e:
                    cam_errors += 1
                    if self.streaming:
                        log.warning("Frame loop error #%d: %s", cam_errors, e)
                    if cam_errors >= 5:
                        log.warning("Camera broken — restarting in background")
                        self._stop_camera()
                        threading.Thread(target=self._start_camera_bg, daemon=True).start()
                        cam_errors = 0
                    time.sleep(0.1)
                    # Fall through with blank payload — keep Windows connected
            else:
                # Camera still initializing — send blank at ~30fps to keep Windows happy
                time.sleep(0.033)

            # Wait for a free output buffer slot
            try:
                _, w, _ = select.select([], [self.fd], [], 0.5)
                if not w or not self.streaming:
                    continue
                idx = self._dqbuf()
                mm, sz = self.bufs[idx]
                n = min(len(payload), sz)
                mm.seek(0)
                mm.write(payload[:n])
                self._qbuf(idx, n)
            except OSError as e:
                if self.streaming:
                    log.warning("Buffer I/O error (USB disconnect?): %s", e)
                break  # exit frame loop; streaming flag checked by event loop

    # ── UVC event handling ────────────────────────────────────────

    def _subscribe_events(self):
        for ev_type in [UVC_EVENT_CONNECT, UVC_EVENT_DISCONNECT,
                        UVC_EVENT_STREAMON, UVC_EVENT_STREAMOFF,
                        UVC_EVENT_SETUP, UVC_EVENT_DATA]:
            sub = V4L2EventSub()
            sub.type = ev_type
            fcntl.ioctl(self.fd, VIDIOC_SUBSCRIBE_EVENT, sub)

    def _send_uvc_response(self, length: int, data: bytes):
        resp = UvcRequestData()
        resp.length = length
        n = min(len(data), 60)
        for i in range(n):
            resp.data[i] = data[i]
        fcntl.ioctl(self.fd, UVCIOC_SEND_RESPONSE, resp)

    def _handle_setup(self, ev, ev_data: bytes):
        # ev_data is ctrlrequest from ev.data[4:12] (kernel has 4-byte speed field first)
        b_request_type = ev_data[0]
        b_request = ev_data[1]
        w_value   = int.from_bytes(ev_data[2:4], "little")
        w_index   = int.from_bytes(ev_data[4:6], "little")
        w_length  = int.from_bytes(ev_data[6:8], "little")
        cs        = (w_value >> 8) & 0xFF
        vs_iface  = (w_index & 0xFF) == 1  # VS interface is always interface 1

        log.info("UVC SETUP bRT=0x%02x req=0x%02x cs=0x%02x wi=0x%04x wlen=%d",
                 b_request_type, b_request, cs, w_index, w_length)

        if vs_iface and cs in (VS_PROBE_CONTROL, VS_COMMIT_CONTROL):
            probe = _make_probe()
            if b_request in (UVC_GET_CUR, UVC_GET_MIN, UVC_GET_MAX, UVC_GET_DEF):
                self._send_uvc_response(len(probe), probe)
            elif b_request == UVC_SET_CUR:
                # Accept whatever the host proposes
                self._send_uvc_response(w_length, b"")
            else:
                self._send_uvc_response(-1, b"")  # stall
        elif b_request == 0x86:  # GET_INFO — respond "no capabilities" for all VC controls
            self._send_uvc_response(1, bytes([0x00]))
        elif b_request in (UVC_GET_CUR, UVC_GET_MIN, UVC_GET_MAX, UVC_GET_DEF):
            # Unknown VC control GET — respond with zeros
            self._send_uvc_response(w_length, bytes(w_length))
        elif b_request == UVC_SET_CUR:
            # Unknown VC control SET — ack
            self._send_uvc_response(w_length, b"")
        else:
            self._send_uvc_response(-1, b"")  # stall truly unknown

    # ── Control socket server ────────────────────────────────────

    def _ctrl_loop(self):
        if os.path.exists(CTRL_SOCK):
            os.unlink(CTRL_SOCK)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(CTRL_SOCK)
        srv.listen(5)
        os.chmod(CTRL_SOCK, 0o666)
        log.info("Control socket listening at %s", CTRL_SOCK)
        while True:
            try:
                conn, _ = srv.accept()
                threading.Thread(
                    target=self._handle_ctrl, args=(conn,), daemon=True
                ).start()
            except Exception as e:
                log.warning("Control socket error: %s", e)

    def _handle_ctrl(self, conn):
        with conn:
            try:
                raw = conn.recv(256).decode(errors="replace").strip()
                if raw == "CAPTURE":
                    path = self.capture_full_res()
                    conn.sendall(f"CAPTURED:{path}\n".encode())
                elif raw.startswith("BRIGHTNESS:"):
                    val = int(raw.split(":", 1)[1])
                    self.set_brightness(val)
                    conn.sendall(b"OK\n")
                else:
                    conn.sendall(b"ERR:unknown\n")
            except Exception as e:
                log.warning("ctrl handler error: %s", e)

    # ── Main event loop ──────────────────────────────────────────

    def run(self):
        threading.Thread(target=self._ctrl_loop, daemon=True).start()

        # Wait for UVC gadget device to appear (needs gadget service to run first)
        for _ in range(30):
            if os.path.exists(UVC_DEVICE):
                break
            log.info("Waiting for %s ...", UVC_DEVICE)
            time.sleep(2)
        else:
            log.error("UVC device %s did not appear. Is retinex-gadget running?", UVC_DEVICE)
            sys.exit(1)

        self.fd = open(UVC_DEVICE, "rb+", buffering=0)
        self._subscribe_events()
        log.info("UVC gadget open at %s, waiting for host connection...", UVC_DEVICE)
        # Pre-init camera so it's ready when STREAMON arrives (avoids blank-frame timeout)
        threading.Thread(target=self._start_camera_bg, daemon=True).start()

        while True:
            # UVC gadget events signal POLLPRI — use exceptional set, not read
            _, _, x = select.select([], [], [self.fd], 1.0)
            if not x:
                continue

            ev = V4L2Event()
            try:
                fcntl.ioctl(self.fd, VIDIOC_DQEVENT, ev)
            except Exception as e:
                log.warning("DQEVENT error: %s", e)
                continue

            if ev.type == UVC_EVENT_CONNECT:
                log.info("Host USB connected (speed=%d)", int.from_bytes(bytes(ev.data[:4]), "little"))
            elif ev.type == UVC_EVENT_DISCONNECT:
                log.info("Host USB disconnected")
                with self._lock:
                    if self.streaming:
                        self._stop_streaming_locked()
                # Camera left running — ready for next host connection
            elif ev.type == UVC_EVENT_SETUP:
                self._handle_setup(ev, bytes(ev.data[4:12]))
            elif ev.type == UVC_EVENT_DATA:
                # ev.data = uvc_request_data: [0:4]=length, [4:64]=UVC data
                # UVC probe: bmHint[0:2], bFormatIndex[2], bFrameIndex[3], dwFrameInterval[4:8]
                # → in ev.data: offset 4+2=6 for bFormatIndex, 7 for bFrameIndex, 8:12 for interval
                data = bytes(ev.data[:12])
                if len(data) >= 12:
                    fmt_idx = data[6]
                    frm_idx = data[7]
                    interval = int.from_bytes(data[8:12], "little")
                    fps = round(10_000_000 / interval) if interval else 0
                    log.info("UVC COMMIT data: bFormatIndex=%d bFrameIndex=%d interval=%d (~%dfps)",
                             fmt_idx, frm_idx, interval, fps)
            elif ev.type == UVC_EVENT_STREAMON:
                log.info("UVC STREAMON")
                with self._lock:
                    if not self.streaming:
                        self._start_streaming_locked()
            elif ev.type == UVC_EVENT_STREAMOFF:
                log.info("UVC STREAMOFF")
                with self._lock:
                    if self.streaming:
                        self._stop_streaming_locked()


if __name__ == "__main__":
    RetinexStreamer().run()
