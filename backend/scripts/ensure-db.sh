#!/bin/sh
set -e

python <<'PY'
import asyncio

import asyncpg


async def ensure_test_db() -> None:
    import os
    from urllib.parse import quote_plus

    user = os.environ.get("POSTGRES_USER", "lfg")
    password = quote_plus(os.environ.get("POSTGRES_PASSWORD", "lfg"))
    db = os.environ.get("POSTGRES_DB", "lfg")
    dsn = f"postgresql://{user}:{password}@postgres:5432/{db}"
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("CREATE DATABASE lfg_test")
    except asyncpg.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


asyncio.run(ensure_test_db())
PY

if ! python -c "
import asyncio
from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import create_engine

async def main() -> None:
    engine = create_engine(get_settings())
    async with engine.connect() as conn:
        await conn.execute(text('SELECT 1 FROM users LIMIT 1'))
    await engine.dispose()

asyncio.run(main())
" 2>/dev/null; then
  echo "Schema em falta — a recriar..."
  python <<'PY'
import asyncio
from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import create_engine

async def main() -> None:
    engine = create_engine(get_settings())
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO lfg"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await engine.dispose()

asyncio.run(main())
PY
fi

alembic upgrade head
