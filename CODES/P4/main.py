"""
main.py  -  Arceus Robot Unified Controller
==========================================
"""

import os
import math
import time
import threading

from flask import Flask, jsonify, request, render_template, Response
from flask_socketio import SocketIO, emit

import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_bus_device.i2c_device import I2CDevice
from smbus2 import SMBus
from luma.core.interface.serial import i2c as luma_i2c
from luma.oled.device import sh1106
from PIL import Image, ImageOps

# =============================================================================
#  HARDWARE CONFIG
# =============================================================================
TCA_ADDR         = 0x70
BODY_TCA_CHANNEL = 0
LEG_TCA_CHANNEL  = 5

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
    HIP_ROLL_RIGHT_CH:    100,
    HIP_PITCH_LEFT_CH:     80,
    HIP_PITCH_RIGHT_CH:   105,
    KNEE_LEFT_CH:         145,
    KNEE_RIGHT_CH:         65,
    ANKLE_PITCH_LEFT_CH:  130,
    ANKLE_PITCH_RIGHT_CH:  65,
    ANKLE_ROLL_LEFT_CH:   100,
    ANKLE_ROLL_RIGHT_CH:   95,
}

# =============================================================================
#  GAIT SYSTEM  (from controller.py)
# =============================================================================

# ── Servo config table ────────────────────────────────────────────────────────
SERVO = {
    "neck_y":          {"tca": BODY_TCA_CHANNEL, "pca":  0, "ini": 105, "mn":  60, "mx": 150, "sign": +1, "scale":  40},
    "neck_x":          {"tca": BODY_TCA_CHANNEL, "pca": 11, "ini":  95, "mn":  10, "mx": 180, "sign": +1, "scale":  80},
    "chest_arm_L":     {"tca": BODY_TCA_CHANNEL, "pca": 12, "ini": 150, "mn":  50, "mx": 180, "sign": -1, "scale":  50},
    "chest_arm_R":     {"tca": BODY_TCA_CHANNEL, "pca": 10, "ini":  45, "mn":  10, "mx": 145, "sign": +1, "scale":  50},
    "shoulder_L":      {"tca": BODY_TCA_CHANNEL, "pca":  3, "ini":  30, "mn":  10, "mx": 180, "sign": +1, "scale":  30},
    "shoulder_R":      {"tca": BODY_TCA_CHANNEL, "pca":  1, "ini": 150, "mn":   0, "mx": 170, "sign": -1, "scale":  30},
    "bicep_L":         {"tca": BODY_TCA_CHANNEL, "pca":  4, "ini": 100, "mn":  40, "mx": 160, "sign": +1, "scale":  50},
    "bicep_R":         {"tca": BODY_TCA_CHANNEL, "pca":  2, "ini":  95, "mn":  60, "mx": 140, "sign": -1, "scale":  50},
    "elbow_L":         {"tca": BODY_TCA_CHANNEL, "pca":  7, "ini":  95, "mn":  40, "mx": 155, "sign": +1, "scale":  50},
    "elbow_R":         {"tca": BODY_TCA_CHANNEL, "pca":  5, "ini":  95, "mn":  40, "mx": 155, "sign": -1, "scale":  50},
    "gripper_L":       {"tca": BODY_TCA_CHANNEL, "pca":  8, "ini":  95, "mn":  40, "mx":  95, "sign": +1, "scale":  30},
    "gripper_R":       {"tca": BODY_TCA_CHANNEL, "pca":  6, "ini":  95, "mn":  40, "mx":  95, "sign": -1, "scale":  30},
    "spine":           {"tca": BODY_TCA_CHANNEL, "pca":  9, "ini": 105, "mn":  94, "mx": 110, "sign": -1, "scale":  30},
    "hip_yaw_L":       {"tca": LEG_TCA_CHANNEL,  "pca": 11, "ini": 100, "mn":  80, "mx": 120, "sign": -1, "scale":  80},
    "hip_yaw_R":       {"tca": LEG_TCA_CHANNEL,  "pca":  0, "ini": 100, "mn":  80, "mx": 120, "sign": -1, "scale":  80},
    "hip_roll_L":      {"tca": LEG_TCA_CHANNEL,  "pca": 10, "ini": 105, "mn":  95, "mx": 115, "sign": -1, "scale":  80},
    "hip_roll_R":      {"tca": LEG_TCA_CHANNEL,  "pca":  1, "ini": 100, "mn":  95, "mx": 115, "sign": -1, "scale":  80},
    "hip_pitch_L":     {"tca": LEG_TCA_CHANNEL,  "pca":  9, "ini":  80, "mn":  85, "mx": 105, "sign": -1, "scale":  40},
    "hip_pitch_R":     {"tca": LEG_TCA_CHANNEL,  "pca":  2, "ini": 105, "mn":  85, "mx": 105, "sign": +1, "scale":  40},
    "knee_L":          {"tca": LEG_TCA_CHANNEL,  "pca":  8, "ini": 145, "mn": 105, "mx": 145, "sign": -1, "scale":  80},
    "knee_R":          {"tca": LEG_TCA_CHANNEL,  "pca":  3, "ini":  65, "mn":  55, "mx": 105, "sign": +1, "scale":  80},
    "ankle_pitch_L":   {"tca": LEG_TCA_CHANNEL,  "pca":  7, "ini": 130, "mn": 110, "mx": 150, "sign": +1, "scale":  60},
    "ankle_pitch_R":   {"tca": LEG_TCA_CHANNEL,  "pca":  4, "ini":  65, "mn":  45, "mx":  85, "sign": -1, "scale":  60},
    "ankle_roll_L":    {"tca": LEG_TCA_CHANNEL,  "pca":  6, "ini": 100, "mn":  70, "mx": 130, "sign": +1, "scale": 200},
    "ankle_roll_R":    {"tca": LEG_TCA_CHANNEL,  "pca":  5, "ini":  95, "mn":  70, "mx": 130, "sign": +1, "scale": 200},
}

