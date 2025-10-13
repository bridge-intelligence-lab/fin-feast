from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolMap:
    feast_symbol: str
    binance_symbol: str  # lowercase, e.g., btcusdt


def to_binance_symbol(feast_symbol: str) -> str:
    s = feast_symbol.upper()
    if s == "X:BTCUSD":
        return "btcusdt"
    if s == "C:ETHUSD":
        return "ethusdt"
    raise ValueError(f"Unsupported Feast symbol for Binance mapping: {feast_symbol}")


def to_feast_symbol(binance_stream: str) -> str | None:
    st = binance_stream.lower()
    if "btcusdt" in st:
        return "X:BTCUSD"
    if "ethusdt" in st:
        return "C:ETHUSD"
    return None
