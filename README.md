# Jarvis

A modular AI assistant for macOS. Currently: a terminal chat agent with a
plugin tool system, powered by the Claude API.

## Setup

```sh
uv sync
export ANTHROPIC_API_KEY=...   # or `ant auth login`
uv run jarvis
```

## Architecture

- `jarvis/core/agent.py` — turn engine: LLM ↔ tool dispatch loop
- `jarvis/core/llm/` — provider abstraction (`base.py`) + Claude implementation
- `jarvis/core/config.py` — typed settings (`JARVIS_*` env vars / `.env`)
- `jarvis/tools/` — plugin protocol (`base.py`); tools: `get_time`, `run_shell`, `read_file`, `write_file`, `edit_file`, `github`, `remember`, `recall`, plus Calendar.app (`list_events`, `create_event`) and Mail.app (`list_emails`, `read_email`, `send_email`) via AppleScript. Personal-data tools can be disabled with `JARVIS_ENABLE_PERSONAL_TOOLS=false`; `send_email` always requires confirmation.
- `jarvis/memory/` — SQLite store (`~/.jarvis/jarvis.db`): conversation persistence + long-term facts with FTS5 recall; recent facts are seeded into the system prompt at startup
- `jarvis/security/` — consent manager, JSONL audit log (`~/.jarvis/audit.jsonl`), path confinement, `SafeExecutor`
- `jarvis/voice/` — TTS (macOS `say`), STT (whisper.cpp), push-to-talk recorder
- `jarvis/interfaces/cli.py` — streaming REPL (`/voice`, `/clear`, `/exit`)

## Voice mode

```sh
pip install 'jarvis[voice]'          # mic capture (sounddevice)
brew install whisper-cpp             # local speech-to-text
curl -L --create-dirs -o ~/.jarvis/models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

Then type `/voice` in the REPL: Enter starts recording, Enter stops,
transcription runs locally (audio never leaves the Mac), and the reply is
spoken aloud. Wake word and barge-in are planned.

## API server (for the menu bar / iPhone apps)

```sh
pip install 'jarvis[server]'
jarvis-server                        # http://127.0.0.1:8765, loopback only
```

Auth is a bearer token auto-generated at `~/.jarvis/server.token` (0600).
Endpoints (`/v1`): `POST /sessions`, `POST /sessions/{id}/messages`
(SSE stream: `text`, `tool_use`, `consent_request`, `done`, `error`),
`POST /sessions/{id}/consent/{consent_id}` `{"allow": bool}`,
`DELETE /sessions/{id}`, `GET /health`. One turn per session at a time
(409 while busy). Consent requests unanswered for `JARVIS_CONSENT_TIMEOUT`
(default 300s) are denied.

## Security model

Every tool call is risk-classified per call (`read_only` / `reversible` /
`destructive`). Read-only calls run automatically; everything else prompts
you with the exact parameters (`y`/`N`/`a` = allow tool for session). All
attempts — allowed, denied, or failed — are appended to the audit log.
File tools and shell working directories are confined to
`JARVIS_PERMITTED_ROOTS` (default: your home directory). Shell commands are
auto-allowed only when they parse cleanly, contain no shell metacharacters,
and use a benign binary (`ls`, `pwd`, `date`, …); anything else asks first.

## Tests

```sh
uv run pytest
```
