#!/usr/bin/env python3
"""
Hub Manager API - Flask backend for dynamic Hub configuration
Handles MQTT broker settings, network config, and service control
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import subprocess
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "/etc/mosquitto/hub_config.json"
DEFAULT_CONFIG = {
    "mode": "LAN",
    "broker_ip": "192.168.4.1",
    "broker_port": 1883,
    "headscale_server": "headscale.local",
    "headscale_port": 443
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_CONFIG

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@app.route('/config/get', methods=['GET'])
def get_config():
    config = load_config()
    return jsonify(config), 200

@app.route('/config/set', methods=['POST'])
def set_config():
    try:
        data = request.json
        config = load_config()
        config.update(data)
        save_config(config)
        logger.info(f"Configuration updated: {data}")
        return jsonify({"status": "success", "config": config}), 200
    except Exception as e:
        logger.error(f"Config error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/network/set-static-ip', methods=['POST'])
def set_static_ip():
    try:
        data = request.json
        interface = data.get('interface', 'eth0')
        ip_address = data.get('ip_address')
        gateway = data.get('gateway')
        
        if not all([ip_address, gateway]):
            return jsonify({"status": "error", "message": "Missing IP or gateway"}), 400
        
        config_line = f"interface {interface}\nstatic ip_address={ip_address}/24\nstatic routers={gateway}\n"
        with open('/etc/dhcpcd.conf', 'a') as f:
            f.write(config_line)
        
        subprocess.run(['sudo', 'systemctl', 'restart', 'dhcpcd'], check=True)
        logger.info(f"Static IP set: {ip_address} on {interface}")
        return jsonify({"status": "success", "message": f"Static IP {ip_address} configured"}), 200
    except Exception as e:
        logger.error(f"Network config error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/service/restart', methods=['POST'])
def restart_service():
    try:
        service = request.json.get('service')
        if service not in ['mosquitto', 'headscale', 'nginx', 'dhcpcd']:
            return jsonify({"status": "error", "message": "Invalid service"}), 400
        
        subprocess.run(['sudo', 'systemctl', 'restart', service], check=True)
        logger.info(f"Service restarted: {service}")
        return jsonify({"status": "success", "message": f"{service} restarted"}), 200
    except Exception as e:
        logger.error(f"Service restart error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
