from __future__ import annotations

from app.services.guide_content import (
    DEFAULT_GUIDE_BODY,
    effective_guide_body,
    normalize_guide_body,
)


def test_effective_guide_body_default() -> None:
    assert effective_guide_body(None) == DEFAULT_GUIDE_BODY
    assert effective_guide_body("") == DEFAULT_GUIDE_BODY
    assert effective_guide_body("   ") == DEFAULT_GUIDE_BODY
    assert "só **simples**" in DEFAULT_GUIDE_BODY
    assert "`/fechar`" in DEFAULT_GUIDE_BODY
    assert "`/ranking`" in DEFAULT_GUIDE_BODY
    assert "grupos criados" in DEFAULT_GUIDE_BODY
    assert "tipo Detalhado" in DEFAULT_GUIDE_BODY


def test_effective_guide_body_custom() -> None:
    assert effective_guide_body("Olá") == "Olá"


def test_normalize_guide_body_truncates() -> None:
    long = "x" * 5000
    assert len(normalize_guide_body(long) or "") <= 3900
