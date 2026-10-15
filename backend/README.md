# Backend LFG Valorant

Python 3.12 — discord.py, FastAPI, SQLAlchemy async, PostgreSQL.

## Desenvolvimento local

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp ../.env.example ../.env
python -m app.main
```

Com Docker (na raiz do repositório):

```bash
cp .env.example .env
docker compose up --build
```

Deves ver `ready` nos logs da app após o Postgres ficar healthy.