# ── Gait parameters ───────────────────────────────────────────────────────────
FREQ      = 0.90
HIP_AMP   = 0.24
KNEE_BASE = 0.10
KNEE_LIFT = 0.40
ANK_COMP  = 0.52
ANK_BIAS  = 0.04
ANK_ROLL  = 0.09
HIP_ROLL  = 0.06
HIP_YAW   = 0.04
SPINE_AMP = 0.055
ARM_AMP   = 0.22

# ── Gait state ────────────────────────────────────────────────────────────────
gait_state = {
    "walking":   False,
    "speed":     1.0,       # 0.4 – 1.6
    "turn":      0.0,       # -1 left … +1 right
    "direction": "front",   # "front" | "back"
    "clock":     0.0,
}

# ── PCA cache (one object per TCA channel, avoids re-init overhead at 50 Hz) ─
_pca_cache = {}

def _get_pca_gait(tca_ch: int):
    """Get or create a cached PCA9685 object. Must be called inside i2c_lock."""
    if not _hw_ok:
        return None
    if tca_ch not in _pca_cache:
        _select_tca(tca_ch)
        pca = PCA9685(i2c_bus)
        pca.frequency = 50
        _pca_cache[tca_ch] = pca
    return _pca_cache[tca_ch]

def _angle_to_duty_gait(angle_deg: float) -> int:
    pulse_us = 500.0 + 2000.0 * (angle_deg / 180.0)
    return int((pulse_us / 1_000_000.0) * 50.0 * 65535)

def set_servo_deg(name: str, angle_deg: float):
    """Move a named servo to an absolute degree, clamped to its limits."""
    if not _hw_ok:
        return
    cfg     = SERVO[name]
    clamped = max(cfg["mn"], min(cfg["mx"], angle_deg))
    _select_tca(cfg["tca"])
    pca = _get_pca_gait(cfg["tca"])
    if pca:
        pca.channels[cfg["pca"]].duty_cycle = _angle_to_duty_gait(clamped)

def gait_to_servo(name: str, gait_rad: float) -> float:
    cfg = SERVO[name]
    deg = cfg["ini"] + cfg["sign"] * math.degrees(gait_rad) * (cfg["scale"] / 57.296)
    return max(cfg["mn"], min(cfg["mx"], deg))

def stand():
    """Move all servos to neutral standing position."""
    if not _hw_ok:
        return
    with i2c_lock:
        for name, cfg in SERVO.items():
            set_servo_deg(name, cfg["ini"])

