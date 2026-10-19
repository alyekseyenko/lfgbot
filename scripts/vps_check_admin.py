"""Smoke-check admin SPA on VPS. Requires VPS_HOST and VPS_SSH_PASSWORD."""
from __future__ import annotations

import sys

from vps_common import connect_vps, vps_lfg_dir


def main() -> None:
    c = connect_vps()
    root = vps_lfg_dir()
    for cmd in [
        f"test -f {root}/frontend/dist/index.html && echo SPA_OK || echo SPA_MISSING",
        "curl -s -o /dev/null -w 'admin HTTP %{http_code}\\n' http://127.0.0.1:8010/admin",
        "curl -s http://127.0.0.1:8010/health/ready",
        f"grep PUBLIC_APP_URL {root}/.env | cut -d= -f1",
        f"grep OAUTH_REDIRECT_URI {root}/.env | cut -d= -f1",
    ]:
        _, o, _ = c.exec_command(cmd)
        sys.stdout.buffer.write(o.read())
    c.close()


if __name__ == "__main__":
    main()
