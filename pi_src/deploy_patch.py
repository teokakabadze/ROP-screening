#!/usr/bin/env python3
"""Patch /usr/local/bin/camera_daemon.py with square-crop changes."""
import sys

path = "/usr/local/bin/camera_daemon.py"
with open(path, "r") as f:
    c = f.read()

# ── Change 1: still_config size → square ────────────────────────────────────
old1 = '        main={"size": (sensor_w, sensor_h), "format": "YUV420"},'
new1 = '        main={"size": (_cap_size, _cap_size), "format": "YUV420"},'
if old1 not in c:
    print("ERROR: Change 1 old text not found - already patched?")
else:
    c = c.replace(old1, new1)
    print("Change 1 applied: still_config size → (_cap_size, _cap_size)")

# ── Change 2: log line ───────────────────────────────────────────────────────
old2 = '    log.info(f"Still config: {sensor_w}x{sensor_h} RGB888 buffer_count=1")'
new2 = '    log.info(f"Still config: {_cap_size}x{_cap_size} YUV420 (1:1 square crop) buffer_count=1")'
if old2 not in c:
    print("ERROR: Change 2 old text not found - already patched?")
else:
    c = c.replace(old2, new2)
    print("Change 2 applied: log line updated")

# ── Change 3: controls dict → add ScalerCrop ────────────────────────────────
old3 = ('        if meta is not None:\n'
        '            _still_cfg["controls"] = {"AeEnable": False, "ExposureTime": meta["ExposureTime"],\n'
        '                                      "AnalogueGain": meta["AnalogueGain"]}\n'
        '        cam.configure(_still_cfg)')
new3 = ('        _sw, _sh = cam.sensor_resolution\n'
        '        _crop_x = (_sw - _sh) // 2  # 1152 for OV64A40\n'
        '        _ctrl = {"ScalerCrop": (_crop_x, 0, _sh, _sh)}\n'
        '        if meta is not None:\n'
        '            _ctrl["AeEnable"] = False\n'
        '            _ctrl["ExposureTime"] = meta["ExposureTime"]\n'
        '            _ctrl["AnalogueGain"] = meta["AnalogueGain"]\n'
        '        _still_cfg["controls"] = _ctrl\n'
        '        cam.configure(_still_cfg)')
if old3 not in c:
    print("ERROR: Change 3 old text not found — check for existing patch")
    print("--- looking for the controls block ---")
    for i, line in enumerate(c.splitlines(), 1):
        if "_still_cfg" in line or "AeEnable" in line or "ScalerCrop" in line:
            print(f"  {i}: {line}")
else:
    c = c.replace(old3, new3)
    print("Change 3 applied: ScalerCrop + restructured controls")

with open(path, "w") as f:
    f.write(c)
print("Done.")