# ── Gait loop (50 Hz background thread) ──────────────────────────────────────
def gait_loop():
    DT = 0.02
    while True:
        walking  = gait_state["walking"]
        speed    = gait_state["speed"]
        turn     = gait_state["turn"]
        fwd      = 1.0 if gait_state["direction"] == "front" else -1.0

        if walking:
            gait_state["clock"] += DT * speed
            ph = 2.0 * math.pi * FREQ * gait_state["clock"]

            lHP =  fwd * HIP_AMP * math.sin(ph)
            rHP = -fwd * HIP_AMP * math.sin(ph)

            lKN = KNEE_BASE + KNEE_LIFT * max(0.0,  math.sin(ph))
            rKN = KNEE_BASE + KNEE_LIFT * max(0.0, -math.sin(ph))

            lAP = -lHP * ANK_COMP + ANK_BIAS
            rAP = -rHP * ANK_COMP + ANK_BIAS

            lAR = -ANK_ROLL * math.sin(ph)
            rAR =  ANK_ROLL * math.sin(ph)

            lHR = -HIP_ROLL * max(0.0, -math.sin(ph))
            rHR =  HIP_ROLL * max(0.0,  math.sin(ph))

            lHY =  HIP_YAW * max(0.0,  math.sin(ph)) + turn * 0.06
            rHY = -HIP_YAW * max(0.0, -math.sin(ph)) + turn * 0.06

            spY  =  SPINE_AMP * math.sin(ph)
            lARM = -ARM_AMP * math.sin(ph)
            rARM =  ARM_AMP * math.sin(ph)

            angles = {
                "hip_yaw_L":     gait_to_servo("hip_yaw_L",     lHY),
                "hip_roll_L":    gait_to_servo("hip_roll_L",     lHR),
                "hip_pitch_L":   gait_to_servo("hip_pitch_L",    lHP),
                "knee_L":        gait_to_servo("knee_L",         lKN),
                "ankle_pitch_L": gait_to_servo("ankle_pitch_L",  lAP),
                "ankle_roll_L":  gait_to_servo("ankle_roll_L",   lAR),
                "hip_yaw_R":     gait_to_servo("hip_yaw_R",      rHY),
                "hip_roll_R":    gait_to_servo("hip_roll_R",      rHR),
                "hip_pitch_R":   gait_to_servo("hip_pitch_R",    rHP),
                "knee_R":        gait_to_servo("knee_R",         rKN),
                "ankle_pitch_R": gait_to_servo("ankle_pitch_R",  rAP),
                "ankle_roll_R":  gait_to_servo("ankle_roll_R",   rAR),
                "spine":         gait_to_servo("spine",          spY),
                "chest_arm_L":   gait_to_servo("chest_arm_L",   lARM),
                "chest_arm_R":   gait_to_servo("chest_arm_R",   rARM),
            }

            try:
                with i2c_lock:
                    for name, deg in angles.items():
                        set_servo_deg(name, deg)
            except Exception as _e:
                print(f"[GAIT] I2C error: {_e}")

        time.sleep(DT)

_gait_thread = threading.Thread(target=gait_loop, daemon=True)

# =============================================================================
#  EXPRESSION DATA  (from master.py - all angles untouched)
# =============================================================================

# -- 1. HI_LEFT ---------------------------------------------------------------
HI_POSITIONS = {
    "high": {
        NECK_Y_CH: 105, NECK_X_CH: 50, CHEST_ARM_LEFT_CH: 150,
        SHOULDER_LEFT_CH: 140, BICEP_LEFT_CH: 20,
        ELBOW_LEFT_CH: 40, GRIPPER_LEFT_CH: 40,
    },
    "reverse": {
        NECK_Y_CH: 105, NECK_X_CH: 140, CHEST_ARM_LEFT_CH: 150,
        SHOULDER_LEFT_CH: 140, BICEP_LEFT_CH: 20,
        ELBOW_LEFT_CH: 155, GRIPPER_LEFT_CH: 95,
    },
}
HI_SPEED    = 0.6
HI_SEQUENCE = [
    ("move", "high"),
    ("loop", 3, [("move", "reverse"), ("move", "high")]),
]

# -- 2. HI_RIGHT --------------------------------------------------------------
HI_RIGHT_POSITIONS = {
    "high": {
        NECK_Y_CH: 105, NECK_X_CH: 140, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_RIGHT_CH: 40, BICEP_RIGHT_CH: 180,
        ELBOW_RIGHT_CH: 155, GRIPPER_RIGHT_CH: 40,
    },
    "reverse": {
        NECK_Y_CH: 105, NECK_X_CH: 50, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_RIGHT_CH: 40, BICEP_RIGHT_CH: 180,
        ELBOW_RIGHT_CH: 40, GRIPPER_RIGHT_CH: 95,
    },
}
HI_RIGHT_SPEED    = 0.6
HI_RIGHT_SEQUENCE = [
    ("move", "high"),
    ("loop", 3, [("move", "reverse"), ("move", "high")]),
]

