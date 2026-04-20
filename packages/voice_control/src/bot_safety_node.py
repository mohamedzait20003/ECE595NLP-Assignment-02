#!/usr/bin/env python3
"""ROS node: publishes obstacle state fused from ToF + camera.

ToF alone is unreliable on dark/matte/off-axis targets (they read as
out-of-range and get filtered). Camera alone is noisy per-frame and sensitive
to lighting. Fusing the two:

    blocked = tof_blocked  OR   cam_blocked     (either sensor catches it)
    clear   = tof_clear    AND  cam_clear       (both must agree it's gone)

This catches ToF's failure modes with the camera and ignores per-frame
camera noise because the ToF has to also go quiet to un-block.
"""

import os
import rospy
from collections import deque
from cv_bridge import CvBridge
from sensor_msgs.msg import Range, CompressedImage
from std_msgs.msg import Bool
from voice_control.utils import OBSTACLE_STOP_DIST, detect_close_obstacle

# ToF filtering
TOF_WINDOW = 5            # rolling median window
TOF_MIN_SAMPLES = 3
TOF_MIN_VALID_RANGE = 0.05
TOF_HYSTERESIS = 0.05     # must pass OBSTACLE_STOP_DIST + this to clear

# Camera filtering — vision can flicker at single-frame level.
CAM_DEBOUNCE = 3          # consecutive frames before committing to a state
CAM_RATE_HZ = 10          # throttle camera processing below sensor rate


class SafetyNode:
    def __init__(self):
        rospy.init_node("safety_node")
        self.bridge = CvBridge()

        # Fused state + per-sensor state
        self.blocked = False
        self.tof_blocked = False
        self.cam_blocked = False

        # ToF median filter
        self.tof_window = deque(maxlen=TOF_WINDOW)

        # Camera debounce
        self.cam_candidate = False
        self.cam_count = 0
        self.last_cam_time = rospy.Time(0)
        self.cam_period = rospy.Duration(1.0 / CAM_RATE_HZ)

        self.pub = rospy.Publisher(
            "/voice_control/obstacle", Bool, queue_size=1
        )

        veh = os.environ.get("VEHICLE_NAME", "duckiebot")
        rospy.Subscriber(
            f"/{veh}/front_center_tof_driver_node/range",
            Range, self.on_range
        )
        rospy.Subscriber(
            f"/{veh}/camera_node/image/compressed",
            CompressedImage, self.on_image
        )
        rospy.loginfo("safety_node ready (ToF + camera fusion)")
        rospy.spin()

    # ── ToF ──────────────────────────────────────────────────────────────────

    def on_range(self, msg):
        r = msg.range
        if r < TOF_MIN_VALID_RANGE or r > msg.max_range:
            return

        self.tof_window.append(r)
        if len(self.tof_window) < TOF_MIN_SAMPLES:
            return

        median = sorted(self.tof_window)[len(self.tof_window) // 2]

        if not self.tof_blocked and median < OBSTACLE_STOP_DIST:
            self.tof_blocked = True
            self._update(f"tof={median:.2f}m")
        elif self.tof_blocked and median > OBSTACLE_STOP_DIST + TOF_HYSTERESIS:
            self.tof_blocked = False
            self._update(f"tof={median:.2f}m")

    # ── Camera ───────────────────────────────────────────────────────────────

    def on_image(self, msg):
        now = rospy.Time.now()
        if now - self.last_cam_time < self.cam_period:
            return
        self.last_cam_time = now

        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        raw = detect_close_obstacle(frame)

        if raw == self.cam_candidate:
            self.cam_count += 1
        else:
            self.cam_candidate = raw
            self.cam_count = 1

        if self.cam_count < CAM_DEBOUNCE:
            return

        if raw != self.cam_blocked:
            self.cam_blocked = raw
            self._update(f"cam={raw}")

    # ── Fusion ───────────────────────────────────────────────────────────────

    def _update(self, source):
        # OR to block, AND to clear: either sensor can raise the alarm, but
        # both must agree it's gone before we resume.
        new_blocked = self.tof_blocked or self.cam_blocked
        if new_blocked == self.blocked:
            return

        self.blocked = new_blocked
        self.pub.publish(Bool(data=new_blocked))
        state = "BLOCKED" if new_blocked else "clear"
        rospy.loginfo(
            f"[{source}] {state} (tof={self.tof_blocked}, cam={self.cam_blocked})"
        )


if __name__ == "__main__":
    SafetyNode()
