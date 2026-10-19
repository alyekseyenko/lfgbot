"""Deploy lfg-test on VPS from GitHub. Uses VPS_HOST and VPS_SSH_PASSWORD; optional local .env upload."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

from vps_common import connect_vps, vps_lfg_dir

REPO = "https://github.com/alyekseyenko/lfgbot.git"
ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV = ROOT / ".env"
DIR = vps_lfg_dir()


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    return code, stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")


def main() -> int:
    client = connect_vps()

    code, out, err = run(client, f"test -d {DIR}/.git && echo yes || echo no", timeout=30)
    if "yes" in out:
        cmd = f"cd {DIR} && git pull --ff-only"
    else:
        cmd = f"rm -rf {DIR} && git clone {REPO} {DIR}"
    print(run(client, cmd, timeout=120)[1])

    if LOCAL_ENV.is_file():
        sftp = client.open_sftp()
        sftp.put(str(LOCAL_ENV), f"{DIR}/.env")
        sftp.close()
        print("Uploaded local .env (secrets not printed).")
    else:
        print("No local .env — ensure .env exists on VPS before bot can start.")

    ensure_pg = (
        f"cd {DIR} && "
        "grep -q '^POSTGRES_PASSWORD=' .env || "
        "printf '\\nPOSTGRES_USER=lfg\\nPOSTGRES_DB=lfg\\nPOSTGRES_PASSWORD=%s\\n' "
        "'$(openssl rand -hex 16)' >> .env"
    )
    run(client, ensure_pg, timeout=30)

    setup = f"cd {DIR} && chmod +x scripts/vps_remote_setup.sh && ./scripts/vps_remote_setup.sh"
    code, out, err = run(client, setup, timeout=900)
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    _code2, out2, _ = run(client, f"cd {DIR} && docker compose -f docker-compose.vps-test.yml ps", timeout=60)
    print(out2)
    _code3, out3, _ = run(
        client,
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8010/health/ready || echo fail",
        timeout=30,
    )
    print("health/ready HTTP:", out3.strip())
    client.close()
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
