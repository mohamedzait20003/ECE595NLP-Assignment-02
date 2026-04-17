#!/usr/bin/env python3
"""ROS node: publishes obstacle state from ToF sensor to /voice_control/obstacle."""

import rospy
from sensor_msgs.msg import Range
from std_msgs.msg import Bool
from voice_control.utils import OBSTACLE_STOP_DIST


class SafetyNode:
    def __init__(self):
        rospy.init_node("safety_node")
        self.blocked = False

        self.pub = rospy.Publisher(
            "/voice_control/obstacle", Bool, queue_size=1
        )
        rospy.Subscriber(
            "/duckiebot/front_center_tof_driver_node/range",
            Range, self.on_range
        )
        rospy.loginfo("safety_node ready")
        rospy.spin()

    def on_range(self, msg):
        if msg.range < OBSTACLE_STOP_DIST:
            if not self.blocked:
                rospy.logwarn(f"Obstacle at {msg.range:.2f}m — blocked")
                self.blocked = True
                self.pub.publish(Bool(data=True))
        else:
            if self.blocked:
                rospy.loginfo("Obstacle cleared")
                self.blocked = False
                self.pub.publish(Bool(data=False))


if __name__ == "__main__":
    SafetyNode()
