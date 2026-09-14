"""Proven technical algorithms, each casting a +1 / -1 / 0 vote per symbol.

1. Trend (SMA20 vs SMA50 + price vs SMA50) — "the trend is your friend".
2. MACD(12,26,9) histogram sign — classic momentum.
3. RSI(14) — oversold (<30) bounce / overbought (>70) caution (mean reversion).
4. Bollinger(20,2) — tag of lower band (buy stretch) / upper band (sell stretch).
5. Donchian 20-day breakout — turtle-trader trend entry.

Votes adjust the model's probability modestly (+/-1.5pp each, max +/-7.5pp):
indicators confirm or temper the statistical edge, never override it alone.
"""
import pandas as pd


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0).rolling(n).mean()
    loss = -d.clip(upper=0).rolling(n).mean()
    rs = gain / (loss + 1e-12)
    return 100 - 100 / (1 + rs)


def votes(symbol: str, df: pd.DataFrame) -> dict:
    """Return {'net': int, 'detail': {name: vote}} — needs ~60+ bars."""
    close = df["Close"].astype(float)
    if len(close) < 60:
        return {"net": 0, "detail": {"insufficient_data": 0}}
    last = close.iloc[-1]
    d = {}

    sma20 = _sma(close, 20).iloc[-1]
    sma50 = _sma(close, 50).iloc[-1]
    d["trend"] = 1 if (last > sma50 and sma20 > sma50) else (-1 if last < sma50 else 0)

    macd_line = _ema(close, 12) - _ema(close, 26)
    hist = (macd_line - _ema(macd_line, 9)).iloc[-1]
    d["macd"] = 1 if hist > 0 else -1

    r = rsi(close).iloc[-1]
    d["rsi"] = 1 if r < 30 else (-1 if r > 70 else 0)

    mid = _sma(close, 20)
    sd = close.rolling(20).std()
    lower, upper = (mid - 2 * sd).iloc[-1], (mid + 2 * sd).iloc[-1]
    d["bollinger"] = 1 if last < lower else (-1 if last > upper else 0)

    hi20 = close.tail(20).max()
    d["breakout"] = 1 if last >= hi20 else 0

    return {"net": sum(d.values()), "detail": d}
