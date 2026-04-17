#!/usr/bin/env python3
"""ROS node: detects traffic lights from camera and publishes state to
/voice_control/traffic_light so other nodes can react."""

import rospy
from cv_bridge import CvBridge
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage
from voice_control.utils import detect_traffic_light


class TrafficLightNode:
    def __init__(self):
        rospy.init_node("traffic_light_node")

        self.bridge = CvBridge()
        self.state = None

        self.state_pub = rospy.Publisher(
            "/voice_control/traffic_light", String, queue_size=1
        )

        rospy.Subscriber(
            "/duckiebot/camera_node/image/compressed",
            CompressedImage, self.on_image
        )

        rospy.loginfo("traffic_light_node ready")
        rospy.spin()

    def on_image(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        color = detect_traffic_light(frame)

        if color == self.state:
            return

        self.state = color
        if color:
            self.state_pub.publish(String(data=color))
            rospy.loginfo(f"Traffic light: {color}")
        elif self.state is not None:
            self.state_pub.publish(String(data="none"))
            rospy.loginfo("Traffic light: none")


if __name__ == "__main__":
    TrafficLightNode()
