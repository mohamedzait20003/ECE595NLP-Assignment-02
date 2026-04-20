#!/usr/bin/env python3

import os
import math
import rospy
from cv_bridge import CvBridge
from std_msgs.msg import String, Bool
from voice_control.msg import VoiceCommand
from sensor_msgs.msg import CompressedImage
from duckietown_msgs.msg import Twist2DStamped
from voice_control.utils import (detect_lane, KP, KD, DEFAULT_SPEED, MAX_SPEED, MIN_SPEED, SPEED_STEP, HEARTBEAT_TIMEOUT, FORWARD_TRIM)

# Maneuver tuning constants
_UTURN_OMEGA = 3.5          # rad/s spin rate for U-turn
_CROSS_STEER_OMEGA = 1.8    # rad/s steer angle for lane cross
_CROSS_STEER_DUR = 0.5      # seconds steering into adjacent lane
_CROSS_STRAIGHT_DUR = 0.3   # seconds straightening in new lane

class LaneFollowerNode:
    def __init__(self):
        rospy.init_node("lane_follower_node")

        self.bridge = CvBridge()

        # Driving state set by voice commands
        self.mode = "idle"
        self.target_speed = DEFAULT_SPEED
        self.target_omega = 0.0
        self.prev_error = 0.0
        self.last_cmd_time = rospy.Time.now()

        # Wheel-trim counter-steer. Launch-file param wins; falls back to the
        # env-var default from utils.load_config.
        self.forward_trim = float(rospy.get_param("~forward_trim", FORWARD_TRIM))
        rospy.loginfo(f"forward_trim = {self.forward_trim:.3f}")

        # External blockers
        self.obstacle_blocked = False
        self.traffic_light = "none"

        # Manual override — when True, obstacle/traffic-light blocks are
        # ignored. Toggled by the "override" voice command; cleared by "stop".
        self.override = False

        veh = os.environ.get("VEHICLE_NAME", "duckiebot")
        self.pub = rospy.Publisher(
            f"/{veh}/car_cmd_switch_node/cmd",
            Twist2DStamped, queue_size=1
        )

        # Subscriptions
        rospy.Subscriber("/voice_control/voice_cmd", VoiceCommand, self.on_voice)
        rospy.Subscriber(f"/{veh}/camera_node/image/compressed", CompressedImage, self.on_image)
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
            self.override = False
            self._send(0.0, 0.0)
            rospy.loginfo("Voice: STOP")

        elif msg.cmd == "override":
            self.override = not self.override
            if self.override:
                rospy.logwarn("Voice: OVERRIDE ON — obstacle/light blocks ignored")
                self._resume()
            else:
                rospy.loginfo("Voice: OVERRIDE OFF — normal safety resumed")

        elif msg.cmd == "max_speed":
            self.target_speed = MAX_SPEED
            rospy.loginfo(f"Voice: MAX SPEED -> {self.target_speed:.2f}")
            if self.mode == "forward" and not self._is_blocked():
                self._send(self.target_speed, self.forward_trim)
            elif self.mode == "turn" and not self._is_blocked():
                self._send(self.target_speed, self.target_omega)

        elif msg.cmd == "forward":
            self.mode = "forward"
            self.target_speed = msg.v if msg.v > 0 else DEFAULT_SPEED
            if not self._is_blocked():
                self._send(self.target_speed, self.forward_trim)
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
            self._send(-self.target_speed, self.forward_trim)
            rospy.loginfo(f"Voice: REVERSE at {self.target_speed}")

        elif msg.cmd == "lane_follow":
            if msg.enable:
                if self.mode != "lane_follow":
                    self.target_speed = msg.v if msg.v > 0 else DEFAULT_SPEED
                    self.mode = "lane_follow"
                    rospy.loginfo("Voice: LANE FOLLOW ON")
            else:
                self.mode = "idle"
                self._send(0.0, 0.0)
                rospy.loginfo("Voice: LANE FOLLOW OFF")

        elif msg.cmd == "pass":
            self._do_pass(msg.side)

        elif msg.cmd == "turn_around":
            self._do_turn_around()

        elif msg.cmd == "cross_lane":
            self._do_cross_lane(msg.side)

        elif msg.cmd == "speed_up":
            self.target_speed = min(self.target_speed + SPEED_STEP, MAX_SPEED)
            rospy.loginfo(f"Voice: SPEED UP -> {self.target_speed:.2f}")
            if self.mode == "forward" and not self._is_blocked():
                self._send(self.target_speed, self.forward_trim)
            elif self.mode == "turn" and not self._is_blocked():
                self._send(self.target_speed, self.target_omega)

        elif msg.cmd == "speed_down":
            self.target_speed = max(self.target_speed - SPEED_STEP, MIN_SPEED)
            rospy.loginfo(f"Voice: SPEED DOWN -> {self.target_speed:.2f}")
            if self.mode == "forward" and not self._is_blocked():
                self._send(self.target_speed, self.forward_trim)
            elif self.mode == "turn" and not self._is_blocked():
                self._send(self.target_speed, self.target_omega)

    # ── Obstacle (can pause forward/turn movement) ───────────────────────────

    def on_obstacle(self, msg):
        was_blocked = self.obstacle_blocked
        self.obstacle_blocked = msg.data

        if msg.data and not was_blocked:
            if self.mode in ("forward", "lane_follow"):
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

        omega = self.forward_trim - (KP * lateral_err + KD * (lateral_err - self.prev_error))
        self.prev_error = lateral_err
        self._send(self.target_speed, omega)

    # ── Heartbeat ────────────────────────────────────────────────────────────

    def heartbeat_check(self, _event):
        if self.mode == "idle":
            return

        dt = (rospy.Time.now() - self.last_cmd_time).to_sec()
        if dt > HEARTBEAT_TIMEOUT:
            rospy.logwarn("Heartbeat timeout — stopping")
            self.mode = "idle"
            self._send(0.0, 0.0)
            return

        if self._is_blocked():
            self._send(0.0, 0.0)
            return
        if self.mode == "forward":
            self._send(self.target_speed, self.forward_trim)
        elif self.mode == "turn":
            self._send(self.target_speed, self.target_omega)
        elif self.mode == "reverse":
            self._send(-self.target_speed, self.forward_trim)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _is_blocked(self):
        if self.override:
            return False
        if self.mode not in ("forward", "lane_follow"):
            return False
        if self.obstacle_blocked:
            return True
        if self.traffic_light in ("red", "yellow"):
            return True
        return False

    def _resume(self):
        """Re-apply the current voice command after a blocker clears."""
        if self._is_blocked():
            return
        if self.mode == "forward":
            self._send(self.target_speed, self.forward_trim)
        elif self.mode == "turn":
            self._send(self.target_speed, self.target_omega)
        elif self.mode == "reverse":
            self._send(-self.target_speed, self.forward_trim)

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

    def _do_turn_around(self):
        """Spin in place 180° then resume forward or lane-follow."""
        prev_mode = self.mode
        self.mode = "idle"

        # Brief stop to settle before spinning
        self._send(0.0, 0.0)
        rospy.sleep(0.25)

        # Spin ~180° in place (π rad at _UTURN_OMEGA rad/s)
        spin_duration = math.pi / _UTURN_OMEGA
        self._send(0.0, _UTURN_OMEGA)
        rospy.sleep(spin_duration)

        # Settle after spin
        self._send(0.0, 0.0)
        rospy.sleep(0.25)

        if prev_mode == "lane_follow":
            self.mode = "lane_follow"
        else:
            self.mode = "forward"
            if not self._is_blocked():
                self._send(self.target_speed, 0.0)
        rospy.loginfo("Voice: TURN AROUND complete")

    def _do_cross_lane(self, side):
        """Smooth lane change: steer into adjacent lane then straighten, keep following."""
        sign = 1.0 if side == "left" else -1.0
        self.mode = "maneuver"

        # Steer into adjacent lane
        self._send(self.target_speed, sign * _CROSS_STEER_OMEGA)
        rospy.sleep(_CROSS_STEER_DUR)

        # Straighten in the new lane
        self._send(self.target_speed, 0.0)
        rospy.sleep(_CROSS_STRAIGHT_DUR)

        # Hand off to lane follower to re-centre in the new lane
        self.prev_error = 0.0
        self.mode = "lane_follow"
        rospy.loginfo(f"Voice: CROSS LANE {side} — lane follow resuming")

    def _send(self, v, omega):
        msg = Twist2DStamped()
        msg.v = v
        msg.omega = omega
        self.pub.publish(msg)


if __name__ == "__main__":
    LaneFollowerNode()
