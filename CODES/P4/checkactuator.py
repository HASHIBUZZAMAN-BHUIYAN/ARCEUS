"""
servo_control.py - Interactive Servo Control Menu
Hardware: Raspberry Pi 4B+ -> TCA9548A -> 2x PCA9685

Navigation:
  Main menu  : type servo number -> enter servo control mode
  Servo mode : type  min | max | ini  to move the servo
               press Ctrl+B then M    to return to main menu
"""

import sys
import time
import termios
import tty

import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_bus_device.i2c_device import I2CDevice

# ──────────────────────────────────────────────
#  HARDWARE CONSTANTS
# ──────────────────────────────────────────────
BODY_TCA_CHANNEL = 0
LEG_TCA_CHANNEL  = 5
TCA_ADDR         = 0x70

# ──────────────────────────────────────────────
#  SERVO TABLE
#  Each entry: (display_name, tca_channel, pca_channel, initial, max_ang, min_ang)
# ──────────────────────────────────────────────
SERVOS = [
    # ── BODY (TCA channel 0) ──────────────────────────────────────────────
    ( 1, "Neck_Y",            BODY_TCA_CHANNEL,  0,  105, 150,  60),
    ( 2, "Neck_X",            BODY_TCA_CHANNEL, 11,   95, 180,  10),
    ( 3, "Chest_Arm_Left",    BODY_TCA_CHANNEL, 12,  150, 180,  50),
    ( 4, "Chest_Arm_Right",   BODY_TCA_CHANNEL, 10,   40, 145,  10),
    ( 5, "Shoulder_Left",     BODY_TCA_CHANNEL,  3,   30, 180,  10),
    ( 6, "Shoulder_Right",    BODY_TCA_CHANNEL,  1,  150,   0, 170),
    ( 7, "Bicep_Left",        BODY_TCA_CHANNEL,  4,  100, 160,  40),
    ( 8, "Bicep_Right",       BODY_TCA_CHANNEL,  2,  100, 140,  60),
    ( 9, "Elbow_Left",        BODY_TCA_CHANNEL,  7,   95, 155,  40),
    (10, "Elbow_Right",       BODY_TCA_CHANNEL,  5,   95, 155,  40),
    (11, "Gripper_Left",      BODY_TCA_CHANNEL,  8,   95,  95,  40),
    (12, "Gripper_Right",     BODY_TCA_CHANNEL,  6,   95,  95,  40),
    (13, "Spinal_X",          BODY_TCA_CHANNEL,  9,  102, 110,  94),
    # ── LEGS (TCA channel 5) ─────────────────────────────────────────────
    (14, "Hip_Yaw_Left",      LEG_TCA_CHANNEL,  11,  100, 120,  80),
    (15, "Hip_Yaw_Right",     LEG_TCA_CHANNEL,   0,  100, 120,  80),
    (16, "Hip_Roll_Left",     LEG_TCA_CHANNEL,  10,  105, 115,  95),
    (17, "Hip_Roll_Right",    LEG_TCA_CHANNEL,   1,  105, 115,  95),
    (18, "Hip_Pitch_Left",    LEG_TCA_CHANNEL,   9,   95, 105,  85),
    (19, "Hip_Pitch_Right",   LEG_TCA_CHANNEL,   2,   95, 105,  85),
    (20, "Knee_Left",         LEG_TCA_CHANNEL,   8,  145, 145, 105),
    (21, "Knee_Right",        LEG_TCA_CHANNEL,   3,   65, 105,  55),
    (22, "Ankle_Pitch_Left",  LEG_TCA_CHANNEL,   7,  130, 150, 110),
    (23, "Ankle_Pitch_Right", LEG_TCA_CHANNEL,   4,   65,  85,  45),
    (24, "Ankle_Roll_Left",   LEG_TCA_CHANNEL,   6,  100, 130,  70),
    (25, "Ankle_Roll_Right",  LEG_TCA_CHANNEL,   5,  100, 130,  70),
]

# Build a quick lookup dict:  number → servo tuple
SERVO_MAP = {s[0]: s for s in SERVOS}

# ──────────────────────────────────────────────
#  I²C / HARDWARE HELPERS
# ──────────────────────────────────────────────
i2c = busio.I2C(board.SCL, board.SDA)

def select_tca_channel(channel: int):
    """Activate a single TCA9548A channel."""
    if 0 <= channel <= 7:
        with I2CDevice(i2c, TCA_ADDR) as dev:
            dev.write(bytes([1 << channel]))

def calculate_duty(angle: float) -> int:
    """Convert angle (0-180 deg) to 16-bit PWM duty for 50 Hz servos."""
    min_pulse = 500    # us
    max_pulse = 2500   # us
    pulse = min_pulse + (max_pulse - min_pulse) * (angle / 180.0)
    return int((pulse / 1_000_000.0) * 50.0 * 65535)

def move_servo(tca_ch: int, pca_ch: int, angle: float):
    """Move a single servo to the given angle."""
    select_tca_channel(tca_ch)
    time.sleep(0.01)
    pca = PCA9685(i2c)
    pca.frequency = 50
    pca.channels[pca_ch].duty_cycle = calculate_duty(angle)
    time.sleep(0.05)

# ──────────────────────────────────────────────
#  RAW CHARACTER INPUT  (Ctrl+B detection)
# ──────────────────────────────────────────────
CTRL_B = '\x02'   # ASCII 2

