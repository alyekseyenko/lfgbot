import os
import sys

import paramiko

pw = os.environ.get("VPS_SSH_PASSWORD", "")
if not pw:
    sys.exit("Set VPS_SSH_PASSWORD")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("167.233.121.62", username="root", password=pw, timeout=25)
cmd = (
    "cd /root/lfg-test && git pull --ff-only && "
    "docker compose -f docker-compose.vps-test.yml build app && "
    "docker compose -f docker-compose.vps-test.yml up -d && sleep 40 && "
    "docker compose -f docker-compose.vps-test.yml ps && "
    "docker compose -f docker-compose.vps-test.yml logs app --tail 8 && "
    "curl -s http://127.0.0.1:8010/health/ready"
)
_, stdout, stderr = c.exec_command(cmd, timeout=900)
sys.stdout.buffer.write(stdout.read())
sys.stderr.buffer.write(stderr.read())
c.close()
