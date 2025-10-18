from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolMap:
    feast_symbol: str
    binance_symbol: str  # lowercase, e.g., btcusdt


# Binance mapping keeps legacy Feast symbol choices for consistency


def to_binance_symbol(feast_symbol: str) -> str:
    s = feast_symbol.upper()
    if s == "X:BTCUSD":
        return "btcusdt"
    if s in ("C:ETHUSD", "X:ETHUSD"):
        return "ethusdt"
    raise ValueError(f"Unsupported Feast symbol for Binance mapping: {feast_symbol}")


def to_feast_symbol(binance_stream: str) -> str | None:
    st = binance_stream.lower()
    if "btcusdt" in st:
        return "X:BTCUSD"
    if "ethusdt" in st:
        return "C:ETHUSD"
    return None


# Polygon mapping: crypto pairs must use X: prefix in the Polygon API


def to_polygon_ticker(feast_symbol: str) -> str:
    s = feast_symbol.upper()
    # Crypto
    if s == "X:BTCUSD":
        return "X:BTCUSD"
    if s in ("C:ETHUSD", "X:ETHUSD"):
        return "X:ETHUSD"
    # Forex or other currency pairs pass through
    if s.startswith("C:"):
        return s
    # Default to echo for already-correct tickers
    if s.startswith("X:"):
        return s
    raise ValueError(f"Unsupported Feast symbol for Polygon mapping: {feast_symbol}")
