#!/bin/bash
# =======================================================
# HUB RPI 5 EDGE GATEWAY INSTALLATION SCRIPT (GENERIC)
# Prepares the RPi 5 to run Mosquitto, Flask API, and Headscale
# =======================================================

echo "--- 1. Updating System and Installing Core Dependencies ---"
sudo apt update
sudo apt upgrade -y
sudo apt install -y build-essential curl git python3 python3-pip

echo "--- 2. Installing MQTT Broker (Mosquitto) and Python Libraries ---"
sudo apt install -y mosquitto mosquitto-clients
pip install Flask flask-cors paho-mqtt

echo "--- 3. Installing Tailscale/Headscale Agent ---"
curl -fsSL https://tailscale.com/install.sh | sudo sh

echo "--- 4. Installing Web Terminal (Wetty) ---"
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g wetty

echo "--- 5. Installation Complete. Setting up Configuration Directories ---"

# Create Mosquitto config directories
sudo mkdir -p /etc/mosquitto/conf.d/
sudo mkdir -p /etc/mosquitto/acl/

echo "--- 6. Next Steps: Set passwords and start services via the Hub Management Dashboard (Web GUI) ---"
echo "Repository files are ready for deployment."
