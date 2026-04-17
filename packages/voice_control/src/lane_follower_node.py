#!/usr/bin/env python3
"""Central driving controller. Only this node publishes to the wheels.

Priority system:
  1. Voice commands (highest) — set the driving mode/action
  2. Obstacles — pause movement until cleared or command changes
  3. Traffic lights — pause movement, voice can override
  4. Lane following — runs when voice says "follow lane"
"""

import rospy
from cv_bridge import CvBridge
from voice_control.msg import VoiceCommand
from duckietown_msgs.msg import Twist2DStamped
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String, Bool
from voice_control.utils import detect_lane, KP, KD, DEFAULT_SPEED, HEARTBEAT_TIMEOUT


class LaneFollowerNode:
    def __init__(self):
        rospy.init_node("lane_follower_node")

        self.bridge = CvBridge()

        # Driving state set by voice commands
        self.mode = "idle"        # idle | forward | turn | reverse | lane_follow | pass
        self.target_speed = DEFAULT_SPEED
        self.target_omega = 0.0
        self.prev_error = 0.0
        self.last_cmd_time = rospy.Time.now()

        # External blockers
        self.obstacle_blocked = False
        self.traffic_light = "none"  # "red", "yellow", "green", "none"

        self.pub = rospy.Publisher(
            "/duckiebot/wheels_driver_node/wheels_cmd",
            Twist2DStamped, queue_size=1
        )

        # Subscriptions
        rospy.Subscriber("/voice_control/voice_cmd", VoiceCommand, self.on_voice)
        rospy.Subscriber("/duckiebot/camera_node/image/compressed", CompressedImage, self.on_image)
        rospy.Subscriber("/voice_control/traffic_light", String, self.on_traffic_light)
        rospy.Subscriber("/voice_control/obstacle", Bool, self.on_obstacle)

        self.timer = rospy.Timer(rospy.Duration(0.1), self.heartbeat_check)
        rospy.loginfo("Lane Follower Node Initialized")
        rospy.spin()

    # ── Voice commands (highest priority) ────────────────────────────────────

    def on_voice(self, msg):
        self.last_cmd_time = rospy.Time.now()

        if msg.cmd == "stop":
            self.mode = "idle"
            self._send(0.0, 0.0)
            rospy.loginfo("Voice: STOP")

        elif msg.cmd == "forward":
            self.mode = "forward"
            self.target_speed = msg.v if msg.v > 0 else DEFAULT_SPEED
            if not self._is_blocked():
                self._send(self.target_speed, 0.0)
            rospy.loginfo(f"Voice: FORWARD at {self.target_speed}")

        elif msg.cmd == "turn":
            self.mode = "turn"
            self.target_speed = msg.v
            self.target_omega = msg.omega
            if not self._is_blocked():
                self._send(self.target_speed, self.target_omega)
            rospy.loginfo(f"Voice: TURN omega={self.target_omega}")

        elif msg.cmd == "reverse":
            self.mode = "reverse"
            self.target_speed = msg.v if msg.v > 0 else DEFAULT_SPEED
            # Obstacles behind are not detected, so just go
            self._send(-self.target_speed, 0.0)
            rospy.loginfo(f"Voice: REVERSE at {self.target_speed}")

        elif msg.cmd == "lane_follow":
            if msg.enable:
                self.mode = "lane_follow"
                self.target_speed = msg.v if msg.v > 0 else DEFAULT_SPEED
                rospy.loginfo("Voice: LANE FOLLOW ON")
            else:
                self.mode = "idle"
                self._send(0.0, 0.0)
                rospy.loginfo("Voice: LANE FOLLOW OFF")

        elif msg.cmd == "pass":
            self._do_pass(msg.side)

    # ── Obstacle (can pause forward/turn movement) ───────────────────────────

    def on_obstacle(self, msg):
        was_blocked = self.obstacle_blocked
        self.obstacle_blocked = msg.data

        if msg.data and not was_blocked:
            # Obstacle appeared — stop if moving forward or turning
            if self.mode in ("forward", "turn", "lane_follow"):
                self._send(0.0, 0.0)
                rospy.logwarn("Obstacle — pausing movement")

        elif not msg.data and was_blocked:
            # Obstacle cleared — resume current command
            rospy.loginfo("Obstacle cleared — resuming")
            self._resume()

    # ── Traffic light (can pause, but voice overrides) ───────────────────────

    def on_traffic_light(self, msg):
        prev = self.traffic_light
        self.traffic_light = msg.data

        if msg.data in ("red", "yellow") and prev not in ("red", "yellow"):
            if self.mode in ("forward", "lane_follow"):
                self._send(0.0, 0.0)
                rospy.logwarn(f"Traffic light {msg.data} — pausing")

        elif msg.data in ("green", "none") and prev in ("red", "yellow"):
            if not self.obstacle_blocked:
                rospy.loginfo("Traffic light clear — resuming")
                self._resume()

    # ── Lane following (camera callback) ─────────────────────────────────────

    def on_image(self, msg):
        if self.mode != "lane_follow" or self._is_blocked():
            return

        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        lateral_err, heading_err = detect_lane(frame)
        if lateral_err is None:
            return

        omega = -(KP * lateral_err + KD * (lateral_err - self.prev_error))
        self.prev_error = lateral_err
        self._send(self.target_speed, omega)

    # ── Heartbeat ────────────────────────────────────────────────────────────

    def heartbeat_check(self, _event):
        if self.mode != "idle":
            dt = (rospy.Time.now() - self.last_cmd_time).to_sec()
            if dt > HEARTBEAT_TIMEOUT:
                rospy.logwarn("Heartbeat timeout — stopping")
                self.mode = "idle"
                self._send(0.0, 0.0)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _is_blocked(self):
        if self.obstacle_blocked:
            return True
        if self.traffic_light in ("red", "yellow") and self.mode != "idle":
            return True
        return False

    def _resume(self):
        """Re-apply the current voice command after a blocker clears."""
        if self._is_blocked():
            return
        if self.mode == "forward":
            self._send(self.target_speed, 0.0)
        elif self.mode == "turn":
            self._send(self.target_speed, self.target_omega)
        elif self.mode == "reverse":
            self._send(-self.target_speed, 0.0)
        # lane_follow resumes automatically via on_image

    def _do_pass(self, side):
        sign = 1.0 if side == "left" else -1.0
        steps = [
            (0.3, self.target_speed,  sign * 2.0),
            (0.8, self.target_speed,  0.0),
            (0.3, self.target_speed, -sign * 2.0),
        ]
        for duration, v, omega in steps:
            self._send(v, omega)
            rospy.sleep(duration)
        self.mode = "lane_follow"

    def _send(self, v, omega):
        msg = Twist2DStamped()
        msg.v = v
        msg.omega = omega
        self.pub.publish(msg)


if __name__ == "__main__":
    LaneFollowerNode()
