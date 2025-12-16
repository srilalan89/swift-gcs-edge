# Swift GCS Edge - Hybrid Drone Ground Control Station

## Overview
Hybrid GCS Edge Architecture for scalable drone operations with centralized Hub management and generic drone clients.

### Components:
- **Hub RPi 5**: Control Plane with Mosquitto MQTT broker, Flask API, and Headscale VPN
- **Drone RPi 5**: Generic client with MAVLink-to-MQTT bridge

## Repository Structure
```
swift-gcs-edge/
├── hub_rpi/              # Hub RPi 5 files
│   ├── install_hub_software.sh
│   ├── start_api.sh
│   ├── hub_manager_api.py
│   └── config/
│       ├── local_hub.conf
│       └── aclfile
└── drone_rpi/           # Drone RPi 5 files
    └── mavlink_mqtt_bridge_generic.py
```

## Installation

### Hub Setup
1. Clone this repo onto your Hub RPi 5
2. Run: `bash hub_rpi/install_hub_software.sh`
3. Configure via Web GUI (hub_manager_api.py handles dynamic settings)

### Drone Setup
1. Copy `drone_rpi/mavlink_mqtt_bridge_generic.py` to Drone RPi 5
2. Set environment variables:
   ```bash
   export DRONE_ASSET_ID=DRONE_001
   export MQTT_HOST=192.168.4.1
   export MQTT_USER=drone_user
   export MQTT_PASS=<password>
   ```
3. Run: `python3 mavlink_mqtt_bridge_generic.py`

## Architecture
- **LAN Mode**: Direct Mosquitto connection for air-gapped operations
- **VPN Mode**: Headscale enrollment for cloud-connected operations
- **All configuration**: Dynamically managed via Web GUI and Flask API
