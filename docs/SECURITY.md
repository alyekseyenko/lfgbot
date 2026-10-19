# Segurança e segredos

- **`.env`** está no `.gitignore`. Nunca commits tokens Discord, `SESSION_SECRET`, passwords Postgres ou `VPS_SSH_PASSWORD`.
- Scripts em `scripts/vps_*.py` exigem **`VPS_HOST`** e **`VPS_SSH_PASSWORD`** no ambiente (sem IP nem password no código).
- Se um segredo foi partilhado em chat, issue ou commit: **roda** o token do bot (Developer Portal), password SSH e `SESSION_SECRET` / `POSTGRES_PASSWORD` conforme o que foi exposto.
- O dashboard OAuth usa `DISCORD_CLIENT_SECRET` e `OAUTH_REDIRECT_URI` alinhados com `PUBLIC_APP_URL`.
