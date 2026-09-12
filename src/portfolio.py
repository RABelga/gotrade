"""Portfolio + allocation logic: fractional Kelly with caps and cash reserve."""
from .strategy import ScoredAsset


def allocate(scored: list[ScoredAsset], equity: float, cfg: dict) -> dict[str, float]:
    """Return target weights {symbol: weight_of_equity}. Weights sum <= 1 - reserve."""
    if not scored or equity <= 0:
        return {}
    reserve = float(cfg.get("cash_reserve_pct", 0.05))
    budget = 1.0 - reserve
    # Micro all-in mode: whole fund (minus reserve) on the single top pick.
    if cfg.get("micro_all_in"):
        return {scored[0].symbol: budget}
    max_pos = int(cfg.get("max_positions", 3))
    max_w = float(cfg.get("max_weight_per_asset", 0.5))
    reserve = float(cfg.get("cash_reserve_pct", 0.05))
    kelly_cap = float(cfg.get("kelly_fraction_cap", 0.5))
    kelly_scale = float(cfg.get("kelly_scale", 0.5))

    candidates = scored[:max_pos]
    raw = {}
    for s in candidates:
        # Half-Kelly by default, capped, scaled by confidence
        w = s.kelly * kelly_scale
        w = min(w, kelly_cap, max_w)
        raw[s.symbol] = max(w, 0.0)

    total = sum(raw.values())
    budget = 1.0 - reserve
    if total <= 0:
        return {}
    if total > budget:
        scale = budget / total
        raw = {k: v * scale for k, v in raw.items()}
    return raw
