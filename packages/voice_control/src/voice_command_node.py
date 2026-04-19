#!/usr/bin/env python3
"""ROS node: HTTP server that receives recognized speech text from a remote
client, parses it into a robot command, and publishes to /voice_control/voice_cmd."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import rospy
from voice_control.msg import VoiceCommand
from voice_control.utils import VoiceSynthesis

_publisher = None
_synthesis = None


class _Handler(BaseHTTPRequestHandler):
    """POST /cmd  — receives {"text": "go forward"}, parses, publishes.
       GET  /health — liveness check."""

    def do_POST(self):
        if self.path != "/cmd":
            self._respond(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "invalid json"})
            return

        text = body.get("text", "").strip()
        if not text:
            self._respond(400, {"error": "empty text"})
            return

        rospy.loginfo(f"[HTTP] received: '{text}'")

        cmd = _synthesis.parse(text)
        if cmd is None:
            rospy.logwarn(f"[HTTP] could not parse: '{text}'")
            self._respond(200, {"status": "unrecognized", "text": text})
            return

        msg = VoiceCommand()
        msg.cmd = cmd.get("cmd", "")
        msg.v = float(cmd.get("v", 0.0))
        msg.omega = float(cmd.get("omega", 0.0))
        msg.enable = bool(cmd.get("enable", False))
        msg.side = cmd.get("side", "")

        _publisher.publish(msg)
        rospy.loginfo(f"[CMD] {cmd}")
        self._respond(200, {"status": "ok", "cmd": cmd})

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "node": "voice_command_node"})
        elif self.path == "/heartbeat":
            msg = VoiceCommand()
            msg.cmd = "heartbeat"
            _publisher.publish(msg)
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        rospy.logdebug(fmt % args)


def main():
    global _publisher, _synthesis
    rospy.init_node("voice_command_node")

    _publisher = rospy.Publisher(
        "/voice_control/voice_cmd", VoiceCommand, queue_size=10
    )
    _synthesis = VoiceSynthesis()

    port = rospy.get_param("~port", 8080)
    server = HTTPServer(("0.0.0.0", port), _Handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rospy.loginfo(f"voice_command_node listening on 0.0.0.0:{port}")

    rospy.spin()
    server.shutdown()


if __name__ == "__main__":
    main()
