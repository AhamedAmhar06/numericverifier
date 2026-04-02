"""Unit tests for llm_fallback.py — Tier 3 LLM verification fallback."""
from app.verifier.llm_fallback import llm_verify_fallback


def _caller(text):
    """Factory: returns a mock llm_caller that always returns `text`."""
    def call(prompt, system_prompt=None):
        return text
    return call


def _table():
    return {
        "columns": ["Item", "FY2023", "FY2022"],
        "rows": [
            ["Revenue", "500", "450"],
            ["Gross Profit", "200", "180"],
            ["Net Income", "90", "81"],
        ],
    }


def test_yes_returns_accept():
    result = llm_verify_fallback(
        "What was revenue growth?", _table(),
        "Revenue grew by 11.1%.", _caller("YES")
    )
    assert result == "ACCEPT"


def test_no_returns_flag():
    result = llm_verify_fallback(
        "What was revenue growth?", _table(),
        "Revenue grew by 25%.", _caller("NO")
    )
    assert result == "FLAG"


def test_cannot_determine_returns_none():
    result = llm_verify_fallback(
        "What was EBITDA margin?", _table(),
        "EBITDA margin was 18%.", _caller("CANNOT_DETERMINE")
    )
    assert result is None


def test_exception_returns_none():
    def bad(prompt, system_prompt=None):
        raise RuntimeError("down")
    result = llm_verify_fallback("Q", _table(), "A", bad)
    assert result is None


def test_yes_case_insensitive():
    result = llm_verify_fallback(
        "What was revenue growth?", _table(),
        "Revenue grew by 11.1%.", _caller("yes")
    )
    assert result == "ACCEPT"
