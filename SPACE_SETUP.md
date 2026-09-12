# Run GoTrade on a server (free)

You have two free pieces that work together. Pick one or both:

## A. Dashboard on Hugging Face Spaces (see signals in a browser)

1. Go to https://huggingface.co/spaces -> **Create new Space**
   - SDK: **Gradio**, Hardware: CPU basic (free)
2. Upload this whole `GoTrade` folder contents (`app.py`, `src/`, `requirements.txt`,
   `config.json`, `run.py`). When asked, keep the Gradio SDK.
3. (Optional) Space Settings -> Variables & secrets -> add
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` if you want Telegram from the Space.
4. Open your Space URL — the dashboard auto-loads signals. Press **Refresh signals**.

Note: free Spaces sleep after ~48h of no visitors. The dashboard wakes when you open it.
For alerts while your PC is off, add part B.

## B. Scheduled Telegram alerts via GitHub Actions (free, no sleeping)

1. Push this folder to a GitHub repo.
2. Repo **Settings -> Secrets and variables -> Actions** -> add
   `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. The workflow in `.github/workflows/daily-signals.yml` runs weekdays at 13:00 UTC
   and Telegram-messages you only when the pick/regime changes.
   Trigger it anytime with **Actions -> daily-signals -> Run workflow**.

## Secrets, never commit tokens

- Keep real tokens in Space secrets / GitHub secrets / local env vars, NOT in `config.json`.
- `config.json` keeps placeholders (`PASTE_TOKEN_HERE`) — git-safe.
