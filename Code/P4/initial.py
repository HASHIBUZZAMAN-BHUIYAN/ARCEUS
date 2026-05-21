import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_bus_device.i2c_device import I2CDevice

# ========== CONFIGURATION ==========
BODY_TCA_CHANNEL = 0  # PCA9685 for upper body, neck, arms
LEG_TCA_CHANNEL  = 5  # PCA9685 for legs, hips, knees, feet
TCA_ADDR         = 0x70  # TCA9548A I2C multiplexer address

# ========== BODY SERVO CHANNELS ==========
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

# ========== LEG SERVO CHANNELS ==========
HIP_YAW_LEFT_CH     = 11
HIP_YAW_RIGHT_CH    = 0
HIP_ROLL_LEFT_CH    = 10
HIP_ROLL_RIGHT_CH   = 1
HIP_PITCH_LEFT_CH   = 9
HIP_PITCH_RIGHT_CH  = 2
KNEE_LEFT_CH        = 8
KNEE_RIGHT_CH       = 3
ANKLE_PITCH_LEFT_CH = 7
ANKLE_PITCH_RIGHT_CH= 4
ANKLE_ROLL_LEFT_CH  = 6
ANKLE_ROLL_RIGHT_CH = 5

# ========== I2C SETUP ==========
i2c = busio.I2C(board.SCL, board.SDA)

def select_tca_channel(channel: int):
    """Activate only the specified TCA9548A I2C channel."""
    if 0 <= channel <= 7:
        with I2CDevice(i2c, TCA_ADDR) as dev:
            dev.write(bytes([1 << channel]))

def calculate_duty(angle: float) -> int:
    """Convert angle to PWM duty cycle for ~50 Hz servos."""
    min_pulse = 500     # microseconds
    max_pulse = 2500    # microseconds
    pulse = min_pulse + (max_pulse - min_pulse) * (angle / 180.0)
    duty = int((pulse / 1_000_000.0) * 50.0 * 65535)
    return duty

def set_multiple_servo_angles(tca_channel: int, servo_angles: dict, per_servo_delay: float = 0.05):
    """Select TCA channel and set multiple servo angles on the corresponding PCA9685."""
    select_tca_channel(tca_channel)
    time.sleep(0.01)

    pca = PCA9685(i2c)
    pca.frequency = 50

    for channel, angle in servo_angles.items():
        duty = calculate_duty(angle)
        pca.channels[channel].duty_cycle = duty
        print(f"[TCA {tca_channel}] PCA channel {channel} -> {angle}°")
        time.sleep(per_servo_delay)

def initialize_body_servos():
    set_multiple_servo_angles(BODY_TCA_CHANNEL, {
        NECK_Y_CH:          105,  # Neck Y
        NECK_X_CH:           95,  # Neck X
        CHEST_ARM_LEFT_CH:  150,  # Chest-Arm Left
        CHEST_ARM_RIGHT_CH:  45,  # Chest-Arm Right
        SHOULDER_LEFT_CH:    30,  # Shoulder Left
        SHOULDER_RIGHT_CH:  150,  # Shoulder Right
        BICEP_LEFT_CH:      100,  # Bicep Left
        BICEP_RIGHT_CH:      95,  # Bicep Right
        ELBOW_LEFT_CH:       95,  # Elbow Left
        ELBOW_RIGHT_CH:      95,  # Elbow Right
        GRIPPER_LEFT_CH:     95,  # Gripper Left
        GRIPPER_RIGHT_CH:    95,  # Gripper Right
        SPINAL_X_CH:        105,  # Spinal X
    })

def initialize_leg_servos():
    set_multiple_servo_angles(LEG_TCA_CHANNEL, {
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
    })

if __name__ == "__main__":
    print("Initializing Body Servos to Base Positions...")
    initialize_body_servos()
    print("Initializing Leg Servos to Base Positions...")
    initialize_leg_servos()
    print("Initialization complete.")




