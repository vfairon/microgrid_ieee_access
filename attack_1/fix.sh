"#!/bin/bash
# Mitigation script: undoes the weaknesses we exploited earlier.
# Run this from the CORE host while a session is live.
set -e

DOCKER_NODES="Internet DockerSTV DockerOWSV DockerMGEx DockerAPFac DockerFacDCV DockerFDBase DockerAndAre DockerCentralR DockerMaster"

echo "=== 1. Locking down SSH on every docker node ==="
# note: no key is added anywhere -- `docker exec` from the CORE host still
# gets you in regardless of sshd's config, no SSH/key needed for that.
for name in $DOCKER_NODES; do
    echo "-- $name --"
    docker exec "$name" bash -c "
        # turn password login off (add the line if missing, fix it if present)
        if grep -q '^PasswordAuthentication' /etc/ssh/sshd_config; then
            sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
        else
            echo 'PasswordAuthentication no' >> /etc/ssh/sshd_config
        fi

        # sshd only reads its config at startup, so kill the running one and
        # start a fresh one that actually picks up the change
        # '^' anchors this to processes whose command line STARTS with
        # 'sshd:' (the real listener) -- without it, this also matches our
        # own bash -c script (which contains this same text) and kills itself
        pkill -f '^sshd: /usr/sbin/sshd' || true
        # sshd backgrounds itself but keeps our inherited stdout/stderr pipe
        # open forever -- redirect it away so 'docker exec' can return
        /usr/sbin/sshd -f /etc/ssh/sshd_config </dev/null >/dev/null 2>&1
    "
done

echo "=== 2. Locking down the firewall on CentralR ==="
# Before: Internet's own address was allowed to pass through to the rest of
# the grid (so the attack demo could still pivot). Removing that -- Internet
# compromised now means a full dead end, no path onward at all.
vcmd -c /tmp/pycore.1/CentralR -- iptables -F FORWARD
vcmd -c /tmp/pycore.1/CentralR -- iptables -A FORWARD -s 10.0.14.0/24 ! -d 10.0.14.0/24 -j DROP

echo "=== done ==="
"