# -- 3. WELCOME ---------------------------------------------------------------
WELCOME_POSITIONS = {
    "arms_open": {
        NECK_Y_CH: 105, NECK_X_CH: 95,
        CHEST_ARM_LEFT_CH: 150, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_LEFT_CH: 140, SHOULDER_RIGHT_CH: 40,
        BICEP_LEFT_CH: 20, BICEP_RIGHT_CH: 180,
        ELBOW_LEFT_CH: 40, ELBOW_RIGHT_CH: 155,
        GRIPPER_LEFT_CH: 40, GRIPPER_RIGHT_CH: 40,
        SPINAL_X_CH: 102,
    },
    "arms_lower": {
        NECK_Y_CH: 105, NECK_X_CH: 95,
        CHEST_ARM_LEFT_CH: 150, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_LEFT_CH: 140, SHOULDER_RIGHT_CH: 40,
        BICEP_LEFT_CH: 20, BICEP_RIGHT_CH: 180,
        ELBOW_LEFT_CH: 155, ELBOW_RIGHT_CH: 40,
        GRIPPER_LEFT_CH: 95, GRIPPER_RIGHT_CH: 95,
        SPINAL_X_CH: 102,
    },
}
WELCOME_SPEED    = 0.8
WELCOME_SEQUENCE = [
    ("move", "arms_open"),
    ("loop", 3, [("move", "arms_lower"), ("move", "arms_open")]),
]

# -- 4. YES -------------------------------------------------------------------
YES_POSITIONS = {
    "head_up": {
        NECK_Y_CH: 90, NECK_X_CH: 95,
        CHEST_ARM_RIGHT_CH: 70, SHOULDER_RIGHT_CH: 90,
        BICEP_RIGHT_CH: 100, ELBOW_RIGHT_CH: 155,
        GRIPPER_RIGHT_CH: 95, SPINAL_X_CH: 102,
    },
    "head_down": {
        NECK_Y_CH: 120, NECK_X_CH: 95,
        CHEST_ARM_RIGHT_CH: 70, SHOULDER_RIGHT_CH: 90,
        BICEP_RIGHT_CH: 100, ELBOW_RIGHT_CH: 95,
        GRIPPER_RIGHT_CH: 95, SPINAL_X_CH: 102,
    },
}
YES_SPEED    = 0.5
YES_SEQUENCE = [
    ("move", "head_up"),
    ("loop", 3, [("move", "head_down"), ("move", "head_up")]),
]

# -- 5. NO --------------------------------------------------------------------
NO_POSITIONS = {
    "head_left": {
        NECK_Y_CH: 105, NECK_X_CH: 140,
        CHEST_ARM_LEFT_CH: 70, CHEST_ARM_RIGHT_CH: 120,
        SHOULDER_LEFT_CH: 30, SHOULDER_RIGHT_CH: 150,
        BICEP_LEFT_CH: 150, BICEP_RIGHT_CH: 50,
        ELBOW_LEFT_CH: 60, ELBOW_RIGHT_CH: 130,
        GRIPPER_LEFT_CH: 95, GRIPPER_RIGHT_CH: 95,
        SPINAL_X_CH: 102,
    },
    "head_right": {
        NECK_Y_CH: 105, NECK_X_CH: 50,
        CHEST_ARM_LEFT_CH: 70, CHEST_ARM_RIGHT_CH: 120,
        SHOULDER_LEFT_CH: 30, SHOULDER_RIGHT_CH: 150,
        BICEP_LEFT_CH: 150, BICEP_RIGHT_CH: 50,
        ELBOW_LEFT_CH: 110, ELBOW_RIGHT_CH: 80,
        GRIPPER_LEFT_CH: 40, GRIPPER_RIGHT_CH: 40,
        SPINAL_X_CH: 102,
    },
}
NO_SPEED    = 0.5
NO_SEQUENCE = [
    ("move", "head_left"),
    ("loop", 3, [("move", "head_right"), ("move", "head_left")]),
]

