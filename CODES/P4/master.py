"""
ARCEUS Expression Movement Tester
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
NECK_Y_CH           = 0
NECK_X_CH           = 11
CHEST_ARM_LEFT_CH   = 12
CHEST_ARM_RIGHT_CH  = 10
SHOULDER_LEFT_CH    = 3
SHOULDER_RIGHT_CH   = 1
BICEP_LEFT_CH       = 4
BICEP_RIGHT_CH      = 2
ELBOW_LEFT_CH       = 7
ELBOW_RIGHT_CH      = 5
GRIPPER_LEFT_CH     = 8
GRIPPER_RIGHT_CH    = 6
SPINAL_X_CH         = 9

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
#  INITIAL ANGLES
# =============================================================================
BODY_INITIAL = {
    NECK_Y_CH:          105,
    NECK_X_CH:           95,
    CHEST_ARM_LEFT_CH:  150,
    CHEST_ARM_RIGHT_CH:  40,
    SHOULDER_LEFT_CH:    30,
    SHOULDER_RIGHT_CH:  150,
    BICEP_LEFT_CH:      100,
    BICEP_RIGHT_CH:     100,
    ELBOW_LEFT_CH:       95,
    ELBOW_RIGHT_CH:      95,
    GRIPPER_LEFT_CH:     95,
    GRIPPER_RIGHT_CH:    95,
    SPINAL_X_CH:        102,
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
#  1. HI_LEFT  -  Left arm waves
#     Pattern: initial -> high -> loop 3x[reverse <-> high] -> initial
# =============================================================================
HI_POSITIONS = {

    "high": {
        NECK_Y_CH:          105,   # head tilt
        NECK_X_CH:           50,   # head turn
        CHEST_ARM_LEFT_CH:  150,   
        SHOULDER_LEFT_CH:   140,   # arm raised
        BICEP_LEFT_CH:       20,  
        ELBOW_LEFT_CH:       40,   # bent up
        GRIPPER_LEFT_CH:     40,   
    },

    "reverse": {
        NECK_Y_CH:          105,   
        NECK_X_CH:          140,   
        CHEST_ARM_LEFT_CH:  150,   
        SHOULDER_LEFT_CH:   140,   
        BICEP_LEFT_CH:       20,  
        ELBOW_LEFT_CH:      155,   # elbow swings other way
        GRIPPER_LEFT_CH:     95,   
    },
}

HI_SPEED = 0.6   # <-- EDIT

HI_SEQUENCE = [
    ("move", "high"),
    ("loop", 3, [
        ("move", "reverse"),
        ("move", "high"),
    ]),
]


# =============================================================================
#  2. HI_RIGHT  -  Right arm waves  (mirror of HI_LEFT)
#     Pattern: initial -> high -> loop 3x[reverse <-> high] -> initial
# =============================================================================
HI_RIGHT_POSITIONS = {

    "high": {
        NECK_Y_CH:           105,   
        NECK_X_CH:           140,  
        CHEST_ARM_RIGHT_CH:   40,   
        SHOULDER_RIGHT_CH:    40,   # arm raised 
        BICEP_RIGHT_CH:      180,  
        ELBOW_RIGHT_CH:      155,  
        GRIPPER_RIGHT_CH:     40,   
    },

    "reverse": {
        NECK_Y_CH:           105,   
        NECK_X_CH:            50,   
        CHEST_ARM_RIGHT_CH:   40,   
        SHOULDER_RIGHT_CH:    40,   
        BICEP_RIGHT_CH:      180,   
        ELBOW_RIGHT_CH:       40,   # elbow swings other way
        GRIPPER_RIGHT_CH:     95,  
    },
}

HI_RIGHT_SPEED = 0.6   # <-- EDIT

HI_RIGHT_SEQUENCE = [
    ("move", "high"),
    ("loop", 3, [
        ("move", "reverse"),
        ("move", "high"),
    ]),
]


# =============================================================================
#  3. WELCOME  -  Both arms open wide, then lower, repeated once
#     Pattern: initial -> arms_open -> arms_lower -> arms_open -> initial
# =============================================================================
WELCOME_POSITIONS = {

    "arms_open": {
        NECK_Y_CH:           105,   # head up
        NECK_X_CH:            95,   # center
        CHEST_ARM_LEFT_CH:   150,  
        CHEST_ARM_RIGHT_CH:   40,   
        SHOULDER_LEFT_CH:    140,   # left arm out to side
        SHOULDER_RIGHT_CH:    40,   # right arm out to side
        BICEP_LEFT_CH:        20,   
        BICEP_RIGHT_CH:      180,   
        ELBOW_LEFT_CH:        40,   # slight bend
        ELBOW_RIGHT_CH:      155,   
        GRIPPER_LEFT_CH:      40,   # open hand
        GRIPPER_RIGHT_CH:     40,   
        SPINAL_X_CH:         102,   
    },

    "arms_lower": {
        NECK_Y_CH:          105,  
        NECK_X_CH:           95,   
        CHEST_ARM_LEFT_CH:  150,   
        CHEST_ARM_RIGHT_CH:  40,   
        SHOULDER_LEFT_CH:   140,   # arms lowered
        SHOULDER_RIGHT_CH:   40,   
        BICEP_LEFT_CH:       20,   
        BICEP_RIGHT_CH:     180,   
        ELBOW_LEFT_CH:      155,   
        ELBOW_RIGHT_CH:      40,   
        GRIPPER_LEFT_CH:     95,   
        GRIPPER_RIGHT_CH:    95,   
        SPINAL_X_CH:        102,   
    },
}

WELCOME_SPEED = 0.8   # <-- EDIT

WELCOME_SEQUENCE = [
    ("move", "arms_open"),
    ("loop", 3, [
        ("move", "arms_lower"),
        ("move", "arms_open"),
    ]),
]


# =============================================================================
#  YES  -  Head nods, both arms raise and lower with it
#     Pattern: initial -> head_down -> loop 3x[head_up <-> head_down] -> initial
# =============================================================================
YES_POSITIONS = {

    "head_up": {
        NECK_Y_CH:           90,   # head up
        NECK_X_CH:           95,   # center
        CHEST_ARM_RIGHT_CH:  70,
        SHOULDER_RIGHT_CH:   90,   # right arm out
        BICEP_RIGHT_CH:     100,
        ELBOW_RIGHT_CH:     155,   # elbow raised (mirrored)
        GRIPPER_RIGHT_CH:    95,
        SPINAL_X_CH:        102,
    },

    "head_down": {
        NECK_Y_CH:          120,   # head down
        NECK_X_CH:           95,   # center
        CHEST_ARM_RIGHT_CH:  70,
        SHOULDER_RIGHT_CH:   90,
        BICEP_RIGHT_CH:     100,
        ELBOW_RIGHT_CH:      95,   # elbow lowered (back to initial)
        GRIPPER_RIGHT_CH:    95,
        SPINAL_X_CH:        102,
    },
}

YES_SPEED = 0.5   # <-- EDIT

YES_SEQUENCE = [
    ("move", "head_up"),
    ("loop", 3, [
        ("move", "head_down"),
        ("move", "head_up"),
    ]),
]


# =============================================================================
#  4. NO  -  Head turns left and right
#     Pattern: initial -> head_left -> loop 3x[head_right <-> head_left] -> initial
# =============================================================================

NO_POSITIONS = {

    "head_left": {
        NECK_Y_CH:          105,   # level
        NECK_X_CH:          140,   # turn left
        CHEST_ARM_LEFT_CH:   70,
        CHEST_ARM_RIGHT_CH: 120,
        SHOULDER_LEFT_CH:    30,
        SHOULDER_RIGHT_CH:  150,
        BICEP_LEFT_CH:      150,
        BICEP_RIGHT_CH:      50,
        ELBOW_LEFT_CH:       60,   # left elbow pulls back
        ELBOW_RIGHT_CH:     130,   # right elbow extends 
        GRIPPER_LEFT_CH:     95,
        GRIPPER_RIGHT_CH:    95,
        SPINAL_X_CH:        102,
    },

    "head_right": {
        NECK_Y_CH:          105,   # level
        NECK_X_CH:           50,   # turn right
        CHEST_ARM_LEFT_CH:   70,
        CHEST_ARM_RIGHT_CH: 120,
        SHOULDER_LEFT_CH:    30,
        SHOULDER_RIGHT_CH:  150,
        BICEP_LEFT_CH:      150,
        BICEP_RIGHT_CH:      50,
        ELBOW_LEFT_CH:      110,   # left elbow extends 
        ELBOW_RIGHT_CH:      80,   # right elbow pulls back
        GRIPPER_LEFT_CH:     40,
        GRIPPER_RIGHT_CH:    40,
        SPINAL_X_CH:        102,
    },
}

NO_SPEED = 0.5   # <-- EDIT

NO_SEQUENCE = [
    ("move", "head_left"),
    ("loop", 3, [
        ("move", "head_right"),
        ("move", "head_left"),
    ]),
]

# =============================================================================
#  5. EXPLAIN
#     Pattern:
#       left_side (head left + left arm) -> loop 2x[left_reverse <-> left_side]
#       right_side (head right + right arm) -> loop 2x[right_reverse <-> right_side]
#       center_a (head center + both arms) -> loop 2x[center_b <-> center_a]
# =============================================================================
EXPLAIN_POSITIONS = {

    # -- left side ------------------------------------------------------------
    "left_side": {
        NECK_Y_CH:          105,   
        NECK_X_CH:          135,   # head turns left
        CHEST_ARM_LEFT_CH:  120,   
        SHOULDER_LEFT_CH:    90,   # left arm gestures
        BICEP_LEFT_CH:      100,   
        ELBOW_LEFT_CH:       35,   # elbow position
        GRIPPER_LEFT_CH:     95,   # open hand
        SPINAL_X_CH:        102,   
    },

    "left_reverse": {
        NECK_Y_CH:          105,   
        NECK_X_CH:          135,   # head still left
        CHEST_ARM_LEFT_CH:  120,   
        SHOULDER_LEFT_CH:    90,   
        BICEP_LEFT_CH:      100,   
        ELBOW_LEFT_CH:       95,   # elbow swings to reverse
        GRIPPER_LEFT_CH:     95,   
        SPINAL_X_CH:        102,   
    },

    # -- right side -----------------------------------------------------------
    "right_side": {
        NECK_Y_CH:          105,   
        NECK_X_CH:           55,   # head turns right
        CHEST_ARM_RIGHT_CH:  70,   
        SHOULDER_RIGHT_CH:   90,   # right arm gestures
        BICEP_RIGHT_CH:     100,  
        ELBOW_RIGHT_CH:     155,   # elbow position (mirrored)
        GRIPPER_RIGHT_CH:    95,   # open hand
        SPINAL_X_CH:        102,   
    },

    "right_reverse": {
        NECK_Y_CH:          105,   
        NECK_X_CH:           55,   # head still right
        CHEST_ARM_RIGHT_CH:  70,   
        SHOULDER_RIGHT_CH:   90,   
        BICEP_RIGHT_CH:     100,   
        ELBOW_RIGHT_CH:      95,   # elbow swings to reverse
        GRIPPER_RIGHT_CH:    95,   
        SPINAL_X_CH:        102,  
    },

    # -- center : both arms moving --------------------------------------------
    "center_a": {
        NECK_Y_CH:          105,   
        NECK_X_CH:           95,   # head center
        CHEST_ARM_LEFT_CH:  120,   
        CHEST_ARM_RIGHT_CH:  70,   
        SHOULDER_LEFT_CH:    90,   # both arms out
        SHOULDER_RIGHT_CH:   90,   
        BICEP_LEFT_CH:      100,   
        BICEP_RIGHT_CH:     100,   
        ELBOW_LEFT_CH:       35,   
        ELBOW_RIGHT_CH:     155,   
        GRIPPER_LEFT_CH:     95,   
        GRIPPER_RIGHT_CH:    95,   
        SPINAL_X_CH:        102,   
    },

    "center_b": {
        NECK_Y_CH:          105,  
        NECK_X_CH:           95,   # head center
        CHEST_ARM_LEFT_CH:  120,   
        CHEST_ARM_RIGHT_CH:  70,   
        SHOULDER_LEFT_CH:    90,   
        SHOULDER_RIGHT_CH:   90,   
        BICEP_LEFT_CH:      100,   
        BICEP_RIGHT_CH:     100,   
        ELBOW_LEFT_CH:       95,   # both elbows swap
        ELBOW_RIGHT_CH:      95,   
        GRIPPER_LEFT_CH:     95,   
        GRIPPER_RIGHT_CH:    95,   
        SPINAL_X_CH:        102,   
    },
}

EXPLAIN_SPEED = 0.6   # <-- EDIT

EXPLAIN_SEQUENCE = [
    # left side with elbow loop
    ("move", "left_side"),
    ("loop", 2, [
        ("move", "left_reverse"),
        ("move", "left_side"),
    ]),
    # right side with elbow loop
    ("move", "right_side"),
    ("loop", 2, [
        ("move", "right_reverse"),
        ("move", "right_side"),
    ]),
    # center with both arms
    ("move", "center_a"),
    ("loop", 2, [
        ("move", "center_b"),
        ("move", "center_a"),
    ]),
]




# =============================================================================
#  7. AUDIENCE
#     Pattern:
#       left_think (left hand to head + head down-left)
#       -> loop 2x [left_up <-> left_think]
#       -> center
#       -> right_think (right hand to head + head down-right)
#       -> loop 2x [right_up <-> right_think]
#       -> initial (automatic)
# =============================================================================
AUDIENCE_POSITIONS = {

    # -- left side : left hand toward chin, head down-left --------------------
    "left_think": {
        NECK_Y_CH:          120,   # head down
        NECK_X_CH:          135,   # head turns left
        CHEST_ARM_LEFT_CH:  150,   # forward from initial 150
        SHOULDER_LEFT_CH:   140,   # raised toward chin
        BICEP_LEFT_CH:       20,   # rotated to angle forearm toward face
        ELBOW_LEFT_CH:       40,   # sharply bent to bring hand toward chin
        GRIPPER_LEFT_CH:     95,   # closed
    },

    "left_up": {
        NECK_Y_CH:           90,   # head up  
        NECK_X_CH:          135,   # still looking left
        CHEST_ARM_LEFT_CH:  150,   # hand stays in place
        SHOULDER_LEFT_CH:   140,
        BICEP_LEFT_CH:       20,
        ELBOW_LEFT_CH:       40,   # elbow at high position
        GRIPPER_LEFT_CH:     95,
    },

    "left_elbow_rev": {
        NECK_Y_CH:           90,   # head up
        NECK_X_CH:          135,   # still looking left
        CHEST_ARM_LEFT_CH:  150,   # hand stays in place
        SHOULDER_LEFT_CH:   140,
        BICEP_LEFT_CH:       20,
        ELBOW_LEFT_CH:      155,   # elbow swings to reverse 
        GRIPPER_LEFT_CH:     95,
    },

    # -- center reset : all channels back to initial --------------------------
    "center": {
        NECK_Y_CH:          105,   # initial
        NECK_X_CH:           95,   # initial 
        CHEST_ARM_LEFT_CH:  150,   # initial
        SHOULDER_LEFT_CH:    30,   # initial
        BICEP_LEFT_CH:      100,   # initial
        ELBOW_LEFT_CH:       95,   # initial
        GRIPPER_LEFT_CH:     95,   # initial
        CHEST_ARM_RIGHT_CH:  40,   # initial
        SHOULDER_RIGHT_CH:  150,   # initial
        BICEP_RIGHT_CH:     100,   # initial
        ELBOW_RIGHT_CH:      95,   # initial
        GRIPPER_RIGHT_CH:    95,   # initial
    },

    # -- right side : right hand toward chin, head down-right -----------------
    "right_think": {
        NECK_Y_CH:          120,   # head down 
        NECK_X_CH:           55,   # head turns right 
        CHEST_ARM_RIGHT_CH:  40,   
        SHOULDER_RIGHT_CH:   40,   
        BICEP_RIGHT_CH:     180,   
        ELBOW_RIGHT_CH:     155,   # elbow at high position
        GRIPPER_RIGHT_CH:    95,   # closed
    },

    "right_up": {
        NECK_Y_CH:           90,   # head up  
        NECK_X_CH:           55,   # still looking right
        CHEST_ARM_RIGHT_CH:  40,   # hand stays in place
        SHOULDER_RIGHT_CH:   40,
        BICEP_RIGHT_CH:     180,
        ELBOW_RIGHT_CH:     155,   # elbow at high position
        GRIPPER_RIGHT_CH:    95,
    },

    "right_elbow_rev": {
        NECK_Y_CH:           90,   # head up
        NECK_X_CH:           55,   # still looking right
        CHEST_ARM_RIGHT_CH:  40,   # hand stays in place
        SHOULDER_RIGHT_CH:   40,
        BICEP_RIGHT_CH:     180,
        ELBOW_RIGHT_CH:      40,   # elbow swings to reverse
        GRIPPER_RIGHT_CH:    95,
    },
}

AUDIENCE_SPEED = 0.8   # SPEED

AUDIENCE_SEQUENCE = [
    ("move", "left_think"),
    ("loop", 2, [
        ("move", "left_up"),
        ("move", "left_elbow_rev"),
        ("move", "left_think"),
    ]),
    ("move", "center"),
    ("move", "right_think"),
    ("loop", 2, [
        ("move", "right_up"),
        ("move", "right_elbow_rev"),
        ("move", "right_think"),
    ]),
]






# =============================================================================
#  10. BOW  -  Spinal leans forward, head tilts down, holds, returns
#      Pattern: initial -> bow_down -> hold_bow -> initial
# =============================================================================
BOW_POSITIONS = {

    "bow_down": {
        NECK_Y_CH:          140,   # <-- EDIT  head tilts down
        NECK_X_CH:           95,   # <-- EDIT  center
        CHEST_ARM_LEFT_CH:  130,   
        CHEST_ARM_RIGHT_CH:  90,   
        SHOULDER_LEFT_CH:    30,   # <-- EDIT  arms stay at sides
        SHOULDER_RIGHT_CH:  150,   
        BICEP_LEFT_CH:      180,   
        BICEP_RIGHT_CH:       0,   
        ELBOW_LEFT_CH:       60,   
        ELBOW_RIGHT_CH:     120,   
        GRIPPER_LEFT_CH:     95,   
        GRIPPER_RIGHT_CH:    95,   
        SPINAL_X_CH:        102    # spinal leans forward
    }
}

BOW_SPEED = 6   # speed to reach bow_down position

BOW_SEQUENCE = [
    ("move", "bow_down"),
    ("wait", 2),        # seconds to hold the bow
]


# =============================================================================
#  EXPRESSION REGISTRY
# =============================================================================
EXPRESSIONS = {
    "hi_left":  (HI_POSITIONS,       HI_SPEED,       HI_SEQUENCE),
    "hi_right": (HI_RIGHT_POSITIONS, HI_RIGHT_SPEED, HI_RIGHT_SEQUENCE),
    "welcome":  (WELCOME_POSITIONS,  WELCOME_SPEED,  WELCOME_SEQUENCE),
    "yes":      (YES_POSITIONS,      YES_SPEED,      YES_SEQUENCE),
    "no":       (NO_POSITIONS,       NO_SPEED,       NO_SEQUENCE),
    "explain":  (EXPLAIN_POSITIONS,  EXPLAIN_SPEED,  EXPLAIN_SEQUENCE),
    "audience": (AUDIENCE_POSITIONS, AUDIENCE_SPEED, AUDIENCE_SEQUENCE),
    "bow":      (BOW_POSITIONS,      BOW_SPEED,      BOW_SEQUENCE),
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

def set_servos(tca_channel: int, angles: dict):
    """Send all angles to the PCA9685 on the given TCA channel."""
    select_tca_channel(tca_channel)
    time.sleep(0.01)
    pca = PCA9685(i2c)
    pca.frequency = 50
    for ch, angle in angles.items():
        pca.channels[ch].duty_cycle = calculate_duty(angle)


# =============================================================================
#  STARTUP
# =============================================================================
def initialize_all():
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
    Start from BODY_INITIAL, then apply only the channels listed
    in the named position. Anything not listed stays at initial.
    """
    full = dict(BODY_INITIAL)
    full.update(positions[name])
    return full

