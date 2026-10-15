from __future__ import annotations

import asyncio

import httpx

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20


async def exchange_code(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def fetch_current_user(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def fetch_user_guilds(access_token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        last_response: httpx.Response | None = None
        for attempt in range(4):
            response = await client.get(
                f"{DISCORD_API}/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            last_response = response
            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After", "1")
                try:
                    wait_s = float(retry_after)
                except ValueError:
                    wait_s = 1.0
                await asyncio.sleep(min(max(wait_s, 0.5), 5.0))
                continue
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        if last_response is not None:
            last_response.raise_for_status()
        return []


def user_can_manage_guild(guild: dict) -> bool:
    permissions = int(guild.get("permissions", 0))
    return bool(permissions & MANAGE_GUILD)
