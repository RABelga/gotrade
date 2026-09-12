"""Telegram alerts (stdlib only — urllib, no new packages).

Setup (5 min, on your phone):
  1. Chat with @BotFather -> /newbot -> copy the token.
  2. Open your new bot chat, press Start (send any message).
  3. Get your chat id: open in a browser
       https://api.telegram.org/bot<TOKEN>/getUpdates
     and copy "chat":{"id": 123456789.
     (Or message @userinfobot — it replies with your id.)
  4. Either edit config.json -> "telegram" section, or set env vars:
       setx TELEGRAM_BOT_TOKEN "123:ABC"
       setx TELEGRAM_CHAT_ID "123456789"
     then restart the terminal.
"""
import json
import os
import urllib.request


def get_creds(cfg: dict) -> tuple[str | None, str | None]:
    tg = (cfg or {}).get("telegram") or {}
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or tg.get("bot_token") or None
    chat = os.environ.get("TELEGRAM_CHAT_ID") or tg.get("chat_id") or None
    token = str(token).strip() if token else None
    chat = str(chat).strip() if chat else None
    if token in ("", "PASTE_TOKEN_HERE"):
        token = None
    if chat in ("", "PASTE_CHAT_ID_HERE"):
        chat = None
    return token, chat


def send(token: str, chat_id: str, text: str, timeout: int = 15) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
            return bool(body.get("ok"))
    except Exception as e:
        print(f"[telegram] send failed: {e}")
        return False


def alert_cfg(cfg: dict, text: str) -> bool:
    """Send if configured, else print why skipped. Returns True if sent."""
    token, chat = get_creds(cfg)
    if not token or not chat:
        print("[telegram] not configured — set bot_token/chat_id (see src/telegram.py).")
        return False
    ok = send(token, chat, text)
    print(f"[telegram] {'sent' if ok else 'FAILED'}")
    return ok
