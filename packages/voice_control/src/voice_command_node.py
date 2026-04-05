#!/usr/bin/env python3
import rospy
import sounddevice as sd
from voice_control.msg import VoiceCommand
import azure.cognitiveservices.speech as speechsdk
from voice_control.utils import (VoiceSynthesis, AUDIO_DEVICE_INDEX, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION)


class VoiceCommandNode:
    """ROS node: USB mic → Azure STT → VoiceSynthesis → /voice_control/voice_cmd"""

    def __init__(self):
        rospy.init_node("voice_command_node")

        self._pub       = rospy.Publisher("/voice_control/voice_cmd",
                                          VoiceCommand, queue_size=10)
        self._synthesis = VoiceSynthesis()
        self._recognizer, self._push_stream = self._build_recognizer()
        self._mic = self._build_mic()

    # ── public ───────────────────────────────────────────────────────────────

    def run(self):
        self._recognizer.start_continuous_recognition()
        self._mic.start()
        rospy.loginfo("voice_command_node ready — listening")
        rospy.spin()
        self._shutdown()

    # ── private ──────────────────────────────────────────────────────────────

    def _build_recognizer(self):
        speech_cfg = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION
        )
        speech_cfg.speech_recognition_language = "en-US"

        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_cfg   = speechsdk.audio.AudioConfig(stream=push_stream)
        recognizer  = speechsdk.SpeechRecognizer(speech_cfg, audio_cfg)
        recognizer.recognized.connect(self._on_recognized)
        return recognizer, push_stream

    def _build_mic(self):
        def _audio_cb(indata, *_):
            self._push_stream.write(bytes(indata))

        return sd.RawInputStream(
            samplerate=16000,
            channels=1,
            dtype="int16",
            device=AUDIO_DEVICE_INDEX,
            callback=_audio_cb,
            blocksize=3200
        )

    def _on_recognized(self, evt):
        text = evt.result.text.strip()
        if not text:
            return
        rospy.loginfo(f"[STT] {text}")

        cmd = self._synthesis.parse(text)
        if cmd is None:
            rospy.logwarn(f"[VoiceCommandNode] Could not parse: '{text}'")
            return

        rospy.loginfo(f"[CMD] {cmd}")
        self._pub.publish(self._to_msg(cmd))

    def _to_msg(self, d: dict) -> VoiceCommand:
        msg = VoiceCommand()
        msg.cmd    = d.get("cmd", "")
        msg.v      = float(d.get("v", 0.0))
        msg.omega  = float(d.get("omega", 0.0))
        msg.enable = bool(d.get("enable", False))
        msg.side   = d.get("side", "")
        return msg

    def _shutdown(self):
        self._mic.stop()
        self._recognizer.stop_continuous_recognition()


if __name__ == "__main__":
    VoiceCommandNode().run()
