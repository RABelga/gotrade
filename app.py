"""GoTrade dashboard for Hugging Face Spaces (Gradio).

Local test:  python app.py        -> opens http://127.0.0.1:7860
On Spaces: upload this whole folder, pick SDK "Gradio", secret TELEGRAM_* optional.
"""
import json

import gradio as gr
import pandas as pd

from src.bot import load_config
from src.data import fetch_all
from src.strategy import rank_assets
from src.portfolio import allocate
from src import learner

try:
    import spaces  # preinstalled on Hugging Face Spaces (ZeroGPU)

    @spaces.GPU(duration=5)
    def _zerogpu_keepalive() -> str:
        """No-op: this app is CPU-bound; ZeroGPU just requires one decorated fn."""
        return "ok"
except Exception:
    pass  # local run without the `spaces` package


def refresh(fund: float):
    cfg = load_config()
    try:
        fund = float(fund)
    except Exception:
        fund = float(cfg.get("initial_cash", 6.0))
    histories = fetch_all(cfg["universe"], int(cfg.get("lookback_days", 120)))
    if not histories:
        return "No data fetched.", None, "n/a", "n/a"

    scored = rank_assets(histories,
                         float(cfg.get("min_probability", 0.52)),
                         float(cfg.get("min_expected_return", 0.001)))
    mem = learner.load_memory()
    learner.settle(mem, histories)
    scored = learner.calibrate(scored, mem)
    reg = learner.regime(histories)
    if reg["prob_bump"]:
        scored = [s for s in scored
                  if s.prob_up >= float(cfg.get("min_probability", 0.52)) + reg["prob_bump"]]
    learner.record(mem, scored)
    learner.save_memory(mem)

    targets = allocate(scored, fund, cfg)
    if reg["size_mult"] != 1.0:
        targets = {k: v * reg["size_mult"] for k, v in targets.items()}

    sig_rows = []
    for s in scored:
        if s.symbol not in targets:
            continue
        w = targets[s.symbol]
        sig_rows.append({
            "Symbol": s.symbol,
            "Action": "BUY in Gotrade",
            "$ Amount": round(fund * w, 2),
            "Est. qty": round(fund * w / s.price, 4) if s.price else 0,
            "Prob. up": f"{s.prob_up:.1%}",
            "Weight": f"{w:.1%}",
        })
    sig_df = pd.DataFrame(sig_rows) if sig_rows else pd.DataFrame(
        [{"Message": "HOLD cash — nothing passes the filter"}])

    score_rows = [{
        "Symbol": s.symbol,
        "Price": round(s.price, 2),
        "Prob. up": f"{s.prob_up:.1%}",
        "Expected": round(s.expected_return, 5),
        "Kelly": round(s.kelly, 2),
        "Trust": round(getattr(s, "trust", 1.0), 2),
        "Mom 20d": f"{s.momentum_20d:.1%}",
        "Sharpe": round(s.sharpe, 2),
    } for s in scored]
    score_df = pd.DataFrame(score_rows) if score_rows else pd.DataFrame(
        [{"Message": "No candidates"}])

    regime_md = f"**{reg['label']}** — {reg['reason']}"
    learn_md = learner.stats_line(mem, list(histories.keys()))
    return sig_df, score_df, regime_md, learn_md


with gr.Blocks(title="GoTrade Auto-Invest") as demo:
    gr.Markdown("# 🤖 GoTrade Auto-Invest\nHighest-probability signals for your Gotrade app.")
    fund_in = gr.Number(value=6.0, label="Fund amount ($)", precision=2)
    btn = gr.Button("Refresh signals", variant="primary")
    sig_out = gr.Dataframe(label="Today's orders (execute in Gotrade)")
    score_out = gr.Dataframe(label="All ranked candidates")
    regime_out = gr.Markdown()
    learn_out = gr.Markdown()
    btn.click(refresh, inputs=fund_in,
              outputs=[sig_out, score_out, regime_out, learn_out])
    demo.load(refresh, inputs=fund_in,
              outputs=[sig_out, score_out, regime_out, learn_out])

if __name__ == "__main__":
    demo.launch(mcp_server=True)
