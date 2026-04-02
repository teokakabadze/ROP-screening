#!/bin/bash
# setup_usb_gadget_ncm.sh — Option 1 gadget: CDC ACM + USB NCM only (NO UVC)
# Run as root at boot (retinex-gadget.service)
set -e

GADGET=/sys/kernel/config/usb_gadget/retinex
ACM="${GADGET}/functions/acm.usb0"
NCM="${GADGET}/functions/ncm.usb0"

load_mod() { /sbin/modprobe "$1" 2>/dev/null || true; }

echo "Loading kernel modules..."
load_mod libcomposite
load_mod usb_f_acm
load_mod usb_f_ncm   # USB NCM (Network Control Model) — better than ECM on Windows 10+

# ---- Tear down any previous gadget ----
if [ -d "$GADGET" ]; then
    echo "Cleaning up previous gadget..."
    echo "" > "${GADGET}/UDC" 2>/dev/null || true
    sleep 0.2
    rm -f "${GADGET}/configs/c.1/acm.usb0" 2>/dev/null || true
    rm -f "${GADGET}/configs/c.1/ncm.usb0" 2>/dev/null || true
    rmdir "${GADGET}/configs/c.1/strings/0x409" 2>/dev/null || true
    rmdir "${GADGET}/configs/c.1" 2>/dev/null || true
    rmdir "$ACM" 2>/dev/null || true
    rmdir "$NCM" 2>/dev/null || true
    rmdir "${GADGET}/strings/0x409" 2>/dev/null || true
    rmdir "${GADGET}" 2>/dev/null || true
fi

mkdir -p "$GADGET"
cd "$GADGET"

# ---- Gadget identity ----
echo 0x1d6b > idVendor     # Linux Foundation
echo 0x0104 > idProduct    # Multifunction Composite Gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB
echo 0xEF   > bDeviceClass
echo 0x02   > bDeviceSubClass
echo 0x01   > bDeviceProtocol

mkdir -p strings/0x409
echo "Retinex Ltd"    > strings/0x409/manufacturer
echo "Retinex Camera" > strings/0x409/product
echo "RETINEX00003"   > strings/0x409/serialnumber

# ---- CDC ACM (serial control channel) ----
mkdir -p "functions/acm.usb0"

# ---- USB NCM (network for MJPEG preview + image transfer) ----
mkdir -p "functions/ncm.usb0"
# Fixed MAC addresses so Windows doesn't create new adapter on each plug
echo "12:34:56:78:9a:bc" > "functions/ncm.usb0/host_addr"   # Windows side MAC
echo "12:34:56:78:9a:bd" > "functions/ncm.usb0/dev_addr"    # Pi side MAC

# ---- USB config ----
mkdir -p configs/c.1/strings/0x409
echo "Retinex NCM+ACM" > configs/c.1/strings/0x409/configuration
echo 500               > configs/c.1/MaxPower

ln -sf "$(pwd)/functions/acm.usb0" configs/c.1/acm.usb0
ln -sf "$(pwd)/functions/ncm.usb0" configs/c.1/ncm.usb0

# ---- Bind to UDC ----
UDC=$(ls /sys/class/udc | head -1)
echo "$UDC" > UDC
echo "Gadget active: ${UDC}"

# ---- Bring up USB NCM network interface ----
# Wait for usb0 to appear (up to 5s)
for i in $(seq 1 10); do
    ip link show usb0 &>/dev/null && break
    sleep 0.5
done

if ip link show usb0 &>/dev/null; then
    ip link set usb0 up
    ip addr flush dev usb0 2>/dev/null || true
    ip addr add 192.168.7.1/24 dev usb0
    echo "usb0 up: 192.168.7.1/24"
else
    echo "WARNING: usb0 did not appear — check NCM module loaded"
fi
