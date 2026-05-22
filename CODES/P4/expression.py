from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageOps
from smbus2 import SMBus
import time
import os

# ─── I2C multiplexer ─────────────────────────────────────────────────────────
TCA9548A_ADDRESS = 0x70
OLED_ADDRESSES = [0x3C, 0x3D]  # try both common addresses

def select_tca_channel(channel):
    if 0 <= channel <= 7:
        with SMBus(1) as bus:
            bus.write_byte(TCA9548A_ADDRESS, 1 << channel)
    else:
        raise ValueError("Channel must be between 0 and 7")

def scan_channel(channel):
    """Scan one TCA channel for OLED addresses."""
    select_tca_channel(channel)
    found = []
    with SMBus(1) as bus:
        for addr in OLED_ADDRESSES:
            try:
                bus.read_byte(addr)
                found.append(addr)
            except OSError:
                pass
    return found

def auto_detect_oled():
    """Find the first TCA channel and address where an OLED responds."""
    print("Scanning TCA9548A channels for OLED...")
    for ch in range(8):
        try:
            found = scan_channel(ch)
            if found:
                addr = found[0]
                print(f"✅ Found OLED at channel={ch}, address=0x{addr:02X}")
                return ch, addr
        except Exception as e:
            print(f"  Channel {ch} error: {e}")
    raise RuntimeError(
        "❌ No OLED found on any TCA9548A channel.\n"
        "   Check wiring, I2C enabled (raspi-config), and run: sudo i2cdetect -y 1"
    )

# ─── OLED setup ──────────────────────────────────────────────────────────────
channel, oled_address = auto_detect_oled()
select_tca_channel(channel)
serial = i2c(port=1, address=oled_address)
device = sh1106(serial)
print(f"OLED ready on channel {channel}, address 0x{oled_address:02X}")

# ─── Helpers ─────────────────────────────────────────────────────────────────
def load_eye(name):
    filepath = f"expressions/{name}.bmp"
    print(f"Loading: {filepath}")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Missing: {filepath}")
    img = Image.open(filepath).convert("1")
    return ImageOps.invert(img)

def blink_and_show(img, blink=0.1, hold=1.5):
    blank = Image.new("1", (128, 64), color=0)
    device.display(blank)
    time.sleep(blink)
    device.display(img)
    time.sleep(hold)

def clear_display():
    device.display(Image.new("1", (128, 64), color=0))

# ─── Expression loop ─────────────────────────────────────────────────────────
expressions = [
    "focus", "left", "right",
    "focus", "topLeft", "topRight",
    "focus", "bottomLeft", "bottomRight"
]

if __name__ == "__main__":
    last_img = None
    print("Running… Press Ctrl+C to stop.")
    try:
        while True:
            for exp in expressions:
                try:
                    new_img = load_eye(exp)
                    if last_img:
                        blink_and_show(new_img)
                    else:
                        device.display(new_img)
                        time.sleep(1.5)
                    last_img = new_img
                    time.sleep(1)
                except FileNotFoundError as e:
                    print(f"❌ {e}")
                    clear_display()
                    break
                except Exception as e:
                    print(f"❌ Unexpected error: {e}")
                    clear_display()
                    break
    except KeyboardInterrupt:
        clear_display()
        print("\nStopped by user (Ctrl+C).")