#!/usr/bin/env python3
"""
Arceus Biped Robot — RPi4B Web Gait Server
=========================================
Hardware : RPi4B+ → TCA9548A (0x70) → 2× PCA9685 → 20× MG996R

Port: 5000
"""

import math
import time
import threading
from flask import Flask, render_template, Response
from flask_socketio import SocketIO, emit

# ── Try to import RPi hardware ────────────────────────────────────────────────
try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_bus_device.i2c_device import I2CDevice
    i2c = busio.I2C(board.SCL, board.SDA)
    HARDWARE = True
    print("[ARCEUS] Hardware mode: RPi I2C detected")
except Exception as e:
    HARDWARE = False
    print(f"[ARCEUS] Simulation mode (no RPi hardware): {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#  HARDWARE CONSTANTS 
# ═══════════════════════════════════════════════════════════════════════════════
TCA_ADDR         = 0x70
BODY_TCA_CHANNEL = 0
LEG_TCA_CHANNEL  = 5

# ── Servo config table ────────────────────────────────────────────────────────
# Each key maps to:
#   tca   : TCA9548A channel
#   pca   : PCA9685 channel
#   ini   : initial/neutral angle (degrees, 0-180 scale)
#   mn    : minimum angle (degrees)
#   mx    : maximum angle (degrees)
#   sign  : +1 → positive gait angle increments servo,
#           -1 → positive gait angle decrements servo
#   scale : degrees of servo travel per radian of gait angle
#
# Signs derived from ANG_DATA.xlsx DECREMENT/INCREMENT directions.
# ─────────────────────────────────────────────────────────────────────────────
SERVO = {
    # ── BODY (TCA 0) ──────────────────────────────────────────────────────────
    "neck_y":          {"tca": BODY_TCA_CHANNEL, "pca":  0, "ini": 105, "mn":  60, "mx": 150, "sign": +1, "scale": 40},
    "neck_x":          {"tca": BODY_TCA_CHANNEL, "pca": 11, "ini":  95, "mn":  10, "mx": 180, "sign": +1, "scale": 80},
    "chest_arm_L":     {"tca": BODY_TCA_CHANNEL, "pca": 12, "ini": 150, "mn":  50, "mx": 180, "sign": -1, "scale": 50},
    "chest_arm_R":     {"tca": BODY_TCA_CHANNEL, "pca": 10, "ini":  40, "mn":  10, "mx": 145, "sign": +1, "scale": 50},
    "shoulder_L":      {"tca": BODY_TCA_CHANNEL, "pca":  3, "ini":  30, "mn":  10, "mx": 180, "sign": +1, "scale": 30},
    "shoulder_R":      {"tca": BODY_TCA_CHANNEL, "pca":  1, "ini": 150, "mn":   0, "mx": 170, "sign": -1, "scale": 30},
    "bicep_L":         {"tca": BODY_TCA_CHANNEL, "pca":  4, "ini": 100, "mn":  40, "mx": 160, "sign": +1, "scale": 50},
    "bicep_R":         {"tca": BODY_TCA_CHANNEL, "pca":  2, "ini": 100, "mn":  60, "mx": 140, "sign": -1, "scale": 50},
    "elbow_L":         {"tca": BODY_TCA_CHANNEL, "pca":  7, "ini":  95, "mn":  40, "mx": 155, "sign": +1, "scale": 50},
    "elbow_R":         {"tca": BODY_TCA_CHANNEL, "pca":  5, "ini":  95, "mn":  40, "mx": 155, "sign": -1, "scale": 50},
    "gripper_L":       {"tca": BODY_TCA_CHANNEL, "pca":  8, "ini":  95, "mn":  40, "mx":  95, "sign": +1, "scale": 30},
    "gripper_R":       {"tca": BODY_TCA_CHANNEL, "pca":  6, "ini":  95, "mn":  40, "mx":  95, "sign": -1, "scale": 30},
    "spine":           {"tca": BODY_TCA_CHANNEL, "pca":  9, "ini": 102, "mn":  94, "mx": 110, "sign": -1, "scale": 30},
    # ── LEGS (TCA 5) ──────────────────────────────────────────────────────────
    # Hip yaw: DECREMENT=OUTSIDE(toe-out) for left, DECREMENT=INSIDE for right → both sign=-1
    "hip_yaw_L":       {"tca": LEG_TCA_CHANNEL,  "pca": 11, "ini": 100, "mn":  80, "mx": 120, "sign": -1, "scale": 80},
    "hip_yaw_R":       {"tca": LEG_TCA_CHANNEL,  "pca":  0, "ini": 100, "mn":  80, "mx": 120, "sign": -1, "scale": 80},
    # Hip roll: INSIDE=INCREMENT(L) / INSIDE=DECREMENT(R) → sign=-1 both (mirror mounted)
    "hip_roll_L":      {"tca": LEG_TCA_CHANNEL,  "pca": 10, "ini": 105, "mn":  95, "mx": 115, "sign": -1, "scale": 80},
    "hip_roll_R":      {"tca": LEG_TCA_CHANNEL,  "pca":  1, "ini": 105, "mn":  95, "mx": 115, "sign": -1, "scale": 80},
    # Hip pitch: DECREMENT=UP(forward) for L, INCREMENT=UP for R
    "hip_pitch_L":     {"tca": LEG_TCA_CHANNEL,  "pca":  9, "ini":  95, "mn":  85, "mx": 105, "sign": -1, "scale": 40},
    "hip_pitch_R":     {"tca": LEG_TCA_CHANNEL,  "pca":  2, "ini":  95, "mn":  85, "mx": 105, "sign": +1, "scale": 40},
    # Knee: DECREMENT=FORWARD(bend) for L → sign=-1; INCREMENT=FORWARD for R → sign=+1
    "knee_L":          {"tca": LEG_TCA_CHANNEL,  "pca":  8, "ini": 145, "mn": 105, "mx": 145, "sign": -1, "scale": 80},
    "knee_R":          {"tca": LEG_TCA_CHANNEL,  "pca":  3, "ini":  65, "mn":  55, "mx": 105, "sign": +1, "scale": 80},
    # Ankle pitch: INCREMENT=FORWARD(dorsiflex) L; DECREMENT=FORWARD R
    "ankle_pitch_L":   {"tca": LEG_TCA_CHANNEL,  "pca":  7, "ini": 130, "mn": 110, "mx": 150, "sign": +1, "scale": 60},
    "ankle_pitch_R":   {"tca": LEG_TCA_CHANNEL,  "pca":  4, "ini":  65, "mn":  45, "mx":  85, "sign": -1, "scale": 60},
    # Ankle roll: INCREMENT=LEFT UP(inward L), INCREMENT=RIGHT UP(inward R) → both sign=+1
    "ankle_roll_L":    {"tca": LEG_TCA_CHANNEL,  "pca":  6, "ini": 100, "mn":  70, "mx": 130, "sign": +1, "scale":200},
    "ankle_roll_R":    {"tca": LEG_TCA_CHANNEL,  "pca":  5, "ini": 100, "mn":  70, "mx": 130, "sign": +1, "scale":200},
}

# ═══════════════════════════════════════════════════════════════════════════════
#  I2C / SERVO DRIVER
# ═══════════════════════════════════════════════════════════════════════════════
_pca_cache = {}   # cache PCA objects per TCA channel

def _select_tca(channel: int):
    if HARDWARE:
        with I2CDevice(i2c, TCA_ADDR) as dev:
            dev.write(bytes([1 << channel]))
        time.sleep(0.005)

def _get_pca(tca_ch: int) -> object:
    if tca_ch not in _pca_cache:
        _select_tca(tca_ch)
        pca = PCA9685(i2c)
        pca.frequency = 50
        _pca_cache[tca_ch] = pca
    return _pca_cache[tca_ch]

def _angle_to_duty(angle_deg: float) -> int:
    """Convert 0-180° to 16-bit PWM duty at 50 Hz (500-2500 µs pulse)."""
    pulse_us = 500.0 + (2500.0 - 500.0) * (angle_deg / 180.0)
    return int((pulse_us / 1_000_000.0) * 50.0 * 65535)

def set_servo_deg(name: str, angle_deg: float):
    """Move a servo to an absolute degree (0-180), clamped to its limits."""
    cfg = SERVO[name]
    clamped = max(cfg["mn"], min(cfg["mx"], angle_deg))
    if HARDWARE:
        _select_tca(cfg["tca"])
        pca = _get_pca(cfg["tca"])
        pca.channels[cfg["pca"]].duty_cycle = _angle_to_duty(clamped)

def gait_to_servo(name: str, gait_rad: float) -> float:
    """
    Convert a gait joint angle (radians, centred at 0) to a servo degree.
    servo_deg = initial + sign * gait_rad * scale_deg_per_rad
    Returns the clamped degree value.
    """
    cfg = SERVO[name]
    deg = cfg["ini"] + cfg["sign"] * math.degrees(gait_rad) * (cfg["scale"] / 57.296)
    return max(cfg["mn"], min(cfg["mx"], deg))

def stand():
    """Move all servos to their initial (neutral standing) positions."""
    for name, cfg in SERVO.items():
        set_servo_deg(name, cfg["ini"])

# ═══════════════════════════════════════════════════════════════════════════════
#  GAIT PARAMETERS  (matched to 3-D simulation)
# ═══════════════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED ROBOT STATE
# ═══════════════════════════════════════════════════════════════════════════════
state = {
    "walking": False,
    "speed":   1.0,    # 0.5 – 1.5
    "turn":    0.0,    # -1 left … +1 right
    "clock":   0.0,
    "lock":    threading.Lock(),
}

# ═══════════════════════════════════════════════════════════════════════════════
#  GAIT LOOP  (50 Hz background thread)
# ═══════════════════════════════════════════════════════════════════════════════
def gait_loop():
    DT = 0.02  # 50 Hz
    while True:
        with state["lock"]:
            walking = state["walking"]
            speed   = state["speed"]
            turn    = state["turn"]
            if walking:
                state["clock"] += DT * speed

        if walking:
            ph = 2.0 * math.pi * FREQ * state["clock"]

            # ── Joint angles (radians, URDF convention) ──────────────
            lHP =  HIP_AMP * math.sin(ph)
            rHP = -HIP_AMP * math.sin(ph)

            lKN = KNEE_BASE + KNEE_LIFT * max(0.0,  math.sin(ph))
            rKN = KNEE_BASE + KNEE_LIFT * max(0.0, -math.sin(ph))

            lAP = -lHP * ANK_COMP + ANK_BIAS
            rAP = -rHP * ANK_COMP + ANK_BIAS

            lAR = -ANK_ROLL * math.sin(ph)
            rAR =  ANK_ROLL * math.sin(ph)

            lHR = -HIP_ROLL * max(0.0, -math.sin(ph))
            rHR =  HIP_ROLL * max(0.0,  math.sin(ph))

            # Hip yaw: toe-out during swing + turn bias
            lHY =  HIP_YAW * max(0.0,  math.sin(ph)) + turn * 0.06
            rHY = -HIP_YAW * max(0.0, -math.sin(ph)) + turn * 0.06

            spY =  SPINE_AMP * math.sin(ph)
            lARM = -ARM_AMP * math.sin(ph)
            rARM =  ARM_AMP * math.sin(ph)

            # ── Convert to servo degrees and send ────────────────────
            angles = {
                "hip_yaw_L":    gait_to_servo("hip_yaw_L",    lHY),
                "hip_roll_L":   gait_to_servo("hip_roll_L",   lHR),
                "hip_pitch_L":  gait_to_servo("hip_pitch_L",  lHP),
                "knee_L":       gait_to_servo("knee_L",       lKN),
                "ankle_pitch_L":gait_to_servo("ankle_pitch_L",lAP),
                "ankle_roll_L": gait_to_servo("ankle_roll_L", lAR),
                "hip_yaw_R":    gait_to_servo("hip_yaw_R",    rHY),
                "hip_roll_R":   gait_to_servo("hip_roll_R",   rHR),
                "hip_pitch_R":  gait_to_servo("hip_pitch_R",  rHP),
                "knee_R":       gait_to_servo("knee_R",       rKN),
                "ankle_pitch_R":gait_to_servo("ankle_pitch_R",rAP),
                "ankle_roll_R": gait_to_servo("ankle_roll_R", rAR),
                "spine":        gait_to_servo("spine",        spY),
                "chest_arm_L":  gait_to_servo("chest_arm_L",  lARM),
                "chest_arm_R":  gait_to_servo("chest_arm_R",  rARM),
            }

            for name, deg in angles.items():
                set_servo_deg(name, deg)

            # ── Broadcast telemetry ───────────────────────────────────
            socketio.emit("telemetry", {
                "phase":   round(ph % (2 * math.pi), 3),
                "stance":  "LEFT" if math.sin(ph) < 0 else "RIGHT",
                "lHP": round(math.degrees(lHP), 1),
                "rHP": round(math.degrees(rHP), 1),
                "lKN": round(math.degrees(lKN), 1),
                "rKN": round(math.degrees(rKN), 1),
                "lAP": round(math.degrees(lAP), 1),
                "rAP": round(math.degrees(rAP), 1),
                "lAR": round(math.degrees(lAR), 1),
                "rAR": round(math.degrees(rAR), 1),
                "lHR": round(math.degrees(lHR), 1),
                "rHR": round(math.degrees(rHR), 1),
                "spine": round(math.degrees(spY), 1),
                "servo_lHP": round(angles["hip_pitch_L"], 1),
                "servo_rHP": round(angles["hip_pitch_R"], 1),
                "servo_lKN": round(angles["knee_L"], 1),
                "servo_rKN": round(angles["knee_R"], 1),
                "servo_lAR": round(angles["ankle_roll_L"], 1),
                "servo_rAR": round(angles["ankle_roll_R"], 1),
            })

        time.sleep(DT)

# ═══════════════════════════════════════════════════════════════════════════════
#  FLASK + SOCKETIO
# ═══════════════════════════════════════════════════════════════════════════════
app = Flask(__name__)
app.config["SECRET_KEY"] = "lumi_rpi_2024"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.route("/")
def index():
    return render_template("lumi_controller.html")

@socketio.on("connect")
def on_connect():
    print(f"[LUMI] Browser connected")
    emit("status", {
        "hardware": HARDWARE,
        "walking":  state["walking"],
        "speed":    state["speed"],
    })

@socketio.on("disconnect")
def on_disconnect():
    print("[LUMI] Browser disconnected")

@socketio.on("command")
def on_command(data):
    cmd = data.get("cmd", "")
    print(f"[LUMI] Command: {data}")

    if cmd == "walk":
        with state["lock"]:
            state["walking"] = True

    elif cmd == "stop":
        with state["lock"]:
            state["walking"] = False
        # Return to stand after a short delay
        threading.Thread(target=lambda: (time.sleep(0.3), stand()), daemon=True).start()
        socketio.emit("status", {"walking": False})

    elif cmd == "stand":
        with state["lock"]:
            state["walking"] = False
        stand()
        socketio.emit("status", {"walking": False})

    elif cmd == "speed":
        val = float(data.get("value", 1.0))
        with state["lock"]:
            state["speed"] = max(0.4, min(1.6, val))

    elif cmd == "turn":
        val = float(data.get("value", 0.0))
        with state["lock"]:
            state["turn"] = max(-1.0, min(1.0, val))

    elif cmd == "servo":
        # Direct servo control: {"cmd":"servo","name":"knee_L","deg":120}
        name = data.get("name")
        deg  = float(data.get("deg", 90))
        if name in SERVO:
            set_servo_deg(name, deg)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("[LUMI] Moving to stand position...")
    stand()
    time.sleep(1.0)

    print("[LUMI] Starting gait loop thread...")
    t = threading.Thread(target=gait_loop, daemon=True)
    t.start()

    print("[LUMI] Server starting at  http://0.0.0.0:5000")
    print("[LUMI] Open http://<RPi_IP>:5000  in any browser")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
