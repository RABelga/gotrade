"""Probability model: estimates P(next-period gain) per asset.

This is NOT a guarantee of profit. It ranks assets by historical
win-rate, momentum, and risk-adjusted return, then sizes with Kelly.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class ScoredAsset:
    symbol: str
    price: float
    prob_up: float
    expected_return: float
    kelly: float
    win_rate: float
    momentum_20d: float
    volatility: float
    sharpe: float


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def score_asset(symbol: str, df: pd.DataFrame) -> ScoredAsset | None:
    if df is None or len(df) < 30:
        return None
    close = df["Close"].astype(float)
    rets = close.pct_change().dropna()
    if len(rets) < 20:
        return None

    price = float(close.iloc[-1])
    recent = rets.tail(60)

    win_rate = float((recent > 0).mean())
    avg_win = float(recent[recent > 0].mean()) if (recent > 0).any() else 0.0
    avg_loss = float(-recent[recent < 0].mean()) if (recent < 0).any() else 0.0
    mean_ret = float(recent.mean())
    vol = float(recent.std() + 1e-9)

    momentum_20d = float(close.iloc[-1] / close.iloc[-21] - 1.0) if len(close) >= 21 else 0.0
    sharpe = float(mean_ret / vol * np.sqrt(252)) if vol > 0 else 0.0

    # Blend three probability signals into 0..1
    p_winrate = win_rate
    p_momentum = _sigmoid(momentum_20d / (vol * np.sqrt(20) + 1e-9) * 1.5)
    p_sharpe = _sigmoid(sharpe * 1.2)
    prob_up = float(0.5 * p_winrate + 0.25 * p_momentum + 0.25 * p_sharpe)
    prob_up = min(max(prob_up, 0.01), 0.99)

    # Expected daily return
    expected_return = float(prob_up * avg_win - (1 - prob_up) * avg_loss)

    # Kelly fraction: f = (p*(b+1) - 1) / b, b = avg_win / avg_loss
    b = (avg_win / avg_loss) if avg_loss > 1e-12 else 0.0
    if b > 0:
        kelly = (prob_up * (b + 1) - 1) / b
    else:
        kelly = 0.0
    kelly = float(max(0.0, min(kelly, 1.0)))

    return ScoredAsset(
        symbol=symbol,
        price=price,
        prob_up=prob_up,
        expected_return=expected_return,
        kelly=kelly,
        win_rate=win_rate,
        momentum_20d=momentum_20d,
        volatility=vol,
        sharpe=sharpe,
    )


def rank_assets(histories: dict[str, pd.DataFrame], min_prob: float = 0.52,
                min_expected: float = 0.001) -> list[ScoredAsset]:
    scored: list[ScoredAsset] = []
    for sym, df in histories.items():
        s = score_asset(sym, df)
        if s is None:
            continue
        if s.prob_up >= min_prob and s.expected_return >= min_expected and s.kelly > 0:
            scored.append(s)
    # Highest probability-adjusted edge first: sort by expected value, then prob
    scored.sort(key=lambda s: (s.expected_return, s.prob_up), reverse=True)
    return scored
