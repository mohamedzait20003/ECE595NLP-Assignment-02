#!/usr/bin/env python3
import os
import rospy
from sensor_msgs.msg import Range
from std_msgs.msg import Bool
from voice_control.utils import OBSTACLE_STOP_DIST

DEBOUNCE_COUNT = 2
MIN_VALID_RANGE = 0.05  # meters

class SafetyNode:
    def __init__(self):
        rospy.init_node("safety_node")
        self.blocked = False
        self.block_streak = 0
        self.clear_streak = 0

        self.pub = rospy.Publisher(
            "/voice_control/obstacle", Bool, queue_size=1
        )
        veh = os.environ.get("VEHICLE_NAME", "duckiebot")
        rospy.Subscriber(
            f"/{veh}/front_center_tof_driver_node/range",
            Range, self.on_range
        )
        rospy.loginfo("safety_node ready")
        rospy.spin()

    def on_range(self, msg):
        r = msg.range

        # Discard obviously invalid readings (sensor noise / out-of-range).
        if r < MIN_VALID_RANGE or r > msg.max_range:
            return

        if r < OBSTACLE_STOP_DIST:
            self.block_streak += 1
            self.clear_streak = 0
            if not self.blocked and self.block_streak >= DEBOUNCE_COUNT:
                rospy.logwarn(f"Obstacle at {r:.2f}m — blocked")
                self.blocked = True
                self.pub.publish(Bool(data=True))
        else:
            self.clear_streak += 1
            self.block_streak = 0
            if self.blocked and self.clear_streak >= DEBOUNCE_COUNT:
                rospy.loginfo("Obstacle cleared")
                self.blocked = False
                self.pub.publish(Bool(data=False))


if __name__ == "__main__":
    SafetyNode()
