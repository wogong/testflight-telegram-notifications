# TestFlight Telegram Notifications

Monitor an iOS TestFlight public beta link and receive a Telegram notification
when slots appear to open. Runs once for cron or continuously as a small Python
process. No Apple account is required, and the script does not enroll testers.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A TestFlight public join link and a Telegram bot

## Setup

```bash
git clone https://github.com/wogong/testflight-telegram-notifications.git
cd testflight-telegram-notifications
uv sync --locked
cp .env.example .env
```

Edit `.env` with your values. Create a bot through
[@BotFather](https://t.me/BotFather), then send your bot a message (or add it to
the target group). Use the Telegram Bot API `getUpdates` method to find the
message's `chat.id`. For a channel, give the bot permission to post messages.
Keep the bot token private, including when sharing logs or API responses.

| Variable | Required | Description / default |
| --- | --- | --- |
| `TF_URL` | Yes | Public URL: `https://testflight.apple.com/join/XXXXXXXX` |
| `TG_BOT_TOKEN` | Yes | Token issued by BotFather |
| `TG_CHAT_ID` | Yes | Destination user, group, or channel chat ID |
| `CHECK_INTERVAL` | No | Seconds between loop checks; default `300` |
| `HTTP_TIMEOUT` | No | HTTP request timeout in seconds; default `20` |

Use positive integers for interval and timeout. Existing environment variables
take precedence over `.env`. The config file must exist, even if you supply all
values through the environment. The simple loader supports `KEY=VALUE`, optional
surrounding quotes, and full-line `#` comments; it does not expand variables.

## Run

```bash
uv run --locked python monitor.py
uv run --locked python monitor.py --loop
uv run --locked python monitor.py --env /path/to/custom.env
```

The default `.env` is read from the script directory. Stop loop mode with Ctrl-C.
Loop checks are separated by `CHECK_INTERVAL` seconds after each check completes.

For cron, replace both absolute paths below with your checkout path and the
output of `command -v uv`:

```cron
*/5 * * * * cd /path/to/testflight-telegram-notifications && /absolute/path/to/uv run --locked python monitor.py >> monitor.log 2>&1
```

Use either cron or loop mode for a checkout, and arrange log rotation for
long-running installations.

## Notification behavior

- The first check sends a notification if the beta appears open.
- Subsequent checks notify only on a closed-to-open transition.
- State is stored in `.tf_state.json` next to the script. Deleting it resets
  notification history. Reset it when changing the monitored beta.
- Network failures leave state unchanged. A failed Telegram request is retried
  on the next check if the beta still appears open.
- Each checkout supports one beta and one running monitor; custom `.env` files
  still share the same state file.

## Limitations and troubleshooting

Availability is a heuristic based on Apple's English public join page and known
closed-beta phrases. It is not an official API: page changes, unexpected content,
or localized responses can cause false positives or missed openings. A
notification does not guarantee a slot is still available when you open the link.
This project is not affiliated with Apple or Telegram.

If notifications do not arrive, verify the chat ID, start a conversation with
the bot, and check that it has permission to post. Check stderr for request
failures. Request failures are logged but currently do not produce a nonzero
exit status in one-shot mode. Never attach `.env` or raw bot API URLs to issues.

## Development and contributions

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
```

Tests use temporary state files and mocked HTTP calls; they do not contact Apple
or Telegram or read your `.env`. GitHub Actions runs them on Python 3.12 and 3.14.

Issues and pull requests are welcome. Include steps to reproduce bugs, redact
credentials and chat IDs, and add regression tests for behavior changes. Keep
changes focused and run the tests before submitting a pull request.

## License

[MIT](LICENSE)
