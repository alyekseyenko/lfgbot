"""Upload local repo to VPS and rebuild (keeps remote .env). Needs VPS_SSH_PASSWORD."""
from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import paramiko

from vps_common import vps_lfg_dir, vps_host, vps_password, vps_user

DIR = vps_lfg_dir()
ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".cursor",
}
SKIP_FILES = {".env"}


def _should_add(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if parts and parts[0] in SKIP_DIRS:
        return False
    for part in parts:
        if part in SKIP_DIRS:
            return False
    if path.name in SKIP_FILES:
        return False
    return True


def build_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if not _should_add(path):
                continue
            tar.add(path, arcname=path.relative_to(ROOT).as_posix())
    return buf.getvalue()


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 900) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    return code, stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")


def main() -> int:
    host = vps_host()
    password = vps_password()
    user = vps_user()

    print("Creating tarball...")
    payload = build_tarball()
    print(f"Uploading {len(payload) // 1024} KiB to {host}:{DIR} ...")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host, username=user, password=password, timeout=30, allow_agent=False, look_for_keys=False
    )

    sftp = client.open_sftp()
    remote_tar = "/tmp/lfg-deploy.tgz"
    with sftp.file(remote_tar, "wb") as remote:
        remote.write(payload)
    sftp.close()

    run(client, f"mkdir -p {DIR}", timeout=30)
    code, out, err = run(
        client,
        f"cd {DIR} && tar xzf {remote_tar} && rm -f {remote_tar} && "
        "chmod +x scripts/vps_remote_setup.sh && ./scripts/vps_remote_setup.sh",
        timeout=900,
    )
    sys.stdout.buffer.write(out.encode(errors="replace"))
    if err.strip():
        sys.stderr.buffer.write(err.encode(errors="replace"))
    _, ps, _ = run(client, f"cd {DIR} && docker compose -f docker-compose.vps-test.yml ps", timeout=60)
    print(ps)
    _, health, _ = run(client, "curl -s http://127.0.0.1:8010/health/ready", timeout=30)
    print("health/ready:", health.strip())
    client.close()
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
