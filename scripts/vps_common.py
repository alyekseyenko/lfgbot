"""Shared SSH helpers for VPS maintenance scripts. Secrets only via environment."""
from __future__ import annotations

import os
import sys

import paramiko

VPS_HOST = "VPS_HOST"
VPS_USER = "VPS_USER"
VPS_PASSWORD = "VPS_SSH_PASSWORD"
VPS_LFG_DIR = "VPS_LFG_DIR"


def vps_host() -> str:
    host = os.environ.get(VPS_HOST, "").strip()
    if not host:
        print(f"Set {VPS_HOST} in the environment.", file=sys.stderr)
        raise SystemExit(1)
    return host


def vps_user() -> str:
    return os.environ.get(VPS_USER, "root").strip() or "root"


def vps_password() -> str:
    password = os.environ.get(VPS_PASSWORD, "")
    if not password:
        print(f"Set {VPS_PASSWORD} in the environment (do not commit it).", file=sys.stderr)
        raise SystemExit(1)
    return password


def vps_lfg_dir() -> str:
    return os.environ.get(VPS_LFG_DIR, "/root/lfg-test").strip() or "/root/lfg-test"


def connect_vps(timeout: int = 25) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        vps_host(),
        username=vps_user(),
        password=vps_password(),
        timeout=timeout,
        allow_agent=False,
        look_for_keys=False,
    )
    return client
