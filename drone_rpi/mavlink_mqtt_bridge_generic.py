#!/usr/bin/env python3
"""
Generic MAVLink-to-MQTT Bridge for Drone RPi 5
Reads configuration from environment variables set via Web GUI
"""

import os
import sys
import json
import time
from pymavlink import mavutil
import paho.mqtt.client as mqtt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DRONE_ASSET_ID = os.getenv('DRONE_ASSET_ID', 'DRONE_001')
MQTT_HOST = os.getenv('MQTT_HOST', '192.168.4.1')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USER = os.getenv('MQTT_USER', 'drone_user')
MQTT_PASS = os.getenv('MQTT_PASS', 'changeme')
MAVLINK_PORT = os.getenv('MAVLINK_PORT', '/dev/ttyUSB0')
MAVLINK_BAUD = int(os.getenv('MAVLINK_BAUD', '57600'))

TELEMETRY_TOPIC = f"drone/{DRONE_ASSET_ID}/telemetry"
STATUS_TOPIC = f"drone/{DRONE_ASSET_ID}/status"
COMMAND_TOPIC = f"drone/{DRONE_ASSET_ID}/command"

mav = None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(COMMAND_TOPIC)
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

def telemetry_publisher(mqtt_client):
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
                    "drone_id": DRONE_ASSET_ID
                }
                mqtt_client.publish(STATUS_TOPIC, json.dumps(status), qos=1)
            elif msg.get_type() == 'GLOBAL_POSITION_INT':
                telemetry = {
                    "timestamp": time.time(),
                    "lat": msg.lat / 10000000.0,
                    "lon": msg.lon / 10000000.0,
                    "alt": msg.alt / 1000.0,
                    "vx": msg.vx / 100.0,
                    "vy": msg.vy / 100.0,
                    "drone_id": DRONE_ASSET_ID
                }
                mqtt_client.publish(TELEMETRY_TOPIC, json.dumps(telemetry), qos=1)
                logger.info(f"Telemetry published: {telemetry}")
        except Exception as e:
            logger.error(f"Telemetry error: {str(e)}")
            time.sleep(1)

def arm_drone():
    mav.mav.command_long_send(1, 0, 400, 0, 1, 0, 0, 0, 0, 0, 0)
    logger.info("ARM command sent")

def disarm_drone():
    mav.mav.command_long_send(1, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0)
    logger.info("DISARM command sent")

def takeoff_drone(altitude):
    mav.mav.command_long_send(1, 0, 22, 0, 0, 0, 0, 0, 0, 0, altitude)
    logger.info(f"TAKEOFF command sent (altitude: {altitude}m)")

def land_drone():
    mav.mav.command_long_send(1, 0, 21, 0, 0, 0, 0, 0, 0, 0, 0)
    logger.info("LAND command sent")

def main():
    global mav
    logger.info(f"Starting MAVLink-MQTT bridge for {DRONE_ASSET_ID}")
    logger.info(f"MQTT Host: {MQTT_HOST}:{MQTT_PORT}")
    logger.info(f"MAVLink Port: {MAVLINK_PORT} @ {MAVLINK_BAUD} baud")
    try:
        mav = mavutil.mavlink_connection(MAVLINK_PORT, baud=MAVLINK_BAUD)
        mav.wait_heartbeat()
        logger.info("MAVLink connection established")
    except Exception as e:
        logger.error(f"Failed to connect to MAVLink: {str(e)}")
        sys.exit(1)
    mqtt_client = mqtt.Client(client_id=DRONE_ASSET_ID)
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        telemetry_publisher(mqtt_client)
    except Exception as e:
        logger.error(f"MQTT connection error: {str(e)}")
    finally:
        mqtt_client.loop_stop()
        mav.close()

if __name__ == '__main__':
    main()
