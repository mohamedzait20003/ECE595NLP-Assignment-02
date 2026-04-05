# Voice command parsed from spoken English
# cmd: forward | stop | turn | speed_adjust | lane_follow | pass | reverse
string cmd

# Linear velocity (m/s) — used by forward, lane_follow, speed_adjust
float32 v

# Angular velocity (rad/s) — used by turn
float32 omega

# Used by lane_follow command to enable/disable lane following
bool enable

# Used by pass command: "left" or "right"
string side
