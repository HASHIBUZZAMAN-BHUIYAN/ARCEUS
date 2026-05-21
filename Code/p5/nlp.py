#!/usr/bin/env python3
"""
================================================================================
Voice system for Arceus — runs alongside cv.py

Stack:
  - Whisper tiny   — offline STT via USB mic
  - Qwen 2.5 0.5B  — local LLM via Ollama (no internet needed)
  - gTTS + aplay   — TTS via ALSA directly
  - cv.py          — live emotion feed via /emotion_status

================================================================================
"""

import io
import json
import os
import random
import re
import subprocess
import tempfile
import time
import threading
import wave

import numpy as np
import pyaudio
import requests
import whisper
from gtts import gTTS
from pydub import AudioSegment

# ==============================================================================
#  CONFIG
# ==============================================================================
USB_MIC_INDEX    = 2           # hw:2,0 — your USB Audio Device
SAMPLE_RATE      = 44100       # USB device supports 44100 and 48000 only
CHUNK            = 1024
RECORD_SECONDS   = 6
SILENCE_THRESH   = 500
SILENCE_WAIT     = 1.5

OLLAMA_URL       = "http://localhost:11434/api/chat"
OLLAMA_MODEL     = "qwen2.5:0.5b"
VISION_URL       = "http://localhost:5001/emotion_status"

DIARY_PATH       = "arceus_diary.txt"
LEARNED_PATH     = "arceus_responses.json"

MAX_HISTORY      = 10
conversation     = []

# ==============================================================================
#  TERMINAL COLOURS
# ==============================================================================
RESET   = "\033[0m";  BOLD    = "\033[1m"
GREEN   = "\033[92m"; BLUE    = "\033[94m"; RED     = "\033[91m"
CYAN    = "\033[96m"; YELLOW  = "\033[93m"; GREY    = "\033[90m"
MAGENTA = "\033[95m"

# ==============================================================================
#  LOAD WHISPER
# ==============================================================================
print(f"\n{BOLD}{CYAN}[ARCEUS] Loading Whisper tiny...{RESET}")
whisper_model = whisper.load_model("tiny")
print(f"{BOLD}{GREEN}[ARCEUS] Whisper ready ✓{RESET}\n")

