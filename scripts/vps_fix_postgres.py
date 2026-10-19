"""Reset Postgres volume on VPS test stack. Requires VPS_HOST and VPS_SSH_PASSWORD."""
from __future__ import annotations

import sys

from vps_common import connect_vps, vps_lfg_dir


def main() -> None:
    c = connect_vps()
    root = vps_lfg_dir()
    cmd = (
        f"cd {root} && docker compose -f docker-compose.vps-test.yml down -v && "
        "grep -q '^POSTGRES_PASSWORD=' .env || echo 'POSTGRES_PASSWORD='$(openssl rand -hex 16) >> .env && "
        "grep -q '^POSTGRES_USER=' .env || echo 'POSTGRES_USER=lfg' >> .env && "
        "grep -q '^POSTGRES_DB=' .env || echo 'POSTGRES_DB=lfg' >> .env && "
        "docker compose -f docker-compose.vps-test.yml up -d && sleep 30 && "
        "docker compose -f docker-compose.vps-test.yml logs app --tail 12 && "
        "curl -s http://127.0.0.1:8010/health/ready"
    )
    _, stdout, stderr = c.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(out.encode("utf-8", "replace"))
    if err:
        sys.stderr.buffer.write(err.encode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
