from __future__ import annotations


def backoff_delay(attempt: int, cap: int = 30) -> float:
    attempt = max(1, attempt)
    delay = 2 ** min(attempt, 8)
    return float(min(cap, delay))


def test_backoff_delay_growth_and_cap() -> None:
    TWO = 2.0
    FOUR = 4.0
    EIGHT = 8.0
    THIRTY = 30.0
    assert backoff_delay(1) == TWO
    assert backoff_delay(2) == FOUR
    assert backoff_delay(3) == EIGHT
    # Cap around 30
    assert backoff_delay(10) == THIRTY
    assert backoff_delay(100) == THIRTY
