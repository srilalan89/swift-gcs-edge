#!/usr/bin/env python3
"""
Generic MAVLink-to-MQTT Bridge for Drone RPi 5
Updated: Now reads configuration from local JSON file (drone_config.json)
Supports both environment variables and API-fetched configuration
"""
import os
import sys
import json
import time
import requests
from pymavlink import mavutil
import paho.mqtt.client as mqtt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration file paths
CONFIG_FILE = "/home/pi/drone_config.json"
DEFAULT_CONFIG = {
    "drone_asset_id": "DRONE_001",
    "mqtt_host": "192.168.4.1",
    "mqtt_port": 1883,
    "mqtt_user": "drone_user",
    "mqtt_pass": "changeme",
    "mavlink_port": "/dev/ttyUSB0",
    "mavlink_baud": 57600,
    "firmware_version": "1.0.0",
    "current_mode": "LAN"
}

# ---- CONFIGURATION LOADING ----

def load_local_config():
    """Load configuration from local JSON file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded local config from {CONFIG_FILE}")
                return config
        except Exception as e:
            logger.error(f"Failed to load local config: {str(e)}")
    return None

def load_config_from_env():
    """Load configuration from environment variables"""
    config = DEFAULT_CONFIG.copy()
    
    # Override with environment variables if present
    config["drone_asset_id"] = os.getenv('DRONE_ASSET_ID', config["drone_asset_id"])
    config["mqtt_host"] = os.getenv('MQTT_HOST', config["mqtt_host"])
    config["mqtt_port"] = int(os.getenv('MQTT_PORT', config["mqtt_port"]))
    config["mqtt_user"] = os.getenv('MQTT_USER', config["mqtt_user"])
    config["mqtt_pass"] = os.getenv('MQTT_PASS', config["mqtt_pass"])
    config["mavlink_port"] = os.getenv('MAVLINK_PORT', config["mavlink_port"])
    config["mavlink_baud"] = int(os.getenv('MAVLINK_BAUD', config["mavlink_baud"]))
    
    logger.info("Loaded config from environment variables")
    return config

def fetch_config_from_api(drone_asset_id, hub_ip="192.168.4.1"):
    """Fetch configuration from Hub API endpoint"""
    try:
        url = f"http://{hub_ip}:5000/api/drones/{drone_asset_id}/config"
        logger.info(f"Fetching configuration from: {url}")
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            config = response.json()
            logger.info("Successfully fetched config from Hub API")
            return config
        else:
            logger.warning(f"Failed to fetch from API: HTTP {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Could not reach Hub API: {str(e)}")
        return None

def load_config():
    """
    Priority-based configuration loading:
    1. Local JSON file (drone_config.json)
    2. Environment variables
    3. API endpoint (if drone_asset_id available)
    4. Default configuration
    """
    # Try local config first
    config = load_local_config()
    if config:
        return config
    
    # Fall back to environment variables
    config = load_config_from_env()
    
    # Try to fetch from API using the asset ID
    try:
        api_config = fetch_config_from_api(config["drone_asset_id"])
        if api_config:
            config.update(api_config)
            logger.info("Updated config from Hub API")
    except Exception as e:
        logger.warning(f"Could not update config from API: {str(e)}")
    
    return config

# ---- GLOBAL VARIABLES ----

mav = None
config = None

# ---- MQTT CALLBACKS ----

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Connected to MQTT broker at {config['mqtt_host']}:{config['mqtt_port']}")
        command_topic = f"drone/{config['drone_asset_id']}/command"
        client.subscribe(command_topic)
        logger.info(f"Subscribed to {command_topic}")
    else:
        logger.error(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        logger.info(f"Command received: {payload}")
        cmd_type = payload.get('command')
        if cmd_type == 'arm':
            arm_drone()
        elif cmd_type == 'disarm':
            disarm_drone()
        elif cmd_type == 'takeoff':
            takeoff_drone(payload.get('altitude', 10))
        elif cmd_type == 'land':
            land_drone()
    except json.JSONDecodeError:
        logger.error("Invalid JSON in command message")
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}")

# ---- TELEMETRY PUBLISHER ----

def telemetry_publisher(mqtt_client):
    """Continuously read MAVLink telemetry and publish via MQTT"""
    while True:
        try:
            msg = mav.recv_match(blocking=False)
            if not msg:
                time.sleep(0.1)
                continue
            
            if msg.get_type() == 'HEARTBEAT':
                status = {
                    "timestamp": time.time(),
                    "mode": msg.custom_mode,
                    "system_status": msg.system_status,
                    "drone_id": config['drone_asset_id']
                }
                status_topic = f"drone/{config['drone_asset_id']}/status"
                mqtt_client.publish(status_topic, json.dumps(status), qos=1)
            
            elif msg.get_type() == 'GLOBAL_POSITION_INT':
                telemetry = {
                    "timestamp": time.time(),
                    "lat": msg.lat / 10000000.0,
                    "lon": msg.lon / 10000000.0,
                    "alt": msg.alt / 1000.0,
                    "vx": msg.vx / 100.0,
                    "vy": msg.vy / 100.0,
                    "drone_id": config['drone_asset_id']
                }
                telemetry_topic = f"drone/{config['drone_asset_id']}/telemetry"
                mqtt_client.publish(telemetry_topic, json.dumps(telemetry), qos=1)
                logger.debug(f"Telemetry published: {telemetry}")
        
        except Exception as e:
            logger.error(f"Telemetry error: {str(e)}")
            time.sleep(1)

# ---- DRONE COMMANDS ----

def arm_drone():
    """Send ARM command to drone"""
    mav.mav.command_long_send(1, 0, 400, 0, 1, 0, 0, 0, 0, 0, 0)
    logger.info("ARM command sent")

def disarm_drone():
    """Send DISARM command to drone"""
    mav.mav.command_long_send(1, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0)
    logger.info("DISARM command sent")

def takeoff_drone(altitude):
    """Send TAKEOFF command to drone"""
    mav.mav.command_long_send(1, 0, 22, 0, 0, 0, 0, 0, 0, 0, altitude)
    logger.info(f"TAKEOFF command sent (altitude: {altitude}m)")

def land_drone():
    """Send LAND command to drone"""
    mav.mav.command_long_send(1, 0, 21, 0, 0, 0, 0, 0, 0, 0, 0)
    logger.info("LAND command sent")

# ---- MAIN ----

def main():
    global mav, config
    
    # Load configuration
    config = load_config()
    logger.info(f"Using configuration: {config}")
    logger.info(f"Drone Asset ID: {config['drone_asset_id']}")
    logger.info(f"MQTT Host: {config['mqtt_host']}:{config['mqtt_port']}")
    logger.info(f"MAVLink Port: {config['mavlink_port']} @ {config['mavlink_baud']} baud")
    logger.info(f"Firmware Version: {config['firmware_version']}")
    
    # Connect to MAVLink
    try:
        mav = mavutil.mavlink_connection(config['mavlink_port'], baud=config['mavlink_baud'])
        mav.wait_heartbeat()
        logger.info("MAVLink connection established")
    except Exception as e:
        logger.error(f"Failed to connect to MAVLink: {str(e)}")
        sys.exit(1)
    
    # Connect to MQTT
    mqtt_client = mqtt.Client(client_id=config['drone_asset_id'])
    mqtt_client.username_pw_set(config['mqtt_user'], config['mqtt_pass'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(config['mqtt_host'], config['mqtt_port'], keepalive=60)
        mqtt_client.loop_start()
        logger.info("MQTT client started")
        
        # Start publishing telemetry
        telemetry_publisher(mqtt_client)
    
    except Exception as e:
        logger.error(f"MQTT connection error: {str(e)}")
        sys.exit(1)
    
    finally:
        mqtt_client.loop_stop()
        mav.close()
        logger.info("Bridge stopped")

if __name__ == '__main__':
    main()
