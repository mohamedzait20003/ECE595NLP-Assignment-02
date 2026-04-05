import rospy
from cv_bridge import CvBridge
from voice_control.msg import VoiceCommand
from duckietown_msgs.msg import Twist2DStamped
from sensor_msgs.msg import Image, CompressedImage
from voice_control.utils import detect_lane, KP, KD, DEFAULT_SPEED, HEARTBEAT_TIMEOUT

class LaneFollowerNode:
    def __init__(self):
        rospy.init_node("lane_follower_node")
        
        self.enabled = False
        self.prev_error = 0.0
        self.bridge = CvBridge()
        self.target_speed = DEFAULT_SPEED
        self.last_cmd_time = rospy.Time.now()

        self.pub = rospy.Publisher(
            "/duckiebot/wheels_driver_node/wheels_cmd",
            Twist2DStamped, queue_size=1
        )

        rospy.Subscriber("/voice_control/voice_cmd",  VoiceCommand,  self.on_voice)
        rospy.Subscriber("/duckiebot/camera_node/image/compressed", CompressedImage, self.on_image)

        self.timer = rospy.Timer(rospy.Duration(0.1), self.heartbeat_check)
        rospy.loginfo("Lane Follower Node Initialized")
        rospy.spin()

    def _do_pass(self, side):
        sign = 1.0 if side == "left" else -1.0
        steps = [
            (0.3, self.target_speed,  sign * 2.0),
            (0.8, self.target_speed,  0.0),
            (0.3, self.target_speed, -sign * 2.0),
        ]

        for duration, v, omega in steps:
            self.publish_twist(v, omega)
            rospy.sleep(duration)

        self.enabled = True

    def on_voice(self, msg):
        self.last_cmd_time = rospy.Time.now()

        if msg.cmd == "lane_follow":
            self.enabled  = msg.enable
            self.target_speed = msg.v if msg.v > 0 else DEFAULT_SPEED
            rospy.loginfo(f"Lane following {'ON' if self.enabled else 'OFF'}")
        elif msg.cmd == "stop":
            self.enabled = False
            self.publish_twist(0.0, 0.0)
        elif msg.cmd == "forward" and not self.enabled:
            self.publish_twist(msg.v, 0.0)
        elif msg.cmd == "turn" and not self.enabled:
            self.publish_twist(msg.v, msg.omega)
        elif msg.cmd == "reverse" and not self.enabled:
            self.publish_twist(-msg.v, 0.0)
        elif msg.cmd == "pass":
            self._do_pass(msg.side)

    def on_image(self, msg):
        if not self.enabled:
            return
        
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        lateral_err, heading_err = detect_lane(frame)
        if lateral_err is None:
            return
        
        omega = -(KP * lateral_err + KD * (lateral_err - self.prev_error))
        self.prev_error = lateral_err
        self.publish_twist(self.target_speed, omega)

    def heartbeat_check(self, _event):
        if self.enabled:
            dt = (rospy.Time.now() - self.last_cmd_time).to_sec()
            if dt > HEARTBEAT_TIMEOUT:
                rospy.logwarn("Heartbeat timeout — stopping")
                self.enabled = False
                self.publish_twist(0.0, 0.0)

    def publish_twist(self, v, omega):
        msg = Twist2DStamped()
        msg.v     = v
        msg.omega = omega
        self.pub.publish(msg)

if __name__ == "__main__":
    LaneFollowerNode()