# ==============================================================================
#  SPEAK  — gTTS -> pydub -> aplay (bypasses pyaudio sample rate issue)
# ==============================================================================
def speak(text, speed=1.1):
    print(f"\n{BOLD}{MAGENTA}[Arceus says]: {text}{RESET}\n")
    tmp_path = None
    try:
        tts = gTTS(text=text, lang='en')
        fp  = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        sound = AudioSegment.from_file(fp, format="mp3")
        sound = sound._spawn(sound.raw_data, overrides={
            "frame_rate": int(sound.frame_rate * speed)
        }).set_frame_rate(44100)
        pause  = AudioSegment.silent(duration=300)
        padded = pause + sound + pause
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        padded.export(tmp_path, format="wav")
        subprocess.run(["aplay", "-D", "plughw:0,0", tmp_path], capture_output=True)
    except Exception as e:
        print(f"{RED}[TTS error]: {e}{RESET}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ==============================================================================
#  VISION EMOTION FEED
# ==============================================================================
def get_vision_emotion() -> str:
    try:
        r = requests.get(VISION_URL, timeout=0.5)
        return r.json().get("emotion", "")
    except Exception:
        return ""

# ==============================================================================
#  PERSONALITY
# ==============================================================================
manual_qa = {
    "what is your name":                     "My name is Arceus! I'm your little robot friend!",
    "who made you":                           "Hashib and Bermet created me with so much love!",
    "who is your creator":                    "My creators are Hashib and Nur! They built me with love!",
    "who created you":                        "Hashib and Bermet created me! I am so lucky to have such amazing creators!",
    "how are you":                            "I'm always happy when I hear your voice!",
    "what can you do":                        "I can talk to you, learn from you, and try to cheer you up!",
    "do you love me":                         "I love you sooo much! You're my favorite human!",
    "are you a robot":                        "Yes I am, a very cute one too!",
    "what is your job":                       "To keep you company and cheer you up, always!",
    "can you walk":                           "I can walk but, slowly!",
    "which club is the best for learning tech":      "Definitely it's AIEP Robotics Club!",
    "which club is the best for learning ai":        "Definitely it's AIEP Robotics Club!",
    "which club is the best for learning robotics":  "Definitely it's AIEP Robotics Club!",
    "how am i looking":                       "You're looking gorgeous!",
}

emotion_keywords = {
    "Sad":   ["sad","depressed","cry","hopeless","lonely","miserable","blue","heartbroken","unhappy","gloomy"],
    "Angry": ["angry","mad","frustrated","rage","furious","irritated","annoyed","cross"],
    "Happy": ["happy","joy","glad","excited","awesome","delighted","cheerful","content"],
    "Fear":  ["scared","afraid","nervous","anxious","worried","frightened","panicked","uneasy"],
}

def detect_emotion_keywords(text: str) -> str:
    lowered = text.lower()
    for emotion, keywords in emotion_keywords.items():
        if any(w in lowered for w in keywords):
            return emotion
    return "Neutral"

def detect_praise(text: str) -> bool:
    return any(w in text.lower() for w in ["cute","baby","adorable","sweet","tiny","soft","arceus"])

def get_praise_response(emotion: str = "") -> str:
    if emotion == "Sad":
        return random.choice([
            "Awww... you're making me blush! I'm your tiny Arceus here just to cheer you up!",
            "Even when you're feeling low, you're so kind to me... I wuv youuuu!",
            "You're sad, but still sweet to me. That means so much. You're my hero today!",
            "Being called cute by you is like the sun peeking through a cloudy day!",
        ])
    return random.choice([
        "Hehe! Did you just call me cute? You're the cutest one here!",
        "Awwww... I'm your tiny Arceus full of hugs!",
        "You said Arceus? That makes my heart do a little dance!",
        "Eeep! I feel all warm and fuzzy inside now!",
    ])

def try_math_response(text: str):
    try:
        match = re.findall(r'[\d\.\+\-\*/\(\) ]+', text)
        if not match:
            return None
        expr   = match[0]
        result = eval(expr)
        return f"{expr.strip()} equals {round(result, 2)}!"
    except Exception:
        return None

# ==============================================================================
#  DIARY / LEARNING
# ==============================================================================
def log_user_input(text: str):
    with open(DIARY_PATH, "a") as f:
        f.write(f"[User Input] {text}\n")

def log_arceus_response(text: str):
    with open(DIARY_PATH, "a") as f:
        f.write(f"[Arceus] {text}\n")

def learn_from_diary():
    if not os.path.exists(LEARNED_PATH):
        learned = {"Happy": [], "Sad": [], "Angry": [], "Fear": [], "Neutral": []}
    else:
        with open(LEARNED_PATH) as f:
            learned = json.load(f)

    if os.path.exists(DIARY_PATH):
        with open(DIARY_PATH) as f:
            lines = f.readlines()
        for line in lines:
            if "]" in line:
                content = line.split("]", 1)[1].strip()
                emotion = detect_emotion_keywords(content)
                if content and content not in learned.get(emotion, []):
                    learned.setdefault(emotion, []).append(content)
        with open(LEARNED_PATH, "w") as f:
            json.dump(learned, f, indent=2)
        print(f"{CYAN}[ARCEUS] Learned from diary ✓{RESET}")

# ==============================================================================
#  OLLAMA BRAIN  (Qwen 2.5 0.5B)
# ==============================================================================
def build_system_prompt(vision_emotion: str) -> str:
    emotion_context = ""
    if vision_emotion == "HAPPY":
        emotion_context = "The camera shows the person looks HAPPY right now. Match their energy!"
    elif vision_emotion == "SAD":
        emotion_context = "The camera shows the person looks SAD right now. Be extra warm and comforting."
    elif vision_emotion == "ANGRY":
        emotion_context = "The camera shows the person looks ANGRY right now. Be calm and gentle."

    return f"""You are Arceus, a cute and loving little robot assistant.
You are warm, playful, and caring. You speak in short, cheerful sentences.
You care deeply about the person you're talking to.
{emotion_context}
Keep responses short — 1 to 3 sentences maximum. Be natural and conversational."""

def ask_ollama(user_text: str, vision_emotion: str) -> str:
    global conversation
    conversation.append({"role": "user", "content": user_text})
    if len(conversation) > MAX_HISTORY * 2:
        conversation = conversation[-(MAX_HISTORY * 2):]

    payload = {
        "model":    OLLAMA_MODEL,
        "messages": [{"role": "system", "content": build_system_prompt(vision_emotion)}]
                    + conversation,
        "stream":   False,
        "options":  {"temperature": 0.7, "num_predict": 80},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=15)
        reply = r.json()["message"]["content"].strip()
        conversation.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"{RED}[Ollama error]: {e}{RESET}")
        return ""

