"""Regression tests for the AI context window (recent-message retention)."""

from app.modules.ai.token_saver import trim_context


def _context(n: int, prefix: str = "mensagem") -> list[dict[str, str]]:
    return [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": (
                f"{prefix} {i}: um texto de contexto razoavelmente longo para "
                "simular uma conversa real de atendimento com o cliente."
            ),
        }
        for i in range(n)
    ]


def test_trim_context_keeps_at_least_20_recent_messages():
    kept = trim_context(_context(40))
    assert len(kept) >= 20
    # The most recent message is always the last one kept.
    assert kept[-1]["content"].startswith("mensagem 39")


def test_trim_context_keeps_at_least_20_with_short_messages():
    kept = trim_context(_context(60, prefix="oi"))
    assert len(kept) >= 20
    assert kept[-1]["content"].startswith("oi 59")


def test_trim_context_never_drops_below_total_when_small():
    kept = trim_context(_context(5))
    assert len(kept) == 5
