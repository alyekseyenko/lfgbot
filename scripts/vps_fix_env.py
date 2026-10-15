import os
import re
import sys

import paramiko

pw = os.environ.get("VPS_SSH_PASSWORD", "")
if not pw:
    sys.exit("Set VPS_SSH_PASSWORD")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("167.233.121.62", username="root", password=pw, timeout=25)
sftp = c.open_sftp()
with sftp.open("/root/lfg-test/.env", "r") as f:
    text = f.read().decode("utf-8", errors="replace")
sftp.close()
lines = []
pg_pass = "lfgtest_vps_" + os.urandom(4).hex()
for line in text.splitlines():
    if line.startswith("DATABASE_URL=") or line.startswith("TEST_DATABASE_URL="):
        continue
    if line.startswith("POSTGRES_PASSWORD="):
        continue
    if line.startswith("POSTGRES_USER=") or line.startswith("POSTGRES_DB="):
        continue
    lines.append(line)
lines.extend(
    [
        "POSTGRES_USER=lfg",
        "POSTGRES_DB=lfg",
        f"POSTGRES_PASSWORD={pg_pass}",
    ]
)
new_env = "\n".join(lines) + "\n"
sftp = c.open_sftp()
with sftp.open("/root/lfg-test/.env", "w") as f:
    f.write(new_env.encode("utf-8"))
sftp.close()
cmd = (
    "cd /root/lfg-test && docker compose -f docker-compose.vps-test.yml down -v && "
    "docker compose -f docker-compose.vps-test.yml up -d && sleep 35 && "
    "docker compose -f docker-compose.vps-test.yml ps && "
    "docker compose -f docker-compose.vps-test.yml logs app --tail 6 && "
    "curl -s http://127.0.0.1:8010/health/ready"
)
_, stdout, _ = c.exec_command(cmd, timeout=600)
sys.stdout.buffer.write(stdout.read())
c.close()
