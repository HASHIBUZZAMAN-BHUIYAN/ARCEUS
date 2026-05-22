from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageOps
from smbus2 import SMBus
import time

# TCA9548A multiplexer I2C address (default is 0x70)
TCA9548A_ADDRESS = 0x70
TCA9548A_CHANNEL = 4  # Channel SD5/SC5 maps to channel 5

# Function to select a channel on TCA9548A
def select_tca_channel(channel):
    if 0 <= channel <= 7:
        with SMBus(1) as bus:
            bus.write_byte(TCA9548A_ADDRESS, 1 << channel)
    else:
        raise ValueError("Channel must be between 0 and 7")

# Select OLED's channel
select_tca_channel(TCA9548A_CHANNEL)

# OLED setup after selecting the right channel
serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

# Load eye expressions and invert the colors (black to white and vice versa)
def load_eye(name):
    img = Image.open(f"expressions/{name}.bmp").convert("1")
    img = ImageOps.invert(img)
    return img

# Blink effect: Blank screen for a short time, then show new image
def blink_and_show(new_img, blink_duration=0.1, delay_duration=1.5):
    blank = Image.new("1", (128, 64), color=0)
    device.display(blank)
    time.sleep(blink_duration)
    device.display(new_img)
    time.sleep(delay_duration)

# Show expression with blink transition
def show_expression(name, last_img=None):
    new_img = load_eye(name)
    if last_img:
        blink_and_show(new_img)
    else:
        device.display(new_img)
    return new_img

# Sequence of all possible expressions
expressions = [
    "front", "left", "right", 
    "top", "topLeft", "topRight", 
    "bottom", "bottomLeft", "bottomRight"
]

# Example sequence with blinking transition
if __name__ == "__main__":
    last = None
    for exp in expressions:
        last = show_expression(exp, last)
        time.sleep(1)