# -- 6. EXPLAIN ---------------------------------------------------------------
EXPLAIN_POSITIONS = {
    "left_side": {
        NECK_Y_CH: 105, NECK_X_CH: 135, CHEST_ARM_LEFT_CH: 120,
        SHOULDER_LEFT_CH: 90, BICEP_LEFT_CH: 100,
        ELBOW_LEFT_CH: 35, GRIPPER_LEFT_CH: 95, SPINAL_X_CH: 102,
    },
    "left_reverse": {
        NECK_Y_CH: 105, NECK_X_CH: 135, CHEST_ARM_LEFT_CH: 120,
        SHOULDER_LEFT_CH: 90, BICEP_LEFT_CH: 100,
        ELBOW_LEFT_CH: 95, GRIPPER_LEFT_CH: 95, SPINAL_X_CH: 102,
    },
    "right_side": {
        NECK_Y_CH: 105, NECK_X_CH: 55, CHEST_ARM_RIGHT_CH: 70,
        SHOULDER_RIGHT_CH: 90, BICEP_RIGHT_CH: 100,
        ELBOW_RIGHT_CH: 155, GRIPPER_RIGHT_CH: 95, SPINAL_X_CH: 102,
    },
    "right_reverse": {
        NECK_Y_CH: 105, NECK_X_CH: 55, CHEST_ARM_RIGHT_CH: 70,
        SHOULDER_RIGHT_CH: 90, BICEP_RIGHT_CH: 100,
        ELBOW_RIGHT_CH: 95, GRIPPER_RIGHT_CH: 95, SPINAL_X_CH: 102,
    },
    "center_a": {
        NECK_Y_CH: 105, NECK_X_CH: 95,
        CHEST_ARM_LEFT_CH: 120, CHEST_ARM_RIGHT_CH: 70,
        SHOULDER_LEFT_CH: 90, SHOULDER_RIGHT_CH: 90,
        BICEP_LEFT_CH: 100, BICEP_RIGHT_CH: 100,
        ELBOW_LEFT_CH: 35, ELBOW_RIGHT_CH: 155,
        GRIPPER_LEFT_CH: 95, GRIPPER_RIGHT_CH: 95, SPINAL_X_CH: 102,
    },
    "center_b": {
        NECK_Y_CH: 105, NECK_X_CH: 95,
        CHEST_ARM_LEFT_CH: 120, CHEST_ARM_RIGHT_CH: 70,
        SHOULDER_LEFT_CH: 90, SHOULDER_RIGHT_CH: 90,
        BICEP_LEFT_CH: 100, BICEP_RIGHT_CH: 100,
        ELBOW_LEFT_CH: 95, ELBOW_RIGHT_CH: 95,
        GRIPPER_LEFT_CH: 95, GRIPPER_RIGHT_CH: 95, SPINAL_X_CH: 102,
    },
}
EXPLAIN_SPEED    = 0.6
EXPLAIN_SEQUENCE = [
    ("move", "left_side"),
    ("loop", 2, [("move", "left_reverse"),  ("move", "left_side")]),
    ("move", "right_side"),
    ("loop", 2, [("move", "right_reverse"), ("move", "right_side")]),
    ("move", "center_a"),
    ("loop", 2, [("move", "center_b"),      ("move", "center_a")]),
]

