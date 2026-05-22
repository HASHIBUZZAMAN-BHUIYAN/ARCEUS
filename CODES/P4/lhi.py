"""
LEFT HAND HI expression_test.py - ARCEUS Expression Movement Tester
Hardware: Raspberry Pi 4B+ -> TCA9548A -> 2x PCA9685

"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_bus_device.i2c_device import I2CDevice

# =============================================================================
#  HARDWARE CONFIG
# =============================================================================
BODY_TCA_CHANNEL = 0
LEG_TCA_CHANNEL  = 5
TCA_ADDR         = 0x70

# -- Body PCA channel numbers -------------------------------------------------
NECK_Y_CH          = 0
NECK_X_CH          = 11
CHEST_ARM_LEFT_CH  = 12
SHOULDER_LEFT_CH   = 3
BICEP_LEFT_CH      = 4
ELBOW_LEFT_CH      = 7
GRIPPER_LEFT_CH    = 8
SPINAL_X_CH        = 9

# -- Leg PCA channel numbers (initialized once, never changed) ----------------
HIP_YAW_LEFT_CH      = 11
HIP_YAW_RIGHT_CH     = 0
HIP_ROLL_LEFT_CH     = 10
HIP_ROLL_RIGHT_CH    = 1
HIP_PITCH_LEFT_CH    = 9
HIP_PITCH_RIGHT_CH   = 2
KNEE_LEFT_CH         = 8
KNEE_RIGHT_CH        = 3
ANKLE_PITCH_LEFT_CH  = 7
ANKLE_PITCH_RIGHT_CH = 4
ANKLE_ROLL_LEFT_CH   = 6
ANKLE_ROLL_RIGHT_CH  = 5

# =============================================================================
#  INITIAL ANGLES  (from ANG_DATA.xlsx)
#  These are the resting positions every expression starts and ends at.
# =============================================================================
BODY_INITIAL = {
    NECK_Y_CH:         105,
    NECK_X_CH:          95,
    CHEST_ARM_LEFT_CH: 150,
    SHOULDER_LEFT_CH:   30,
    BICEP_LEFT_CH:     100,
    ELBOW_LEFT_CH:      95,
    GRIPPER_LEFT_CH:    95,
    SPINAL_X_CH:       102,
}

LEG_INITIAL = {
    HIP_YAW_LEFT_CH:      100,
    HIP_YAW_RIGHT_CH:     100,
    HIP_ROLL_LEFT_CH:     105,
    HIP_ROLL_RIGHT_CH:    105,
    HIP_PITCH_LEFT_CH:     95,
    HIP_PITCH_RIGHT_CH:    95,
    KNEE_LEFT_CH:         145,
    KNEE_RIGHT_CH:         65,
    ANKLE_PITCH_LEFT_CH:  130,
    ANKLE_PITCH_RIGHT_CH:  65,
    ANKLE_ROLL_LEFT_CH:   100,
    ANKLE_ROLL_RIGHT_CH:  100,
}

# =============================================================================
#  EXPRESSION POSITIONS
#  Each position only lists the channels that differ from BODY_INITIAL.
#  Unlisted channels stay at their BODY_INITIAL value.
# =============================================================================

# -----------------------------------------------------------------------------
#  HI  (left arm wave)
#      Pattern: initial -> high -> loop 3x[reverse <-> high] -> initial
# -----------------------------------------------------------------------------
HI_POSITIONS = {

    "high": {
        NECK_Y_CH:         105,   # (head tilt)
        NECK_X_CH:          95,   # (head turn)
        CHEST_ARM_LEFT_CH: 150,   # (chest arm raise)
        SHOULDER_LEFT_CH:  140,   # (shoulder up)
        BICEP_LEFT_CH:      20,   # (bicep angle)
        ELBOW_LEFT_CH:      40,   # (elbow bend)
        GRIPPER_LEFT_CH:    40,   # (gripper)
    },

    "reverse": {
        NECK_Y_CH:         105,   
        NECK_X_CH:          95,   
        CHEST_ARM_LEFT_CH: 150,   
        SHOULDER_LEFT_CH:  140,   
        BICEP_LEFT_CH:      20,   
        ELBOW_LEFT_CH:     155,   # (elbow swings other way)
        GRIPPER_LEFT_CH:    95,   
    },
}

# -- Timing for Hi (seconds between each position move) ----------------------
HI_SPEED = 0.6    # <-- EDIT  seconds per move (lower = faster wave)

# -- Expression step sequence -------------------------------------------------
#   move("name")            -> go to that position once
#   loop(N, [...steps...])  -> repeat those steps N times
HI_SEQUENCE = [
    ("move",  "high"),
    ("loop",  3, [
        ("move", "reverse"),
        ("move", "high"),
    ]),
]

# -- Expression registry (add new ones here after creating them above) --------
EXPRESSIONS = {
    "hi":      (HI_POSITIONS,      HI_SPEED,      HI_SEQUENCE),
}

# =============================================================================
#  HARDWARE HELPERS
# =============================================================================
i2c = busio.I2C(board.SCL, board.SDA)

def select_tca_channel(channel: int):
    if 0 <= channel <= 7:
        with I2CDevice(i2c, TCA_ADDR) as dev:
            dev.write(bytes([1 << channel]))

def calculate_duty(angle: float) -> int:
    min_pulse = 500
    max_pulse = 2500
    pulse = min_pulse + (max_pulse - min_pulse) * (angle / 180.0)
    return int((pulse / 1_000_000.0) * 50.0 * 65535)

def set_servos(tca_channel: int, angles: dict, delay_between: float = 0.0):
    """Send all angles to the PCA9685 on the given TCA channel."""
    select_tca_channel(tca_channel)
    time.sleep(0.01)
    pca = PCA9685(i2c)
    pca.frequency = 50
    for ch, angle in angles.items():
        pca.channels[ch].duty_cycle = calculate_duty(angle)
        if delay_between > 0:
            time.sleep(delay_between)

# =============================================================================
#  STARTUP
# =============================================================================
def initialize_all():
    """Move body and legs to initial positions at startup."""
    print("  Initializing legs ...")
    set_servos(LEG_TCA_CHANNEL, LEG_INITIAL)
    time.sleep(0.5)
    print("  Initializing body ...")
    set_servos(BODY_TCA_CHANNEL, BODY_INITIAL)
    time.sleep(0.5)
    print("  Ready.\n")

# =============================================================================
#  EXPRESSION RUNNER
# =============================================================================
def build_full_position(positions: dict, name: str) -> dict:
    """
    Merge BODY_INITIAL with the named position.
    BODY_INITIAL provides defaults; the expression position overrides only
    the channels it lists. Legs are never included here.
    """
    full = dict(BODY_INITIAL)        # start from initial
    full.update(positions[name])     # apply only the changed channels
    return full

def execute_move(positions: dict, name: str, speed: float):
    """Resolve and send a single named position to the body PCA."""
    full = build_full_position(positions, name)
    print(f"    -> position '{name}'")
    set_servos(BODY_TCA_CHANNEL, full)
    time.sleep(speed)

def run_steps(steps: list, positions: dict, speed: float):
    """Recursively execute a list of steps (supports nested loops)."""
    for step in steps:
        kind = step[0]

        if kind == "move":
            _, pos_name = step
            execute_move(positions, pos_name, speed)

        elif kind == "loop":
            _, count, inner_steps = step
            print(f"    [loop x{count}]")
            for i in range(count):
                print(f"      iteration {i + 1}/{count}")
                run_steps(inner_steps, positions, speed)

        else:
            print(f"    WARNING: unknown step type '{kind}' - skipping")

def run_expression(name: str):
    """Run a full expression: initial -> sequence -> initial."""
    if name not in EXPRESSIONS:
        print(f"  Expression '{name}' not found.")
        return

    positions, speed, sequence = EXPRESSIONS[name]

    print(f"\n  Running expression: {name.upper()}")
    print(f"  Speed: {speed}s per move")
    print()

    # Step 1: go to initial
    print("  [1] Going to initial position ...")
    set_servos(BODY_TCA_CHANNEL, BODY_INITIAL)
    time.sleep(speed)

    # Step 2: run the sequence
    print("  [2] Running sequence ...")
    run_steps(sequence, positions, speed)

    # Step 3: return to initial
    print("  [3] Returning to initial position ...")
    set_servos(BODY_TCA_CHANNEL, BODY_INITIAL)
    time.sleep(speed)

    print(f"\n  Done: {name.upper()}\n")

# =============================================================================
#  MENU
# =============================================================================
def print_menu():
    print("=" * 40)
    print("  EXPRESSION TEST MENU")
    print("=" * 40)
    for i, name in enumerate(EXPRESSIONS, 1):
        print(f"  {i}. {name.upper()}")
    print("  0. Quit")
    print("-" * 40)

def main():
    print("\n  Expression Movement Tester - LEFT ARM ONLY\n")
    initialize_all()

    name_list = list(EXPRESSIONS.keys())

    while True:
        print_menu()
        raw = input("  Select > ").strip().lower()

        if raw in ('0', 'q', 'quit'):
            print("  Exiting.")
            break

        # Accept number or name
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(name_list):
                raw = name_list[idx]
            else:
                print(f"  Invalid number. Enter 1-{len(name_list)}.\n")
                continue

        if raw in EXPRESSIONS:
            run_expression(raw)
        else:
            print(f"  Unknown expression '{raw}'.\n")

if __name__ == "__main__":
    main()
