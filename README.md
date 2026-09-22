# noticias-linux

Daily Linux news digest. Aggregates RSS feeds, summarizes articles with a local
Ollama model, and sends a curated digest to a Telegram chat.

Runs as a cron job (designed for Termux on Android, but the Python script works
anywhere Python + Ollama + Telegram are available).

## What it does

1. Pulls RSS feeds from a configurable list of Linux news sources.
2. Picks the top N articles per feed (default: 1).
3. Sends each article through a local Ollama model (`qwen3:0.6b` by default)
   with a short prompt that asks for a 3-bullet summary in Spanish.
4. Builds a Telegram message with all summaries and posts it to the configured
   chat.

## Requirements

- Python 3.11+
- A running Ollama daemon (`http://localhost:11434`)
- A Telegram bot token + chat id
- Bash + cron (for the scheduled runner)

## Setup

```bash
git clone https://github.com/bramirezjofre/noticias-linux.git
cd noticias-linux

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in:
#   - TELEGRAM_BOT_TOKEN (from @BotFather)
#   - TELEGRAM_CHAT_ID    (your chat id)

# Make sure Ollama is running and the model is pulled:
ollama pull qwen3:0.6b
```

## Running

One-off:

```bash
bash run_noticias.sh
```

Or directly:

```bash
source .venv/bin/activate
python noticias_linux.py
```

## Scheduling (cron)

The original setup runs on a Samsung S20 FE via Termux, every day at 09:00:

```
0 9 * * * /data/data/com.termux/files/home/noticias-linux/run_noticias.sh
```

## Configuration

All config is via environment variables (loaded from `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen3:0.6b` | Local model for summarization |
| `TELEGRAM_BOT_TOKEN` | *(required)* | Telegram bot token |
| `TELEGRAM_CHAT_ID` | *(required)* | Destination chat id |
| `NOTICIAS_POR_FEED` | `1` | Articles to summarize per feed |
| `MAX_CONTEXTO_NOTICIA` | `1000` | Max chars fed to the LLM per article |

## Security notes

- **`.env` is git-ignored.** Never commit your real bot token or chat id.
- Use `.env.example` as the template for new deployments.
- The bot token only needs `sendMessage` scope (default for `@BotFather` bots).

## License

MIT (do whatever, attribution appreciated).
