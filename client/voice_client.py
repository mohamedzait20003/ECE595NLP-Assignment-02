#!/usr/bin/env python3
"""Laptop-side voice client: mic -> Azure STT -> HTTP POST text to Duckiebot."""

import os
import argparse
import requests
import sounddevice as sd
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# ── Load .env from project root ─────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

AZURE_SPEECH_KEY = os.environ["AZURE_SPEECH_KEY"]
AZURE_SPEECH_REGION = os.environ["AZURE_SPEECH_REGION"]


def send_text(bot_url: str, text: str):
    try:
        r = requests.post(f"{bot_url}/cmd", json={"text": text}, timeout=3)
        data = r.json()
        if data.get("status") == "ok":
            print(f"  -> bot executed: {data.get('cmd')}")
        elif data.get("status") == "unrecognized":
            print(f"  -> bot could not parse: '{text}'")
        else:
            print(f"  -> bot error: {r.status_code} {r.text}")
    except requests.ConnectionError:
        print(f"  -> cannot reach bot at {bot_url}")


def main():
    parser = argparse.ArgumentParser(description="Voice client for Duckiebot")
    parser.add_argument("--bot", required=True,
                        help="Duckiebot URL, e.g. http://zaitounsbot.local:8080")
    parser.add_argument("--device", type=int, default=None,
                        help="Audio input device index (run with --list-devices to see)")
    parser.add_argument("--list-devices", action="store_true",
                        help="List audio devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    bot_url = args.bot.rstrip("/")

    # Check bot connectivity
    try:
        r = requests.get(f"{bot_url}/health", timeout=3)
        print(f"Bot connected: {r.json()}")
    except requests.ConnectionError:
        print(f"WARNING: Cannot reach bot at {bot_url} — commands will fail")

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

    recognizer.recognized.connect(on_recognized)

    def audio_cb(indata, *_):
        push_stream.write(bytes(indata))

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
    print(f"Listening on mic (device={args.device}) — speak commands, Ctrl+C to quit")
    print(f"Sending to {bot_url}")

    try:
        while True:
            sd.sleep(100)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        mic.stop()
        recognizer.stop_continuous_recognition()


if __name__ == "__main__":
    main()