def read_line_with_ctrlb(prompt: str) -> str | None:
    """
    Display prompt and read a line of input character by character.

    Returns:
        '__MENU__'  if Ctrl+B → M/m was detected anywhere in the input
        The typed string otherwise (stripped, lowercased)
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    buf = []
    try:
        tty.setraw(fd)
        ctrl_b_pending = False

        while True:
            ch = sys.stdin.read(1)

            # ── Ctrl+B pressed ──────────────────────────────────
            if ch == CTRL_B:
                ctrl_b_pending = True
                continue

            if ctrl_b_pending:
                ctrl_b_pending = False
                if ch.lower() == 'm':
                    # Go to menu — print a newline so terminal looks clean
                    sys.stdout.write('\r\n')
                    sys.stdout.flush()
                    return '__MENU__'
                # Not 'm': treat Ctrl+B as no-op, fall through with ch

            # ── Enter / Return ───────────────────────────────────
            if ch in ('\r', '\n'):
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                return ''.join(buf).strip().lower()

            # ── Backspace ────────────────────────────────────────
            if ch in ('\x7f', '\x08'):
                if buf:
                    buf.pop()
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
                continue

            # ── Ctrl+C ───────────────────────────────────────────
            if ch == '\x03':
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                raise KeyboardInterrupt

            # ── Printable character ──────────────────────────────
            buf.append(ch)
            sys.stdout.write(ch)
            sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# ──────────────────────────────────────────────
#  UI HELPERS
# ──────────────────────────────────────────────
DIVIDER      = "-" * 58
THIN_DIVIDER = "-" * 58

def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def print_header():
    print(DIVIDER)
    print("  SERVO CONTROL  --  Raspberry Pi 4B+  |  Dual PCA9685")
    print(DIVIDER)

def print_main_menu():
    clear()
    print_header()
    print(f"  {'No':>3}  {'Servo Name':<22}  {'TCA':>3}  {'PCA':>3}  "
          f"{'INI':>4}  {'MAX':>4}  {'MIN':>4}")
    print(THIN_DIVIDER)

    prev_tca = None
    for num, name, tca, pca, ini, mx, mn in SERVOS:
        if prev_tca is not None and tca != prev_tca:
            print()
        label = "BODY" if tca == BODY_TCA_CHANNEL else "LEGS"
        if prev_tca != tca:
            print(f"  -- {label} servos --")
        prev_tca = tca
        print(f"  {num:>3}. {name:<22}  {tca:>3}  {pca:>3}  "
              f"{ini:>4}   {mx:>4}   {mn:>4}")

    print(DIVIDER)
    print("  Type a servo number to select it, or 'q' to quit.")
    print(DIVIDER)

def print_servo_menu(servo: tuple):
    num, name, tca, pca, ini, mx, mn = servo
    clear()
    print_header()
    group = "BODY (TCA 0)" if tca == BODY_TCA_CHANNEL else "LEGS (TCA 5)"
    print(f"  Selected : #{num} - {name}")
    print(f"  Group    : {group}   PCA channel {pca}")
    print(THIN_DIVIDER)
    print(f"  {'INITIAL':>8} : {ini} deg")
    print(f"  {'MAX':>8} : {mx} deg")
    print(f"  {'MIN':>8} : {mn} deg")
    print(DIVIDER)
    print("  Commands:  ini   max   min")
    print("  Navigate:  Ctrl+B then M  ->  back to main menu")
    print(DIVIDER)

# ──────────────────────────────────────────────
#  SERVO CONTROL LOOP
# ──────────────────────────────────────────────
def servo_loop(servo: tuple):
    num, name, tca, pca, ini, mx, mn = servo
    while True:
        print_servo_menu(servo)
        cmd = read_line_with_ctrlb(f"  [{name}] > ")

        if cmd == '__MENU__':
            return  # back to main menu

        if cmd in ('ini', 'initial'):
            print(f"\n  Moving {name} to INITIAL ({ini} deg) ...")
            move_servo(tca, pca, ini)
            print(f"  Done.")
            time.sleep(0.8)

        elif cmd == 'max':
            print(f"\n  Moving {name} to MAX ({mx} deg) ...")
            move_servo(tca, pca, mx)
            print(f"  Done.")
            time.sleep(0.8)

        elif cmd == 'min':
            print(f"\n  Moving {name} to MIN ({mn} deg) ...")
            move_servo(tca, pca, mn)
            print(f"  Done.")
            time.sleep(0.8)

        elif cmd in ('m', 'menu', 'back', 'b'):
            return  # also allow typing 'menu' or 'back'

        elif cmd in ('q', 'quit', 'exit'):
            clear()
            print("  Goodbye.")
            sys.exit(0)

        elif cmd == '':
            pass   # just re-draw

        else:
            print(f"\n  Unknown command '{cmd}'.  Use: ini | max | min")
            time.sleep(1.0)

# ──────────────────────────────────────────────
#  MAIN MENU LOOP
# ──────────────────────────────────────────────
def main():
    try:
        while True:
            print_main_menu()
            raw = read_line_with_ctrlb("  Select servo number > ")

            if raw == '__MENU__':
                continue   # already on the menu

            if raw in ('q', 'quit', 'exit'):
                clear()
                print("  Goodbye.")
                sys.exit(0)

            if raw == '':
                continue

            try:
                num = int(raw)
            except ValueError:
                print(f"\n  Please enter a number (1-{len(SERVOS)}).")
                time.sleep(1.0)
                continue

            if num not in SERVO_MAP:
                print(f"\n  No servo #{num}.  Valid range: 1-{len(SERVOS)}.")
                time.sleep(1.0)
                continue

            servo_loop(SERVO_MAP[num])

    except KeyboardInterrupt:
        clear()
        print("  Interrupted. Goodbye.")
        sys.exit(0)

if __name__ == "__main__":
    main()
