# Rifo Traveling — Gemini Live Voice Agent

A local prototype of **Sandra**, a natural-sounding voice support agent for the airline *Rifo Traveling*, built on Gemini Live.

Sandra talks like a real person — small pauses, light disfluencies, a beat before reading back a result — and looks up bookings through a tool call instead of inventing details. The browser UI is chat-first: start a session, type or speak, hear Gemini's audio reply, and watch tool calls stream in.

## Model

```text
gemini-3.1-flash-live-preview
```

## Setup

```bash
uv sync
cp .env.example .env
```

Then set your key in `.env`:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-key
```

## Run

```bash
uv run python main.py
```

Open <http://127.0.0.1:8000> and try:

```text
Can you look up booking 271234567?
```

## Test

```bash
uv run pytest -q
```

## Project layout

```text
app/      FastAPI server, Gemini Live bridge, system prompt, tools
static/   Chat UI (HTML/CSS/JS) + voice samples
scripts/  Voice-sample generator
tests/    Unit tests
```
