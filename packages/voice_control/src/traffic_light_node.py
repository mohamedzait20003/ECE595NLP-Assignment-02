#!/usr/bin/env python3

import os
import rospy
from cv_bridge import CvBridge
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage
from voice_control.utils import detect_traffic_light

DEBOUNCE_FRAMES = 4

class TrafficLightNode:
    def __init__(self):
        rospy.init_node("traffic_light_node")

        self.bridge = CvBridge()
        self.state = None
        self.candidate = None
        self.candidate_count = 0

        self.state_pub = rospy.Publisher(
            "/voice_control/traffic_light", String, queue_size=1
        )

        veh = os.environ.get("VEHICLE_NAME", "duckiebot")
        rospy.Subscriber(
            f"/{veh}/camera_node/image/compressed",
            CompressedImage, self.on_image
        )

        rospy.loginfo("traffic_light_node ready")
        rospy.spin()

    def on_image(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        color = detect_traffic_light(frame)

        if color == self.candidate:
            self.candidate_count += 1
        else:
            self.candidate = color
            self.candidate_count = 1

        if self.candidate_count < DEBOUNCE_FRAMES:
            return

        if color == self.state:
            return

        self.state = color
        if color:
            self.state_pub.publish(String(data=color))
            rospy.loginfo(f"Traffic light: {color}")
        else:
            self.state_pub.publish(String(data="none"))
            rospy.loginfo("Traffic light: none")


if __name__ == "__main__":
    TrafficLightNode()
