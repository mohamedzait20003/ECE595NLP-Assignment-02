import rospy
from sensor_msgs.msg import Range
from voice_control.msg import VoiceCommand
from duckietown_msgs.msg import Twist2DStamped
from voice_control.utils import OBSTACLE_STOP_DIST

class SafetyNode:
    def __init__(self):
        rospy.init_node("safety_node")
        self.blocked = False

        self.pub = rospy.Publisher(
            "/duckiebot/wheels_driver_node/wheels_cmd",
            Twist2DStamped, queue_size=1
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
                rospy.logwarn(f"Obstacle at {msg.range:.2f}m — STOP")
                self.blocked = True
                self._stop()
        else:
            if self.blocked:
                rospy.loginfo("Obstacle cleared")
                self.blocked = False

    def _stop(self):
        msg = Twist2DStamped()
        msg.v = 0.0
        msg.omega = 0.0
        self.pub.publish(msg)

if __name__ == "__main__":
    SafetyNode()
