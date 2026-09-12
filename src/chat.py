"""Two-way Telegram chat: you talk to @USgoTradeBot, it answers.

Owner-only: messages from anyone but TELEGRAM_CHAT_ID are ignored.
Brain: free Hugging Face Inference Providers (Qwen via featherless-ai),
using your existing `hf auth login` token. No extra API key needed.

Usage:
    python run.py chat [fund_amount]     # polls forever; keep window open
"""
import json
import time
import urllib.request
from pathlib import Path

from . import telegram as tg
from .signals import generate_signals
from .bot import load_config
from . import learner

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "signals.json"

SYSTEM = ("You are GoTrade Bot, a helpful assistant for a small $6 stock fund. "
          "The fund uses a probability model (win-rate + momentum + Sharpe, Kelly sizing) "
          "on US stocks via the Gotrade app (fractional, manual orders). "
          "Be concise, honest about uncertainty, never promise profits. "
          "If asked what to buy, refer to the today's-signals context given.")


def _context(cfg: dict, fund: float) -> str:
    """Fresh-ish context: reuse signals.json if <12h old, else regenerate."""
    sig = None
    try:
        sig = json.loads(CACHE.read_text())
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) -
               datetime.fromisoformat(sig["generated_at"])).total_seconds()
        if age > 12 * 3600:
            sig = None
    except Exception:
        sig = None
    if sig is None:
        try:
            sig = generate_signals(cfg, fund)
            CACHE.write_text(json.dumps(sig, indent=2))
        except Exception as e:
            return f"(live data unavailable: {e})"
    orders = sig.get("orders", []) or "HOLD cash (nothing passes)"
    reg = sig.get("regime") or {}
    return (f"Today's orders: {orders}. Market regime: {reg.get('label')} "
            f"({reg.get('reason')}). Fund: ${fund:,.2f}.")


def ask_llm(question: str, context: str) -> str:
    from huggingface_hub import InferenceClient
    for provider, model in [("featherless-ai", "Qwen/Qwen2.5-7B-Instruct"),
                            ("cohere", "CohereLabs/c4ai-command-r7b-12-2024")]:
        try:
            c = InferenceClient(provider=provider)
            r = c.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM + "\n" + context},
                          {"role": "user", "content": question[:2000]}],
                max_tokens=400)
            return r.choices[0].message.content.strip()
        except Exception as e:
            print(f"[chat] llm {provider} failed: {str(e).splitlines()[0][:120]}")
    return "My AI brain is unreachable right now — try /signals for today's orders."


def _send(token: str, chat_id: str, text: str) -> None:
    for i in range(0, max(len(text), 1), 4000):
        tg.send(token, chat_id, text[i:i + 4000] or "(empty reply)")


def handle(text: str, cfg: dict, fund: float) -> str:
    t = (text or "").strip()
    low = t.lower()
    if low.startswith("/start") or low.startswith("/help"):
        return ("I'm your GoTrade bot 🤖\n"
                "/signals — today's buy orders\n"
                "/status — regime + learning hit-rates\n"
                "Or just ask me anything about your fund.")
    if low.startswith("/signals"):
        try:
            amt = float(low.split()[1]) if len(low.split()) > 1 else fund
        except Exception:
            amt = fund
        sig = generate_signals(cfg, amt)
        CACHE.write_text(json.dumps(sig, indent=2))
        if not sig["orders"]:
            return "HOLD cash — nothing passes the filter today."
        lines = [f"BUY {o['symbol']}: ${o['dollars']:,.2f} (~{o['est_qty']} sh) | p={o['prob_up']:.1%}"
                 for o in sig["orders"]]
        return f"Today's orders (${amt:,.2f}):\n" + "\n".join(lines)
    if low.startswith("/status"):
        mem = learner.load_memory()
        return ("Market: run /signals for regime.\n"
                f"Learning: {learner.stats_line(mem, cfg['universe'])}")
    return ask_llm(t, _context(cfg, fund))


def loop(cfg: dict, fund: float) -> None:
    token, owner = tg.get_creds(cfg)
    if not token or not owner:
        print("[chat] set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID first.")
        return
    print(f"[chat] listening as @USgoTradeBot for owner {owner}. Press Ctrl+C to stop.")
    offset = 0
    while True:
        try:
            data = json.dumps(
                {"offset": offset, "timeout": 50}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/getUpdates",
                data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=70) as r:
                updates = json.loads(r.read().decode()).get("result", [])
            for u in updates:
                offset = max(offset, u["update_id"] + 1)
                m = u.get("message") or {}
                chat_id = str((m.get("chat") or {}).get("id", ""))
                text = m.get("text", "")
                if not text or chat_id != str(owner):
                    continue  # owner-only
                print(f"[chat] you: {text[:80]}")
                try:
                    reply = handle(text, cfg, fund)
                except Exception as e:
                    reply = f"Error: {e}"
                _send(token, chat_id, reply)
        except Exception as e:
            print(f"[chat] poll error: {str(e).splitlines()[0][:150]}")
            time.sleep(5)
