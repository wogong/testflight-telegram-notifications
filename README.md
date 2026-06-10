# iOS TestFlight availability monitor

Watches a TestFlight **public** beta join link and sends a Telegram message the
moment the beta starts accepting new testers again.

## How it works

Apple's public join page (`https://testflight.apple.com/join/XXXX`) shows a
"This beta is full." message when no slots are open. The script fetches that
page and notifies you when that marker disappears. It tracks the last known
state in `.tf_state.json` and only notifies on the **unavailable → available**
transition, so you won't be spammed every check.

## Setup

```bash
uv sync                  # install dependencies into .venv
cp .env.example .env     # then edit .env with your values
```

Fill in `.env`:

- `TF_URL` — the TestFlight join link
- `TG_BOT_TOKEN` — bot token from [@BotFather](https://t.me/BotFather)
- `TG_CHAT_ID` — your chat id (message the bot, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` to find it)
- `CHECK_INTERVAL` — seconds between checks in loop mode (default 300)

## Run

```bash
uv run python monitor.py          # check once (good for cron)
uv run python monitor.py --loop   # check forever on CHECK_INTERVAL
```

### Run as a cron job (every 5 minutes)

```cron
*/5 * * * * cd /home/wogong/Dropbox/Repos/ios_tf_notification && /home/wogong/.local/bin/uv run python monitor.py >> monitor.log 2>&1
```
