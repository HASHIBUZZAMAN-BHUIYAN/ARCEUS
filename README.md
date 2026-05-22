# ARCEUS

> *"We cannot solve loneliness with technology alone. But we can make sure that on the hardest days, no one faces it without a voice beside them."*

**ARCEUS** is an emotional support robot designed to detect and respond to human sadness, loneliness, and emotional distress. Developed by **Team HYDROXYCITRONELLAL** for the **2026 상반기 SW중심대학 오픈소스 AI·SW활용 경진대회** (2026 SW-Centric University Open Source AI·SW Utilization Competition).

---

## Motivation

In South Korea, loneliness has emerged as a national crisis. According to data from the Ministry of Health and Welfare:

- Deaths attributed to loneliness increased by **7.2%** in 2024 compared to the previous year — a trend rising every year since 2020.
- Deaths by suicide reached a **13-year high** in 2024, approximately **3× the OECD average**.
- Suicide is the **leading cause of death** for Koreans aged **10 to 49**.

ARCEUS was built to stand beside those suffering from loneliness and disconnection — offering a consistent, empathetic presence through technology.

---

## Key Features

- **Facial Emotion Detection** — A proprietary geometric algorithm extracts 5 facial landmarks (eyes, nose, mouth corners) and measures positional ratios and drooping of mouth corners against an individual baseline to assess sadness. Happiness and anger are detected via a pre-trained ONNX model using probability scores.
- **Natural Language Processing** — Offline STT combined with a lightweight local LLM enables natural conversation without an internet connection. An NLP speech emotion keyword classifier achieves **88% accuracy**.
- **Emotion-Aware Responses** — Adaptive responses are triggered based on detected emotional state, progressing through stages: detection → talking → empathy → dopamine release → mood recovery → leaving.
- **OLED Expression Output** — 15 customizable actuator expressions for natural, intuitive emotional communication via an OLED display.
- **Dual Raspberry Pi Architecture** — Parallel processing distributes computational load:
  - **Pi 5**: Global model inference, NLP, and speech tone generation
  - **Pi 4**: OLED expression output and actuator control
- **Privacy-First Design** — Image capture capabilities have been removed for public safety. Conversation data is stored only temporarily for context preservation.
- **Private Server & Manual Control** — Server hosting for monitoring, including critical suicidal area markup support.
- **Safe for All Ages** — Designed to be safe and approachable for children.

---

## Solution Process

```
DETECTION → TALKING → EMPATHY → DOPAMINE RELEASE → MOOD MAKING → LEAVING
   01            02         03            04               05           06
```

1. **Detection** — Identifies individuals showing signs of sadness
2. **Talking** — Initiates conversation with the detected person
3. **Empathy** — Provides empathetic responses
4. **Dopamine Release** — Engages in mood-lifting interaction
5. **Mood Making** — Supports recovery to a positive emotional state
6. **Leaving** — Gently disengages after mood improvement

---

## System Architecture

### Hardware

| Component | Role |
|-----------|------|
| Raspberry Pi 5 | Global model inference, NLP, speech tone generation |
| Raspberry Pi 4 | OLED expression output, actuator control |
| MG996R Servo Motors | Customized actuator expressions (15 expressions) |
| TCA9548A I²C Switch | Multi-device hardware communication |
| OLED Display | Real-time emotion visualization |

> Arms are based on the open-source **Poppy Humanoid Robot** platform.

### Software Stack

| Layer | Technology |
|-------|------------|
| Emotion Detection | Geometric facial landmark algorithm + ONNX pre-trained model |
| Speech-to-Text | Offline STT |
| Language Model | Lightweight local LLM (no internet required) |
| NLP Classification | Speech emotion keyword classifier (88% accuracy) |
| 3D Modeling | Shapr3D |
| 3D Slicing | Ultimaker Cura |
| Remote Access | PuTTY (SSH), RealVNC |
| IDE | Thonny |
| OS | Raspberry Pi OS |

### Performance

| Module | Accuracy |
|--------|----------|
| Emotion Detection (EG) | **89.3%** |
| NLP (Speech Emotion) | **88.0%** |