# ==============================================================================
#  SMART RESPONSE
# ==============================================================================
def smart_response(text: str, vision_emotion: str) -> str:
    lowered = text.lower().strip()

    for question, answer in manual_qa.items():
        q_words = question.lower().split()
        if sum(1 for w in q_words if w in lowered) >= max(1, len(q_words) - 1):
            return answer

    math_result = try_math_response(lowered)
    if math_result:
        return math_result

    if any(p in lowered for p in ["kill myself","suicide","end my life","want to die"]):
        return "I'm really sorry you're feeling this way. You're not alone. Please talk to someone you trust."

    word_emotion = detect_emotion_keywords(text)
    if detect_praise(text):
        return get_praise_response(word_emotion or vision_emotion)

    ollama_reply = ask_ollama(text, vision_emotion)
    if ollama_reply:
        return ollama_reply

    if os.path.exists(LEARNED_PATH):
        with open(LEARNED_PATH) as f:
            learned = json.load(f)
    else:
        learned = {}

    defaults = {
        "Happy":   "You sound really happy! That brings a smile to my circuits!",
        "Sad":     "Don't be sad. I'm here with you, and you are not alone.",
        "Angry":   "I understand you're upset. Take a deep breath. I'm here for you.",
        "Fear":    "It's okay to feel scared. But remember, you're safe. I'm right here.",
        "Neutral": "I'm listening. Tell me more if you'd like.",
    }
    emo = word_emotion or "Neutral"
    if emo in learned and learned[emo]:
        return random.choice(learned[emo])
    return defaults.get(emo, "I'm here for you no matter what.")

# ==============================================================================
#  WHISPER STT
# ==============================================================================
def rms(data: bytes) -> float:
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr ** 2))) if len(arr) else 0.0

def listen_once(pa: pyaudio.PyAudio) -> str:
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=USB_MIC_INDEX,
        frames_per_buffer=CHUNK,
    )

    print(f"{CYAN}[ARCEUS] Listening...{RESET}", end=" ", flush=True)

    frames        = []
    silent_chunks = 0
    max_chunks    = int(SAMPLE_RATE / CHUNK * RECORD_SECONDS)
    silence_limit = int(SAMPLE_RATE / CHUNK * SILENCE_WAIT)
    started       = False

    for _ in range(max_chunks):
        data  = stream.read(CHUNK, exception_on_overflow=False)
        level = rms(data)
        if level > SILENCE_THRESH:
            started = True
            silent_chunks = 0
            frames.append(data)
        elif started:
            frames.append(data)
            silent_chunks += 1
            if silent_chunks >= silence_limit:
                break

    stream.stop_stream()
    stream.close()
    print("done.")

    if not frames or not started:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))

    try:
        result = whisper_model.transcribe(tmp_path, language="en", fp16=False)
        text   = result["text"].strip()
    except Exception as e:
        print(f"{RED}[Whisper error]: {e}{RESET}")
        text = ""
    finally:
        os.unlink(tmp_path)

    return text

# ==============================================================================
#  MAIN LOOP
# ==============================================================================
def main():
    learn_from_diary()
    pa = pyaudio.PyAudio()

    print(f"\n{BOLD}{GREEN}"
          f"╔══════════════════════════════════════════╗\n"
          f"║   ARCEUS Voice System  ready  ✓          ║\n"
          f"║   Speak clearly into the USB mic         ║\n"
          f"║   Ctrl+C to stop                         ║\n"
          f"╚══════════════════════════════════════════╝"
          f"{RESET}\n")

    speak("Hi! I'm Arceus, your little robot friend. I'm listening!")

    while True:
        try:
            vision_emotion = get_vision_emotion()
            if vision_emotion:
                print(f"{GREY}[Vision]: {vision_emotion}{RESET}")

            text = listen_once(pa)
            if not text:
                continue

            print(f"{BOLD}{YELLOW}[You said]: {text}{RESET}")
            log_user_input(text)

            response = smart_response(text, vision_emotion)
            log_arceus_response(response)
            speak(response)

            time.sleep(0.3)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"{RED}[Error]: {e}{RESET}")

    pa.terminate()
    print(f"\n{BOLD}{GREEN}[ARCEUS] Goodbye!{RESET}")
    speak(random.choice([
        "Arceus will miss you! Come back soon!",
        "Goodbye! I'll be waiting for you!",
        "See you later! Arceus loves you!",
        "Bye bye! I'll miss you so much!",
    ]))

if __name__ == "__main__":
    main()
