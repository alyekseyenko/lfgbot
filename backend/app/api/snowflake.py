from __future__ import annotations

from fastapi import HTTPException


def parse_snowflake(value: str, *, field: str = "id") -> int:
    text = value.strip()
    if not text.isdigit():
        raise HTTPException(status_code=400, detail=f"{field} inválido.")
    try:
        return int(text)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} inválido.") from None


def snowflake_to_str(value: int | None) -> str:
    if value is None:
        return "0"
    return str(int(value))


def snowflake_list_to_str(values: list) -> list[str]:
    return [snowflake_to_str(int(x)) for x in values if x is not None and str(x).strip() != ""]


def parse_snowflake_list(values: list[str] | None) -> list[int] | None:
    if values is None:
        return None
    return [parse_snowflake(v, field="id") for v in values]
