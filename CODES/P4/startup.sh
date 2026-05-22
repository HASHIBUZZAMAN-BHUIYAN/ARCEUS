#!/bin/bash
# startup.sh  -  Boot script for Arceus Robot
# ==========================================
# Add to /etc/rc.local or run via systemd service.
#
# To run manually:
#   chmod +x ~/arceus/startup.sh
#   ~/arceus/startup.sh
#
# To auto-start on boot (systemd):
#   sudo nano /etc/systemd/system/arceus.service
#   --- paste the service block below, then:
#   sudo systemctl enable arceus
#   sudo systemctl start arceus
#
# [Unit]
# Description=Arceus Robot Controller
# After=network.target
#
# [Service]
# ExecStart=/home/pi/arceus/startup.sh
# WorkingDirectory=/home/pi/arceus
# Restart=on-failure
# User=pi
#
# [Install]
# WantedBy=multi-user.target

cd ~/arceus
source venv/bin/activate
python main.py
