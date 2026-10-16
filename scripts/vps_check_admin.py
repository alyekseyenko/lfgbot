import os
import sys

import paramiko

pw = os.environ.get("VPS_SSH_PASSWORD", "")
if not pw:
    sys.exit(1)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("167.233.121.62", username="root", password=pw, timeout=25)
for cmd in [
    "test -f /root/lfg-test/frontend/dist/index.html && echo SPA_OK || echo SPA_MISSING",
    "curl -s -o /dev/null -w 'admin HTTP %{http_code}\\n' http://127.0.0.1:8010/admin",
    "curl -s http://127.0.0.1:8010/health/ready",
    "grep PUBLIC_APP_URL /root/lfg-test/.env | cut -d= -f1",
    "grep OAUTH_REDIRECT_URI /root/lfg-test/.env | cut -d= -f1",
]:
    _, o, _ = c.exec_command(cmd)
    sys.stdout.buffer.write(o.read())
c.close()
