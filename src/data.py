"""Price data fetching (Yahoo Finance, no API key needed)."""
import pandas as pd


def fetch_history(symbol: str, period_days: int = 120) -> pd.DataFrame:
    """Fetch daily OHLCV history for a symbol. Returns DataFrame with Close column."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=f"{period_days + 30}d", interval="1d", auto_adjust=True)
    if df is None or df.empty:
        raise ValueError(f"No data for {symbol}")
    df = df.tail(period_days)
    return df


def fetch_latest_price(symbol: str) -> float:
    """Fetch latest close price."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d", interval="1d", auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"No price for {symbol}")
    return float(hist["Close"].iloc[-1])


def fetch_all(universe: list[str], period_days: int) -> dict[str, pd.DataFrame]:
    out = {}
    for sym in universe:
        try:
            out[sym] = fetch_history(sym, period_days)
        except Exception as e:
            print(f"[data] skip {sym}: {e}")
    return out
