"""Normalize Postgres env vars on VPS and restart stack. Requires VPS_HOST and VPS_SSH_PASSWORD."""
from __future__ import annotations

import os
import sys

from vps_common import connect_vps, vps_lfg_dir


def main() -> None:
    c = connect_vps()
    root = vps_lfg_dir()
    sftp = c.open_sftp()
    with sftp.open(f"{root}/.env", "r") as f:
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
    with sftp.open(f"{root}/.env", "w") as f:
        f.write(new_env.encode("utf-8"))
    sftp.close()
    cmd = (
        f"cd {root} && docker compose -f docker-compose.vps-test.yml down -v && "
        "docker compose -f docker-compose.vps-test.yml up -d && sleep 35 && "
        "docker compose -f docker-compose.vps-test.yml ps && "
        "docker compose -f docker-compose.vps-test.yml logs app --tail 6 && "
        "curl -s http://127.0.0.1:8010/health/ready"
    )
    _, stdout, _ = c.exec_command(cmd, timeout=600)
    sys.stdout.buffer.write(stdout.read())
    c.close()


if __name__ == "__main__":
    main()
