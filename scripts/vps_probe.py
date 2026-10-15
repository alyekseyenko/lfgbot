"""One-off VPS probe; password only via VPS_SSH_PASSWORD env. Do not commit secrets."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = os.environ.get("VPS_HOST", "167.233.121.62")
USER = os.environ.get("VPS_USER", "root")
PASSWORD = os.environ.get("VPS_SSH_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("Set VPS_SSH_PASSWORD", file=sys.stderr)
        return 1
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=25,
        allow_agent=False,
        look_for_keys=False,
    )
    cmds = [
        "echo '=== HOST ===' && hostname && uname -a",
        "echo '=== DISK ===' && df -h",
        "echo '=== MEMORY ===' && free -h",
        "echo '=== LOAD ===' && uptime",
        "echo '=== DOCKER PS ===' && (docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'no docker')",
        "echo '=== DOCKER DF ===' && (docker system df 2>/dev/null || true)",
        "echo '=== TOP MEM ===' && ps aux --sort=-%mem | head -12",
        "echo '=== LISTEN PORTS ===' && ss -tlnp 2>/dev/null | head -25",
        "echo '=== LARGE DIRS ===' && du -sh /var/lib/docker /var/log /opt /home /root /srv 2>/dev/null | sort -hr",
    ]
    for cmd in cmds:
        _stdin, stdout, stderr = client.exec_command(cmd, timeout=90)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out, end="")
        if err.strip():
            print(err, end="")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
