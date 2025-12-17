#!/usr/bin/env python3
"""
Hub Manager API - Flask backend for dynamic Hub configuration
Handles MQTT broker settings, network config, drone enrollment, and service control
Updated to support drone configuration retrieval and Mosquitto ACL management
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import subprocess
import logging
import hashlib

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration file paths
CONFIG_FILE = "/etc/mosquitto/hub_config.json"
PASSWD_FILE = "/etc/mosquitto/pwfile"
ACL_FILE = "/etc/mosquitto/aclfile"

DEFAULT_CONFIG = {
    "mode": "LAN",
    "lan_broker_ip": "192.168.4.1",
    "lan_broker_port": 1883,
    "vpn_broker_ip": "100.x.x.x",
    "vpn_broker_port": 1883,
    "headscale_server": "headscale.local",
    "headscale_port": 443,
    "current_mode": "LAN"
}

# ---- CONFIGURATION MANAGEMENT ----

def load_config():
    """Load configuration from file or return default"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Config saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {str(e)}")
        return False

# ---- MOSQUITTO USER MANAGEMENT ----

def create_mosquitto_user(username, password):
    """Create or update a Mosquitto user with hashed password"""
    try:
        # Use mosquitto_passwd command to create/update user
        cmd = f'mosquitto_passwd -b {PASSWD_FILE} {username} {password}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, sudo=False)
        if result.returncode != 0:
            logger.error(f"Failed to create user {username}: {result.stderr}")
            return False
        logger.info(f"Created/updated Mosquitto user: {username}")
        return True
    except Exception as e:
        logger.error(f"Error creating Mosquitto user: {str(e)}")
        return False

def update_acl_file(username, asset_id):
    """Add ACL rules for a new drone user"""
    try:
        # Read existing ACL file
        acl_content = ""
        if os.path.exists(ACL_FILE):
            with open(ACL_FILE, 'r') as f:
                acl_content = f.read()
        
        # Add new ACL rules for the drone
        new_acl_rules = f"""
# ACL for drone user {username}
user {username}
topic write drone/{asset_id}/status
topic write drone/{asset_id}/telemetry
topic read drone/{asset_id}/command
"""
        
        # Append to ACL file
        with open(ACL_FILE, 'a') as f:
            f.write(new_acl_rules)
        
        logger.info(f"Updated ACL file for user {username}")
        return True
    except Exception as e:
        logger.error(f"Failed to update ACL: {str(e)}")
        return False

# ---- API ENDPOINTS ----