# -- 7. AUDIENCE --------------------------------------------------------------
AUDIENCE_POSITIONS = {
    "left_think": {
        NECK_Y_CH: 120, NECK_X_CH: 135, CHEST_ARM_LEFT_CH: 150,
        SHOULDER_LEFT_CH: 140, BICEP_LEFT_CH: 20,
        ELBOW_LEFT_CH: 40, GRIPPER_LEFT_CH: 95,
    },
    "left_up": {
        NECK_Y_CH: 90, NECK_X_CH: 135, CHEST_ARM_LEFT_CH: 150,
        SHOULDER_LEFT_CH: 140, BICEP_LEFT_CH: 20,
        ELBOW_LEFT_CH: 40, GRIPPER_LEFT_CH: 95,
    },
    "left_elbow_rev": {
        NECK_Y_CH: 90, NECK_X_CH: 135, CHEST_ARM_LEFT_CH: 150,
        SHOULDER_LEFT_CH: 140, BICEP_LEFT_CH: 20,
        ELBOW_LEFT_CH: 155, GRIPPER_LEFT_CH: 95,
    },
    "center": {
        NECK_Y_CH: 105, NECK_X_CH: 95,
        CHEST_ARM_LEFT_CH: 150, SHOULDER_LEFT_CH: 30,
        BICEP_LEFT_CH: 100, ELBOW_LEFT_CH: 95, GRIPPER_LEFT_CH: 95,
        CHEST_ARM_RIGHT_CH: 40, SHOULDER_RIGHT_CH: 150,
        BICEP_RIGHT_CH: 100, ELBOW_RIGHT_CH: 95, GRIPPER_RIGHT_CH: 95,
    },
    "right_think": {
        NECK_Y_CH: 120, NECK_X_CH: 55, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_RIGHT_CH: 40, BICEP_RIGHT_CH: 180,
        ELBOW_RIGHT_CH: 155, GRIPPER_RIGHT_CH: 95,
    },
    "right_up": {
        NECK_Y_CH: 90, NECK_X_CH: 55, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_RIGHT_CH: 40, BICEP_RIGHT_CH: 180,
        ELBOW_RIGHT_CH: 155, GRIPPER_RIGHT_CH: 95,
    },
    "right_elbow_rev": {
        NECK_Y_CH: 90, NECK_X_CH: 55, CHEST_ARM_RIGHT_CH: 40,
        SHOULDER_RIGHT_CH: 40, BICEP_RIGHT_CH: 180,
        ELBOW_RIGHT_CH: 40, GRIPPER_RIGHT_CH: 95,
    },
}
AUDIENCE_SPEED    = 0.8
AUDIENCE_SEQUENCE = [
    ("move", "left_think"),
    ("loop", 2, [("move", "left_up"), ("move", "left_elbow_rev"), ("move", "left_think")]),
    ("move", "center"),
    ("move", "right_think"),
    ("loop", 2, [("move", "right_up"), ("move", "right_elbow_rev"), ("move", "right_think")]),
]

# -- 8. BOW -------------------------------------------------------------------
BOW_POSITIONS = {
    "bow_down": {
        NECK_Y_CH: 140, NECK_X_CH: 95,
        CHEST_ARM_LEFT_CH: 130, CHEST_ARM_RIGHT_CH: 90,
        SHOULDER_LEFT_CH: 30, SHOULDER_RIGHT_CH: 150,
        BICEP_LEFT_CH: 180, BICEP_RIGHT_CH: 0,
        ELBOW_LEFT_CH: 60, ELBOW_RIGHT_CH: 120,
        GRIPPER_LEFT_CH: 95, GRIPPER_RIGHT_CH: 95,
        SPINAL_X_CH: 102,
    },
}
BOW_SPEED    = 1.2
BOW_SEQUENCE = [
    ("move", "bow_down"),
    ("wait", 2),
]

# -- Expression registry ------------------------------------------------------
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

# -- OLED eye image per expression --------------------------------------------
OLED_MAP = {
    "hi_left":  "left",
    "hi_right": "right",
    "welcome":  "focus",
    "yes":      "bottomLeft",
    "no":       "focus",
    "explain":  "focus",
    "audience": "topLeft",
    "bow":      "bottomLeft",
}

OLED_LOOP_SEQ = [
    "focus", "left", "right",
    "focus", "topLeft", "topRight",
    "focus", "bottomLeft", "bottomRight",
]

# =============================================================================
#  SHARED STATE
# =============================================================================
i2c_lock   = threading.Lock()
oled_event = threading.Event()
oled_event.set()
expr_lock  = threading.Lock()

robot_status = {
    "expression": "idle",
    "oled":       "loop",
    "busy":       False,
}

# =============================================================================
#  I2C + SERVO HELPERS
# =============================================================================
_hw_ok  = False
i2c_bus = None

try:
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    _hw_ok  = True
    print("I2C bus initialised.")
except Exception as _e:
    print(f"WARNING: I2C init failed — servo/OLED disabled. ({_e})")

def _select_tca(channel: int):
    with I2CDevice(i2c_bus, TCA_ADDR) as dev:
        dev.write(bytes([1 << channel]))

def _calc_duty(angle: float) -> int:
    pulse = 500.0 + 2000.0 * (angle / 180.0)
    return int((pulse / 1_000_000.0) * 50.0 * 65535)

