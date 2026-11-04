#!/bin/bash
# Usage: ./setup_and_connect.sh <target_ip_or_hostname>
#
# openssh-client/sshpass are baked into the image at build time (see Dockerfile) --
# CORE nodes have no route to the real internet, so `apt-get install` at runtime
# fails here. The target's IP also can't be looked up via `docker inspect` --
# these CORE nodes have no Docker CLI/socket of their own -- so it's passed in
# directly: read it from the CORE GUI (click the node) or `ip addr` inside it.

SSH_USER="root"
SSH_PASSWORD="1"      # ← must match the password set on the target node

TARGET_IP="$1"
if [ -z "$TARGET_IP" ]; then
    echo "Usage: $0 <target_ip_or_hostname>"
    exit 1
fi

echo "Connecting to ${SSH_USER}@${TARGET_IP}..."
sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no "${SSH_USER}@${TARGET_IP}"

echo "Script executed successfully."