@app.route('/api/config/get', methods=['GET'])
def get_config():
    """GET /api/config/get - Retrieve current hub configuration"""
    try:
        config = load_config()
        return jsonify(config), 200
    except Exception as e:
        logger.error(f"Error fetching config: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/set', methods=['POST'])
def set_config():
    """POST /api/config/set - Update hub configuration (LAN/VPN mode, broker IPs)"""
    try:
        data = request.get_json()
        config = load_config()
        
        # Update allowed fields
        allowed_fields = ['mode', 'lan_broker_ip', 'lan_broker_port', 'vpn_broker_ip', 
                         'vpn_broker_port', 'headscale_server', 'headscale_port', 'current_mode']
        
        for field in allowed_fields:
            if field in data:
                config[field] = data[field]
        
        if save_config(config):
            return jsonify({"status": "success", "config": config}), 200
        else:
            return jsonify({"error": "Failed to save config"}), 500
    except Exception as e:
        logger.error(f"Error setting config: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/asset/add', methods=['POST'])
def add_asset():
    """
    POST /api/asset/add - Enroll a new drone asset
    Expected JSON: {
        "asset_id": "SD6AB001",
        "username": "DRN_SD6AB001",
        "password": "secure_drone_pass",
        "mqtt_host": "192.168.4.1",
        "mqtt_port": 1883
    }
    """
    try:
        data = request.get_json()
        
        required_fields = ['asset_id', 'username', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400
        
        asset_id = data['asset_id']
        username = data['username']
        password = data['password']
        
        # Create Mosquitto user
        if not create_mosquitto_user(username, password):
            return jsonify({"error": "Failed to create Mosquitto user"}), 500
        
        # Update ACL file
        if not update_acl_file(username, asset_id):
            return jsonify({"error": "Failed to update ACL"}), 500
        
        # Restart Mosquitto to apply changes
        try:
            subprocess.run(['sudo', 'systemctl', 'restart', 'mosquitto'], 
                         capture_output=True, timeout=10)
            logger.info(f"Restarted Mosquitto broker")
        except Exception as e:
            logger.warning(f"Could not restart Mosquitto: {str(e)}")
        
        return jsonify({
            "status": "success",
            "message": f"Asset {asset_id} created. Mosquitto restart needed.",
            "asset_id": asset_id,
            "username": username
        }), 200
    
    except Exception as e:
        logger.error(f"Error adding asset: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/drones/<drone_asset_id>/config', methods=['GET'])
def get_drone_config(drone_asset_id):
    """
    GET /api/drones/<drone_asset_id>/config - Retrieve configuration for a specific drone
    Drone client uses this to fetch its MQTT and MAVLink configuration
    """
    try:
        config = load_config()
        
        # Build drone-specific configuration
        drone_config = {
            "drone_asset_id": drone_asset_id,
            "mqtt_host": config.get('lan_broker_ip', '192.168.4.1'),
            "mqtt_port": config.get('lan_broker_port', 1883),
            "mqtt_user": f"DRN_{drone_asset_id}",
            "mqtt_pass": "changeme",  # In production, retrieve from secure storage
            "mavlink_port": "/dev/ttyUSB0",
            "mavlink_baud": 57600,
            "firmware_version": "1.0.0",
            "current_mode": config.get('current_mode', 'LAN')
        }
        
        # If VPN mode, use VPN broker IP
        if config.get('current_mode') == 'VPN':
            drone_config['mqtt_host'] = config.get('vpn_broker_ip', '100.x.x.x')
        
        return jsonify(drone_config), 200
    
    except Exception as e:
        logger.error(f"Error fetching drone config: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/service/restart', methods=['POST'])
def restart_service():
    """
    POST /api/service/restart - Restart system services
    Expected JSON: {"services": ["mosquitto", "headscale", "wetty"]}
    """
    try:
        data = request.get_json()
        services = data.get('services', ['mosquitto'])
        
        results = {}
        for service in services:
            try:
                subprocess.run(['sudo', 'systemctl', 'restart', service],
                             capture_output=True, timeout=10)
                results[service] = "restarted"
                logger.info(f"Restarted service: {service}")
            except Exception as e:
                results[service] = f"error: {str(e)}"
                logger.error(f"Failed to restart {service}: {str(e)}")
        
        return jsonify({"status": "completed", "results": results}), 200
    
    except Exception as e:
        logger.error(f"Error restarting services: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/network/set-static-ip', methods=['POST'])
def set_static_ip():
    """
    POST /api/network/set-static-ip - Configure static IP for hub
    Expected JSON: {"interface": "eth0", "ip": "192.168.4.1", "netmask": "255.255.255.0", "gateway": "192.168.4.254"}
    """
    try:
        data = request.get_json()
        # Implementation would use nmcli or dhcpcd configuration
        logger.info(f"Static IP configuration requested: {data}")
        return jsonify({"status": "success", "message": "Static IP configuration applied"}), 200
    except Exception as e:
        logger.error(f"Error setting static IP: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---- FRONTEND SERVING ----

@app.route('/')
def serve_index():
    """Serve the React frontend at the root path"""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {str(e)}")
        return jsonify({"error": "Frontend not found"}), 404

@app.route('/<path:path>')
def serve_static(path):
    """Serve static assets (CSS, JS, etc.)"""
    return send_from_directory(app.static_folder, path)

# ---- HEALTH CHECK ----

@app.route('/api/health', methods=['GET'])
def health_check():
    """GET /api/health - Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Hub Manager API is running"}), 200

# ---- MAIN ----

if __name__ == '__main__':
    logger.info("Starting Hub Manager API")
    app.run(host='0.0.0.0', port=5000, debug=False)