def set_servos(tca_channel: int, angles: dict):
    if not _hw_ok:
        return
    try:
        with i2c_lock:
            _select_tca(tca_channel)
            time.sleep(0.01)
            pca = PCA9685(i2c_bus)
            pca.frequency = 50
            for ch, angle in angles.items():
                pca.channels[ch].duty_cycle = _calc_duty(angle)
    except Exception as _e:
        print(f"WARNING: set_servos error — {_e}")

# =============================================================================
#  OLED HELPERS
# =============================================================================
_oled_ok   = False
oled_ch    = None
oled_dev   = None
_blank_img = Image.new("1", (128, 64), 0)

def _find_oled():
    print("Scanning TCA channels for OLED...")
    for ch in range(8):
        try:
            with SMBus(1) as bus:
                bus.write_byte(TCA_ADDR, 1 << ch)
            for addr in [0x3C, 0x3D]:
                try:
                    with SMBus(1) as bus:
                        bus.read_byte(addr)
                    print(f"OLED found: channel={ch}  addr=0x{addr:02X}")
                    return ch, addr
                except OSError:
                    pass
        except Exception:
            pass
    return None, None

if _hw_ok:
    try:
        oled_ch, oled_addr = _find_oled()
        if oled_ch is not None:
            with SMBus(1) as _b:
                _b.write_byte(TCA_ADDR, 1 << oled_ch)
            _oled_serial = luma_i2c(port=1, address=oled_addr)
            oled_dev     = sh1106(_oled_serial)
            _oled_ok     = True
        else:
            print("WARNING: No OLED found — eye display disabled.")
    except Exception as _e:
        print(f"WARNING: OLED init failed — eye display disabled. ({_e})")

def _load_bmp(name: str) -> Image.Image:
    path = os.path.join("expressions", f"{name}.bmp")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing BMP: {path}")
    return ImageOps.invert(Image.open(path).convert("1"))

def _display(img: Image.Image):
    if not _oled_ok:
        return
    with SMBus(1) as bus:
        bus.write_byte(TCA_ADDR, 1 << oled_ch)
    oled_dev.display(img)

def show_oled_blink(name: str):
    if not _oled_ok:
        return
    try:
        img = _load_bmp(name)
        with i2c_lock:
            _display(_blank_img)
            time.sleep(0.1)
            _display(img)
    except FileNotFoundError as _e:
        print(_e)

# =============================================================================
#  STARTUP INIT
# =============================================================================
def initialize_robot():
    if not _hw_ok:
        print("Hardware not available — skipping servo init.")
        return
    try:
        print("Initializing legs...")
        set_servos(LEG_TCA_CHANNEL, LEG_INITIAL)
        time.sleep(0.5)
        print("Initializing body...")
        set_servos(BODY_TCA_CHANNEL, BODY_INITIAL)
        time.sleep(0.5)
        print("Robot ready.")
    except Exception as _e:
        print(f"WARNING: Servo init error — {_e}")

# =============================================================================
#  OLED LOOP THREAD
# =============================================================================
def oled_loop():
    idx  = 0
    last = None
    while True:
        oled_event.wait()   # blocks while paused (during expressions)
        name = OLED_LOOP_SEQ[idx % len(OLED_LOOP_SEQ)]
        try:
            img = _load_bmp(name)
            with i2c_lock:
                if last is not None:
                    _display(_blank_img)
                    time.sleep(0.1)
                _display(img)
            last = img
        except FileNotFoundError as e:
            print(e)
        idx += 1
        # Hold 1.5 s but wake immediately if paused
        for _ in range(15):
            if not oled_event.is_set():
                break
            time.sleep(0.1)

_oled_thread = threading.Thread(target=oled_loop, daemon=True)

# =============================================================================
#  EXPRESSION RUNNER
# =============================================================================
def _build_position(positions: dict, name: str) -> dict:
    full = dict(BODY_INITIAL)
    full.update(positions[name])
    return full

def _execute_move(positions: dict, name: str, speed: float):
    set_servos(BODY_TCA_CHANNEL, _build_position(positions, name))
    time.sleep(speed)

def _run_steps(steps: list, positions: dict, speed: float):
    for step in steps:
        kind = step[0]
        if kind == "move":
            _execute_move(positions, step[1], speed)
        elif kind == "loop":
            for _ in range(step[1]):
                _run_steps(step[2], positions, speed)
        elif kind == "wait":
            time.sleep(step[1])

