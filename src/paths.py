"""Per-fund state files. cfg may carry "tag": "" (stocks, default) or
"crypto" -> crypto_signals.json, crypto_memory.json, etc.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def files(cfg: dict | None = None) -> dict[str, Path]:
    tag = str(((cfg or {}).get("tag")) or "").strip()
    pre = f"{tag}_" if tag else ""
    return {
        "signals": BASE / f"{pre}signals.json",
        "memory": BASE / f"{pre}memory.json",
        "alerts": BASE / f"{pre}last_alert.json",
        "holdings": BASE / f"{pre}holdings.json",
    }
