"""Git pull + rebuild on VPS. Requires VPS_HOST and VPS_SSH_PASSWORD."""
from __future__ import annotations

import sys

from vps_common import connect_vps, vps_lfg_dir


def main() -> None:
    c = connect_vps()
    cmd = (
        f"cd {vps_lfg_dir()} && git pull --ff-only && "
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


if __name__ == "__main__":
    main()
