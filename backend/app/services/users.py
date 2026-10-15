from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ranks import normalize_rank_name
from app.db.models import User


async def upsert_user(
    session: AsyncSession,
    discord_id: int,
    name: str,
    *,
    rank: str | None = None,
) -> User:
    if rank is not None:
        rank = normalize_rank_name(rank) or rank

    result = await session.execute(select(User).where(User.discord_id == discord_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(discord_id=discord_id, name=name, rank=rank)
        session.add(user)
    else:
        if user.name != name:
            user.name = name
        if rank is not None:
            user.rank = rank
    await session.flush()
    return user
