# Voice-Controlled Duckiebot

Voice-driven autonomous driving for the Duckietown DB21J. The laptop captures
speech and streams text to the bot over HTTP; the bot parses the command, runs
lane following, and reacts to obstacles and traffic lights.

Built on top of [duckietown/template-ros](https://github.com/duckietown/template-ros).

## Architecture

```
[Laptop mic] --Azure STT--> [voice_client.py] --HTTP POST--> [voice_command_node]
                                                                    |
                                                                    v
                                                        /voice_control/voice_cmd
                                                                    |
[ToF] -> [safety_node] ----------> /voice_control/obstacle ----+    |
[Cam] -> [traffic_light_node] ---> /voice_control/traffic_light +-> [lane_follower_node] -> wheels
[Cam] -----------------------------------------------------------+
```

Only `lane_follower_node` publishes wheel commands. Priority:
1. Voice command (mode: idle / forward / turn / reverse / lane_follow / pass)
2. Obstacle (ToF) — pauses forward motion, resumes when clear
3. Traffic light — pauses on red/yellow, voice can override
4. Lane following — runs when voice says "follow lane"

## Layout

```
client/                  Laptop voice client (mic + Azure STT + HTTP)
packages/voice_control/
  src/
    voice_command_node   HTTP server, regex parses text -> VoiceCommand
    lane_follower_node   Sole wheels controller (PD lane follow + state machine)
    bot_safety_node      ToF -> /voice_control/obstacle
    traffic_light_node   Camera -> /voice_control/traffic_light
  utils/                 lane_detection, traffic_synthesis, voice_synthesis, config
  launch/                voice_control.launch
  msg/                   VoiceCommand.msg
```

## Setup

### Bot

```bash
dts devel build -f -H <BOT_IP>
dts devel run  -H <BOT_IP>
```

Tunable parameters live in [packages/voice_control/utils/load_config.py](packages/voice_control/utils/load_config.py)
(speeds, PD gains, obstacle threshold, heartbeat timeout).

### Laptop client

```bash
cd client
pip install -r requirements.txt
```

Add Azure Speech credentials to a `.env` at the project root:
```
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=...
```

Run it:
```bash
python voice_client.py --bot http://<BOT_IP>:8080
python voice_client.py --list-devices         # find mic index
python voice_client.py --bot ... --device 3   # pick a specific mic
```

## Voice commands

`stop`, `forward`, `reverse`, `turn left/right`, `follow the lane`,
`stop following`, `pass on the left/right`. Parsing is regex-only (see
[voice_synthesis.py](packages/voice_control/utils/voice_synthesis.py)).

## Dependencies

- Bot: `numpy`, `opencv-python-headless` (see `dependencies-py3.txt`)
- Laptop: `azure-cognitiveservices-speech`, `sounddevice`, `python-dotenv`,
  `requests` (see `client/requirements.txt`)
