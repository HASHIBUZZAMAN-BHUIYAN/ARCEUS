#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════

STACK:
  • YuNet_Compressed  – OpenCV neural face detector (1082 MB ONNX, 3 landmarks,
                    much more accurate + stable than Haar cascade)
  • CSRT Tracker  – locks onto face between detection frames (no jumps)
  • HSEmotion     – EfficientNet-B0 trained on AffectNet-8 (ONNX, accurate)

3 FLAGS:
  HAPPY    – happiness
  SAD      – sadness
  ANGRY    – anger

Port: 5001
════════════════════════════════════════════════════════════════════════════════
"""

import os, time, threading, urllib.request
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request
from picamera2 import Picamera2

# HSEmotion (pip install hsemotion-onnx)
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

# ══════════════════════════════════════════════════════════════════════════════
#  TERMINAL COLOURS
# ══════════════════════════════════════════════════════════════════════════════
RESET   = "\033[0m";  BOLD    = "\033[1m"
GREEN   = "\033[92m"; BLUE    = "\033[94m"; RED  = "\033[91m"
CYAN    = "\033[96m"; MAGENTA = "\033[95m"; GREY = "\033[90m"; YELLOW = "\033[93m"
ORANGE  = "\033[38;5;214m"

FLAG_TERM = {
    "HAPPY":    f"{BOLD}{GREEN}",
    "SAD":      f"{BOLD}{MAGENTA}",
    "ANGRY":    f"{BOLD}{RED}",
    "NO FACE":  f"{GREY}",
}
# BGR tuples — frame goes through COLOR_BGR2RGB before encode
# so (B,G,R) stored → browser sees (R,G,B) correctly
# index.html: HAPPY=#1aff1a  SAD=#f600f6  ANGRY=#ff1a1a
FLAG_BGR = {
    "HAPPY":  (26,  255,  26),   # #1aff1a bright green
    "SAD":    (246,   0, 246),   # #f600f6 magenta
    "ANGRY":  (255,  26,  26),   # #ff1a1a bright red
    "NO FACE":(160, 160, 160),
}

# ══════════════════════════════════════════════════════════════════════════════
#  YUNET FACE DETECTOR  (OpenCV neural detector — replaces Haar)
#  Returns bounding box + 5 landmarks: right-eye, left-eye, nose,
#                                       right-mouth, left-mouth
# ══════════════════════════════════════════════════════════════════════════════
MODEL_DIR   = Path(__file__).parent / "models"
YUNET_PATH  = MODEL_DIR / "yunet.onnx"
YUNET_URL   = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)

def ensure_yunet():
    if YUNET_PATH.exists():
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n{BOLD}{CYAN}[LUMI] Downloading YuNet face model (~400 KB)…{RESET}")
    urllib.request.urlretrieve(YUNET_URL, YUNET_PATH)
    print(f"{BOLD}{GREEN}[LUMI] YuNet saved → {YUNET_PATH}{RESET}\n")

# ══════════════════════════════════════════════════════════════════════════════
#  3-EMOTION MAPPING
#
#  ANGRY  →  model only 
#  HAPPY  →  model only 
#  SAD    →  lip droop geometry vs personal baseline
#
#  measure width reliably. Model handles happy/angry well already.
#
#  YuNet_Compressed landmarks: right_eye(0) left_eye(1) nose(2) right_mouth(3) left_mouth(4)
# ══════════════════════════════════════════════════════════════════════════════

IDX_ANGER = 0
IDX_HAPPY = 4

G_RE, G_LE, G_NOSE, G_RM, G_LM = 0, 1, 2, 3, 4

# ── Model thresholds ──────────────────────────────────────────────────────────
ANGRY_MIN = 0.25    # working great at 95%
HAPPY_MIN = 0.28    # low enough to catch real smiles

# ── Lip droop geometry (SAD) ──────────────────────────────────────────────────
SAD_DELTA  = 0.06   # drooped deviation above neutral baseline → SAD
CALIB_N    = 45     # frames to collect neutral baseline
EMA_ALPHA  = 0.015  # slow drift after calibration

_calib_buf      = []
_baseline       = None


def lip_droop(landmarks: list):
    """
    droop = (avg_mouth_corner_y − nose_y) / (nose_y − eye_y)
    Rises when mouth corners pull DOWN (sad).
    Compared against personal baseline learned during calibration.
    """
    if not landmarks or len(landmarks) < 5:
        return None
    eye_y   = (landmarks[G_RE][1] + landmarks[G_LE][1]) / 2.0
    nose_y  =  landmarks[G_NOSE][1]
    mouth_y = (landmarks[G_RM][1] + landmarks[G_LM][1]) / 2.0
    scale   = nose_y - eye_y
    if scale < 12:
        return None
    return (mouth_y - nose_y) / scale


def update_baseline(droop: float):
    global _baseline, _calib_buf
    if _baseline is None:
        _calib_buf.append(droop)
        remaining = CALIB_N - len(_calib_buf)
        if remaining > 0 and remaining % 15 == 0:
            print(f"{CYAN}[LUMI] Calibrating… {remaining} frames left{RESET}")
        if len(_calib_buf) >= CALIB_N:
            _baseline = float(np.median(_calib_buf))
            print(f"\n{BOLD}{GREEN}[LUMI] Baseline ready: {_baseline:.3f}"
                  f"  |  SAD > {_baseline + SAD_DELTA:.3f}{RESET}\n")
    else:
        if abs(droop - _baseline) < SAD_DELTA * 0.6:
            _baseline = (1 - EMA_ALPHA) * _baseline + EMA_ALPHA * droop
    return _baseline


def map_flag(emotion: str, scores: np.ndarray, landmarks: list) -> str:

    # ── GEOMETRY FIRST: lip droop overrides everything ────────────────────────
    # Sad expressions create facial tension that the model misreads as anger.
    # If geometry clearly says SAD, trust it over the model.
    droop = lip_droop(landmarks)
    if droop is not None:
        baseline = update_baseline(droop)
        if baseline is not None and droop > baseline + SAD_DELTA:
            return "SAD"

    # ── HAPPY: model ──────────────────────────────────────────────────────────
    if float(scores[IDX_HAPPY]) >= HAPPY_MIN:
        return "HAPPY"

    # ── ANGRY: model (only reached if geometry did not say SAD) ───────────────
    if float(scores[IDX_ANGER]) >= ANGRY_MIN:
        return "ANGRY"

    # ── Default: SAD ──────────────────────────────────────────────────────────
    return "SAD"
# ══════════════════════════════════════════════════════════════════════════════
#  TERMINAL PRINTER  (debounced — prints only on flag change)
# ══════════════════════════════════════════════════════════════════════════════
_prev_term = ""

def terminal_print(flag: str):
    global _prev_term
    if flag == _prev_term:
        return
    _prev_term = flag
    col   = FLAG_TERM.get(flag, RESET)
    label = "In Search of Human Face" if flag == "NO FACE" else flag
    bar   = "═" * 46
    print(f"\n{col}{bar}")
    print(f"   [LUMI]  ►  {label}")
    print(f"{bar}{RESET}\n")

# ══════════════════════════════════════════════════════════════════════════════
#  INIT  — models, camera, Flask
# ══════════════════════════════════════════════════════════════════════════════
ensure_yunet()

W, H = 640, 480

# YuNet detector
yunet = cv2.FaceDetectorYN.create(
    str(YUNET_PATH), "", (W, H),
    score_threshold=0.75,
    nms_threshold=0.30,
    top_k=1,                    # only the best face
)

# HSEmotion — EfficientNet-B0 trained on AffectNet-8
# model downloads to ~/.cache/hsemotion/ on first use (~16 MB)
print(f"{BOLD}{CYAN}[LUMI] Loading HSEmotion model…{RESET}")
emo_model = HSEmotionRecognizer(model_name='enet_b0_8_best_vgaf')
print(f"{BOLD}{GREEN}[LUMI] HSEmotion ready ✓{RESET}\n")

# Camera
picam2 = Picamera2()
picam2.configure(
    picam2.create_video_configuration(main={"size": (W, H), "format": "RGB888"})
)
picam2.start()
time.sleep(2)   # let AWB and AE settle before first frame

# Apply camera controls after start
controls = {
    "AwbEnable": True,
    "AeEnable":  True,
}
# Pi Camera Module 3 supports continuous autofocus — V2 does not, so try/except
try:
    af_controls = {**controls, "AfMode": 2, "AfSpeed": 1}
    picam2.set_controls(af_controls)
    print(f"{BOLD}{GREEN}[LUMI] Continuous autofocus enabled ✓{RESET}")
except Exception:
    picam2.set_controls(controls)
    print(f"{BOLD}{YELLOW}[LUMI] Fixed focus camera (Pi Cam V2) — no AF motor{RESET}")
    print(f"{YELLOW}       Tip: rotate the lens ring manually to sharpen focus{RESET}")

app       = Flask(__name__, template_folder="templates")
streaming = False
lock      = threading.Lock()
last_flag = "NO FACE"

# ══════════════════════════════════════════════════════════════════════════════
#  MJPEG FRAME GENERATOR
#
#  Frame strategy (keeps it fast):
#    Every DETECT_INT → YuNet detection  (~5 ms)  — update cached box
#    Between detects  → reuse last box   (~0 ms)  — smooth, no flicker
#    Every EMO_INT    → HSEmotion        (~25 ms) — emotion classification
# ══════════════════════════════════════════════════════════════════════════════
DETECT_INT   = 4     # re-run YuNet every N frames (4 = ~60 ms at 15fps, plenty)
EMO_INT      = 5     # run emotion every N frames

_fidx        = 0
_cached_flag = "NO FACE"
_track_box   = None   # (x, y, w, h) — last known face box
_track_ok    = False

def _yunet_detect(frame_bgr):
    """Run YuNet. Returns (x, y, w, h) or None."""
    _, faces = yunet.detect(frame_bgr)
    if faces is None or len(faces) == 0:
        return None
    f  = faces[0]
    x, y, w, h = int(f[0]), int(f[1]), int(f[2]), int(f[3])
    # clamp to frame
    x  = max(0, x); y = max(0, y)
    w  = min(w, W - x); h = min(h, H - y)
    return (x, y, w, h)

def _landmarks_from_yunet(faces_raw):
    """Extract 5 YuNet landmarks from raw detect output."""
    if faces_raw is None or len(faces_raw) == 0:
        return []
    f = faces_raw[0]
    # columns 4-13: x0,y0, x1,y1, x2,y2, x3,y3, x4,y4
    pts = []
    for i in range(5):
        px = int(f[4 + i * 2])
        py = int(f[5 + i * 2])
        pts.append((px, py))
    return pts

def _draw_overlay(frame, box, landmarks, flag):
    """
    No face  → subtle grey search bar at top only.
    Face     → coloured box + landmarks + clean pill label below box.
               No permanent top banner — less clutter.
    """
    col_bgr = FLAG_BGR.get(flag, (160, 160, 160))

    if box is None:
        # ── Searching bar (no face) ───────────────────────────────────────────
        bar = frame.copy()
        cv2.rectangle(bar, (0, 0), (W, 40), (15, 15, 15), -1)
        cv2.addWeighted(bar, 0.55, frame, 0.45, 0, frame)
        cv2.putText(frame, "In Search of Human Face",
                    (14, 27), cv2.FONT_HERSHEY_SIMPLEX,
                    0.60, (140, 140, 140), 1, cv2.LINE_AA)
        return frame

    x, y, w, h = box

    # ── Face rectangle ────────────────────────────────────────────────────────
    cv2.rectangle(frame, (x, y), (x + w, y + h), col_bgr, 2)

    # ── 5-point landmark mesh ─────────────────────────────────────────────────
    PAIRS = [(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)]
    for pt in landmarks:
        cv2.circle(frame, pt, 3, col_bgr, -1)
        cv2.circle(frame, pt, 3, (255, 255, 255), 1)
    for a, b in PAIRS:
        if a < len(landmarks) and b < len(landmarks):
            cv2.line(frame, landmarks[a], landmarks[b], col_bgr, 1, cv2.LINE_AA)

    # ── Pill label below (or above if near bottom) ────────────────────────────
    label = flag
    font       = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.65
    thickness  = 2
    (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
    px, py = 10, 5                    # horizontal / vertical pill padding
    lx = x                            # left-align with face box
    ly = y + h + 10                   # 10px below box

    if ly + th + py * 2 > H:          # not enough space below → go above
        ly = y - th - py * 2 - 6

    # Filled rounded pill background
    cv2.rectangle(frame,
                  (lx - px,      ly - py),
                  (lx + tw + px, ly + th + py),
                  col_bgr, -1, cv2.LINE_AA)
    # Dark text on coloured pill
    cv2.putText(frame, label,
                (lx, ly + th),
                font, font_scale, (15, 15, 15), thickness, cv2.LINE_AA)

    return frame

def gen_frames():
    global streaming, last_flag, _fidx, _cached_flag
    global _track_box, _track_ok

    yunet.detect(np.zeros((H, W, 3), np.uint8))  # warm up session
    cached_landmarks = []

    while True:
        with lock:
            active = streaming
        if not active:
            time.sleep(0.05)
            continue

        # ── Capture & orient ──────────────────────────────────────────────────
        raw   = picam2.capture_array()
        # picamera2 RGB888 → BGR for OpenCV processing
        frame = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
        frame = cv2.flip(frame, 1)

        _fidx += 1

        # ── YuNet face detection (every DETECT_INT frames, cached between) ────
        if _fidx % DETECT_INT == 0 or not _track_ok:
            _, faces_raw = yunet.detect(frame)
            box = _yunet_detect(frame)
            if box is not None:
                _track_box       = box
                cached_landmarks = _landmarks_from_yunet(faces_raw)
                _track_ok        = True
            else:
                _track_ok    = False
                _track_box   = None
                _cached_flag = "NO FACE"
                cached_landmarks = []
        # Between detections: _track_box keeps last known position (no flicker)

        # ── Emotion inference ─────────────────────────────────────────────────
        if _track_ok and _track_box is not None and _fidx % EMO_INT == 0:
            x, y, w, h = _track_box
            pad = 15
            x1  = max(0, x - pad); y1 = max(0, y - pad)
            x2  = min(W, x + w + pad); y2 = min(H, y + h + pad)
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                # HSEmotion expects BGR (same as OpenCV default)
                emotion, scores = emo_model.predict_emotions(roi, logits=False)
                _cached_flag = map_flag(emotion, scores, cached_landmarks)

        flag      = _cached_flag
        last_flag = flag
        terminal_print(flag)

        # ── Draw ──────────────────────────────────────────────────────────────
        frame = _draw_overlay(frame, _track_box, cached_landmarks, flag)

        # ── MJPEG chunk ───────────────────────────────────────────────────────
        # Convert BGR → RGB before JPEG encoding so browser sees correct colours
        frame_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ret, buf = cv2.imencode(".jpg", frame_out, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n"
               + buf.tobytes() + b"\r\n")

# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/control_stream", methods=["POST"])
def control_stream():
    global streaming
    cmd = request.get_json().get("command")
    with lock:
        streaming = (cmd == "start")
    return jsonify(status="ok", streaming=streaming)

@app.route("/emotion_status")
def emotion_status():
    """Voice-response hook: GET /emotion_status → {"emotion": "HAPPY"}"""
    return jsonify(emotion=last_flag)

@app.after_request
def add_cors(response):
    """Allow browser to call Pi 5 directly from any origin."""
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/nlp_feed")
def nlp_feed():
    """Return last 20 lines from arceus_diary.txt for web display."""
    try:
        diary = Path(__file__).parent / "arceus_diary.txt"
        if not diary.exists():
            return jsonify(entries=[])
        with open(diary, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        return jsonify(entries=lines[-20:])
    except Exception as e:
        return jsonify(entries=[], error=str(e))

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    streaming = False
    print(
        f"\n{BOLD}{GREEN}"
        f"╔══════════════════════════════════════════╗\n"
        f"║   Arceus  –  vision.py  ready  ✓           ║\n"
        f"║   http://0.0.0.0:5001                    ║\n"
        f"║   Press Z to view  |  C to stop        ║\n"
        f"╚══════════════════════════════════════════╝"
        f"{RESET}\n"
    )
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)