---

## Repository Structure

```
ARCEUS/
├── Code/               # Main robot control and inference code
├── ANG DATA/           # Anger detection model data
├── CIRCUIT DIAGRAM/    # Hardware wiring and circuit schematics
├── GCODE/              # 3D printing G-code files for ARCEUS body
├── URDF/               # Robot URDF model for simulation
├── LICENSE             # GPL-3.0 License
└── README.md
```

---

## 3D Printing

ARCEUS's physical body is fully open-source and 3D printable.

- **3D Modeling Tool**: Shapr3D
- **Slicer**: Ultimaker Cura
- **Printer**: Creality Ender V3 SE
- **Files provided**: ready-to-print `.gcode` files (see `/GCODE`)

---

## Open-Source Components

ARCEUS is built entirely on open-source hardware and software:

1. Hardware is open-source and clonable (TCA9548A module)
2. Actuator configurations for MG996R Servo motors — available in this repo
3. Both arms are based on the open-source [Poppy Humanoid Robot](https://www.poppy-project.org/)
4. OLED eye expressions are custom-designed — available in this repo
5. All software tools used are free: PuTTY, VNC, Shapr3D, Ultimaker Cura, Thonny, Raspberry Pi OS
6. Codebase built entirely on open-source Python packages
7. All pre-trained models used are open-source
8. Global model and all resources are available in this repository

---

## Getting Started

### Prerequisites

- Raspberry Pi 5 and Raspberry Pi 4
- Raspberry Pi OS installed on both devices
- Python 3.x
- Required Python packages (see `Code/` directory for dependencies)
- MG996R Servo motors and TCA9548A I²C multiplexer
- OLED display module

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/HASHIBUZZAMAN-BHUIYAN/ARCEUS.git
   cd ARCEUS
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Flash the G-code files to your 3D printer and print the robot body (see `/GCODE`).

4. Assemble the hardware following the circuit diagrams in `/CIRCUIT DIAGRAM`.

5. Deploy the code to the appropriate Pi:
   - Pi 5: global inference + NLP modules
   - Pi 4: OLED + actuator control modules

6. Load the URDF model from `/URDF` into your simulation environment (e.g., ROS/Gazebo) for virtual testing before hardware deployment.

---

## References

1. Texas Instruments. [TCA9548A Low-Voltage 8-Channel I²C Switch with Reset](https://www.ti.com/product/TCA9548A)
2. TowerPro. [MG996R High Torque Servo Motor Specifications](http://www.towerpro.com.tw/)
3. Poppy Project. [Poppy Humanoid Open-Source Robotics Platform](https://www.poppy-project.org/)
4. PuTTY. [Free SSH and Telnet Client](https://www.putty.org/)
5. RealVNC. [VNC Viewer Remote Access Software](https://www.realvnc.com/en/connect/download/viewer/)
6. Shapr3D. [3D CAD Modeling Software](https://www.shapr3d.com/)
7. UltiMaker. [Ultimaker Cura Slicing Software](https://ultimaker.com/software/ultimaker-cura/)
8. Thonny. [Python IDE for Beginners](https://thonny.org/)
9. Raspberry Pi Foundation. [Raspberry Pi OS](https://www.raspberrypi.com/software/)

---

## Team

| Role | Name |
|------|------|
| Creator | Bhuiyan Hashibuzzaman |
| Co-Creator | Abdyllaeva Bermet |
| Supervisor | Prof. Hwang Dong-ha |
| Team | HYDROXYCITRONELLAL |

---

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.

---

## Conclusion

기술만으로 고독을 해결할 수는 없습니다. 그러나 가장 힘든 날에도 곁에서 목소리를 들려줄 존재가 있다면, 아무도 혼자 그 시간을 견디지 않아도 됩니다.

*We cannot solve loneliness with technology alone. But we can make sure that on the hardest days, no one faces it without a voice beside them. Through every movement, every expression, every word it speaks, ARCEUS carries only one message: "I am with you, even when the world leaves you behind."*

---

*HYDROXYCITRONELLAL — where innovation meets the future*
