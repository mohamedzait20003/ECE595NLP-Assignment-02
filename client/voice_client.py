#!/usr/bin/env python3

import os
import time
import argparse
import requests
import threading
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

HEARTBEAT_INTERVAL = 1.0

# ── Load .env from project root ─────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

AZURE_SPEECH_KEY = os.environ["AZURE_SPEECH_KEY"]
AZURE_SPEECH_REGION = os.environ["AZURE_SPEECH_REGION"]


def start_heartbeat(bot_url: str, stop_event: threading.Event):
    def loop():
        while not stop_event.is_set():
            try:
                requests.get(f"{bot_url}/heartbeat", timeout=1)
            except requests.RequestException:
                pass
            time.sleep(HEARTBEAT_INTERVAL)
    threading.Thread(target=loop, daemon=True).start()


def send_text(bot_url: str, text: str):
    try:
        r = requests.post(f"{bot_url}/cmd", json={"text": text}, timeout=3)
    except requests.Timeout:
        print(f"  -> timeout contacting bot at {bot_url}")
        return
    except requests.RequestException as e:
        print(f"  -> cannot reach bot at {bot_url}: {e}")
        return

    try:
        data = r.json()
    except ValueError:
        print(f"  -> bot returned non-JSON ({r.status_code}): {r.text[:120]}")
        return

    status = data.get("status")
    if status == "ok":
        print(f"  -> bot executed: {data.get('cmd')}")
    elif status == "unrecognized":
        print(f"  -> bot could not parse: '{text}'")
    else:
        print(f"  -> bot error {r.status_code}: {data}")


def main():
    parser = argparse.ArgumentParser(description="Voice client for Duckiebot")
    parser.add_argument("--bot", required=True,
                        help="Duckiebot URL, e.g. http://zaitounsbot.local:9090")
    parser.add_argument("--device", type=int, default=None,
                        help="Audio input device index (run with --list-devices to see)")
    parser.add_argument("--list-devices", action="store_true",
                        help="List audio devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    bot_url = args.bot.rstrip("/")
    if not bot_url.startswith(("http://", "https://")):
        bot_url = "http://" + bot_url

    # Check bot connectivity
    try:
        r = requests.get(f"{bot_url}/health", timeout=3)
        r.raise_for_status()
        print(f"Bot connected: {r.json()}")
    except requests.RequestException as e:
        print(f"WARNING: Cannot reach bot at {bot_url} ({e}) — commands will fail")

    # Azure STT setup
    speech_cfg = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION
    )
    speech_cfg.speech_recognition_language = "en-US"

    push_stream = speechsdk.audio.PushAudioInputStream()
    audio_cfg = speechsdk.audio.AudioConfig(stream=push_stream)
    recognizer = speechsdk.SpeechRecognizer(speech_cfg, audio_cfg)

    def on_recognized(evt):
        text = evt.result.text.strip()
        if not text:
            return
        print(f"[STT] {text}")
        send_text(bot_url, text)

    def on_recognizing(evt):
        partial = evt.result.text.strip()
        if partial:
            print(f"[...] {partial}", end="\r")

    def on_canceled(evt):
        print(f"[STT canceled] reason={evt.reason} error={evt.error_details}")

    def on_session_started(_evt):
        print("[STT] session started")

    def on_session_stopped(_evt):
        print("[STT] session stopped")

    recognizer.recognized.connect(on_recognized)
    recognizer.recognizing.connect(on_recognizing)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_started.connect(on_session_started)
    recognizer.session_stopped.connect(on_session_stopped)

    last_level_print = [0.0]

    def audio_cb(indata, *_):
        push_stream.write(bytes(indata))
        now = time.time()
        if now - last_level_print[0] > 1.0:
            samples = np.frombuffer(indata, dtype=np.int16)
            if samples.size:
                rms = int(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
                print(f"[mic level] rms={rms}", end="\r")
            last_level_print[0] = now

    # Resolve the selected input device and print it so the user can confirm.
    try:
        dev_info = sd.query_devices(args.device, "input")
        print(f"Mic device: [{dev_info.get('index', '?')}] {dev_info['name']} "
              f"(default_sr={dev_info['default_samplerate']})")
    except Exception as e:
        print(f"WARNING: could not query input device {args.device}: {e}")

    mic = sd.RawInputStream(
        samplerate=16000,
        channels=1,
        dtype="int16",
        device=args.device,
        callback=audio_cb,
        blocksize=3200,
    )

    recognizer.start_continuous_recognition()
    mic.start()

    heartbeat_stop = threading.Event()
    start_heartbeat(bot_url, heartbeat_stop)

    print(f"Listening on mic (device={args.device}) — speak commands, Ctrl+C to quit")
    print(f"Sending to {bot_url}")

    try:
        while True:
            sd.sleep(100)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        heartbeat_stop.set()
        mic.stop()
        recognizer.stop_continuous_recognition()


if __name__ == "__main__":
    main()
