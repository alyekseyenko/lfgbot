# Arranque local sempre via Docker (bot + API + Postgres + dashboard Vite).
# Uso: .\scripts\docker-dev.ps1
#      .\scripts\docker-dev.ps1 -Rebuild

param(
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($Rebuild) {
    docker compose build app
}

docker compose up -d
Write-Host "A aguardar Postgres e migrações (serviço app)..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

docker compose exec -T app alembic current
Write-Host ""
Write-Host "Dashboard: http://localhost:5190" -ForegroundColor Green
Write-Host "API/OAuth: http://localhost:8000" -ForegroundColor Green
Write-Host "Logs app: docker compose logs -f app" -ForegroundColor DarkGray
