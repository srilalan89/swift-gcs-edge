#!/bin/bash
# =======================================================
# DRONE RPI 5 CLIENT INSTALLATION SCRIPT (GENERIC)
# Installs MAVLink/MQTT bridge prerequisites and Tailscale Agent.
# =======================================================

echo "--- 1. Updating System and Installing Core Dependencies ---"
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl git python3 python3-pip

echo "--- 2. Installing MAVLink and MQTT Bridge Dependencies ---"
pip install pymavlink paho-mqtt pyserial

echo "--- 3. Installing Tailscale Agent (for VPN Hybrid Mode) ---"
# This allows the drone to join the Headscale-controlled network.
curl -fsSL https://tailscale.com/install.sh | sudo sh

echo "--- 4. Enabling UART Serial Port for Pixhawk Connection ---"
# IMPORTANT: This needs to be done via raspi-config or manual boot config edit
echo "NOTE: Please manually run 'sudo raspi-config' -> Interface Options -> Serial Port"
echo "Set 'login shell over serial' to NO and 'serial port hardware' to YES."

echo "--- 5. Installation Complete. ---"
echo "NEXT STEPS (Commissioning via GUI/SSH):"
echo "1. Set the drone's static LAN IP to 192.168.4.2."
echo "2. Set environment variables (DRONE_ASSET_ID, MQTT_PASS)."
echo "3. Run the Python bridge: python3 mavlink_mqtt_bridge_generic.py"