def execute_move(positions: dict, name: str, speed: float):
    full = build_full_position(positions, name)
    print(f"    -> '{name}'")
    set_servos(BODY_TCA_CHANNEL, full)
    time.sleep(speed)

def run_steps(steps: list, positions: dict, speed: float):
    """Recursively execute steps. Supports nested loops."""
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
        elif kind == "wait":
            _, seconds = step
            print(f"    [holding {seconds}s ...]")
            time.sleep(seconds)
        else:
            print(f"    WARNING: unknown step '{kind}' - skipping")

def run_expression(name: str):
    if name not in EXPRESSIONS:
        print(f"  Expression '{name}' not found.")
        return

    positions, speed, sequence = EXPRESSIONS[name]

    print(f"\n  [{name.upper()}]  speed = {speed}s per move")
    print()

    print("  Running sequence ...")
    run_steps(sequence, positions, speed)

    print("  Returning to initial ...")
    set_servos(BODY_TCA_CHANNEL, BODY_INITIAL)
    time.sleep(speed)

    print(f"  Done: {name.upper()}\n")


# =============================================================================
#  MENU
# =============================================================================
def print_menu():
    print("=" * 42)
    print("  EXPRESSION TEST MENU")
    print("=" * 42)
    for i, name in enumerate(EXPRESSIONS, 1):
        print(f"  {i:>2}. {name.upper()}")
    print("   0. Quit")
    print("-" * 42)

def main():
    print("\n  Expression Movement Tester\n")
    initialize_all()

    name_list = list(EXPRESSIONS.keys())

    while True:
        print_menu()
        raw = input("  Select > ").strip().lower()

        if raw in ('0', 'q', 'quit'):
            print("  Exiting.")
            break

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