def trigger_expression(name: str):
    """Run a full expression in a background thread."""
    if name not in EXPRESSIONS:
        return
    if not expr_lock.acquire(blocking=False):
        print(f"Expression busy, ignoring: {name}")
        return

    try:
        positions, speed, sequence = EXPRESSIONS[name]
        robot_status.update({"expression": name, "busy": True, "oled": "expression"})
        socketio.emit("status", robot_status)

        # Pause gait during expression to avoid I2C conflicts
        was_walking = gait_state["walking"]
        gait_state["walking"] = False
        time.sleep(0.05)  # let gait loop finish current cycle

        # Pause OLED loop, wait for it to finish current step
        oled_event.clear()
        time.sleep(0.2)

        # Show matching eye image
        show_oled_blink(OLED_MAP.get(name, "focus"))

        # Run servos
        _run_steps(sequence, positions, speed)

        # Return body to initial
        set_servos(BODY_TCA_CHANNEL, BODY_INITIAL)
        time.sleep(speed)

        robot_status.update({"expression": "idle", "busy": False, "oled": "loop"})
        socketio.emit("status", robot_status)

        # Resume gait if it was walking before the expression
        gait_state["walking"] = was_walking

    finally:
        oled_event.set()    # resume OLED loop no matter what
        expr_lock.release()

# =============================================================================
#  FLASK + SOCKETIO
# =============================================================================
app      = Flask(__name__)
app.config["SECRET_KEY"] = "arceus_2025"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.route("/")
def index():
    return render_template("index.html", expressions=list(EXPRESSIONS.keys()))

@app.route("/status")
def get_status():
    return jsonify(robot_status)

@app.route("/expression/<name>", methods=["POST"])
def do_expression(name):
    if name not in EXPRESSIONS:
        return jsonify({"ok": False, "reason": "unknown expression"}), 404
    if robot_status["busy"]:
        return jsonify({"ok": False, "reason": "busy"}), 409
    threading.Thread(target=trigger_expression, args=(name,), daemon=True).start()
    return jsonify({"ok": True, "expression": name})

@socketio.on("connect")
def on_connect():
    emit("status", robot_status)

@app.after_request
def add_cors(response):
    """Allow browser to call Pi 1 directly from any origin."""
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# =============================================================================
#  WALKING  — wired to gait_loop via gait_state
# =============================================================================
@app.route("/walk/<direction>", methods=["POST", "OPTIONS"])
def walk(direction):
    if direction == "front":
        gait_state["direction"] = "front"
        gait_state["turn"]      = 0.0
        gait_state["walking"]   = True
    elif direction == "back":
        gait_state["direction"] = "back"
        gait_state["turn"]      = 0.0
        gait_state["walking"]   = True
    elif direction == "left":
        gait_state["direction"] = "front"
        gait_state["turn"]      = -1.0
        gait_state["walking"]   = True
    elif direction == "right":
        gait_state["direction"] = "front"
        gait_state["turn"]      = +1.0
        gait_state["walking"]   = True
    else:
        return jsonify({"ok": False, "reason": "unknown direction"}), 400

    print(f"[WALK] {direction.upper()}  speed={gait_state['speed']:.1f}")
    return jsonify({"ok": True, "direction": direction})

@app.route("/walk/stop", methods=["POST", "OPTIONS"])
def walk_stop():
    gait_state["walking"] = False
    gait_state["turn"]    = 0.0
    print("[WALK] STOP")
    threading.Thread(target=lambda: (time.sleep(0.3), stand()), daemon=True).start()
    return jsonify({"ok": True})

@app.route("/walk/speed", methods=["POST", "OPTIONS"])
def walk_speed():
    data  = request.get_json(silent=True) or {}
    speed = float(data.get("speed", 1.0))
    gait_state["speed"] = max(0.4, min(1.6, round(speed * 1.6, 2)))
    print(f"[WALK] Speed = {gait_state['speed']:.2f}")
    return jsonify({"ok": True, "speed": gait_state["speed"]})

# =============================================================================
#  MAIN
# =============================================================================
if __name__ == "__main__":
    print("\n  Arceus Robot Controller\n")
    initialize_robot()

    print("Starting OLED eye loop...")
    _oled_thread.start()

    print("Starting gait loop...")
    _gait_thread.start()

    print("Server starting at http://0.0.0.0:5000")
    print("Open http://<Pi_IP>:5000 in any browser on your network.\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
