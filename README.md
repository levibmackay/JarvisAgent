# Jarvis

A modular AI assistant for macOS. Currently: a terminal chat agent with a
plugin tool system, powered by a hosted large-language-model API.

## Setup

```sh
uv sync
export ANTHROPIC_API_KEY=...   # or `ant auth login`
uv run jarvis
```

## Architecture

- `jarvis/core/agent.py` — turn engine: LLM ↔ tool dispatch loop
- `jarvis/core/llm/` — provider abstraction (`base.py`) + hosted-LLM implementation
- `jarvis/core/config.py` — typed settings (`JARVIS_*` env vars / `.env`)
- `jarvis/tools/` — plugin protocol (`base.py`); tools: `get_time`, `run_shell`, `read_file`, `write_file`, `edit_file`, `github`, `remember`, `recall`, plus Calendar.app (`list_events`, `create_event`) and Mail.app (`list_emails`, `read_email`, `send_email`) via AppleScript. Personal-data tools can be disabled with `JARVIS_ENABLE_PERSONAL_TOOLS=false`; `send_email` always requires confirmation.
- `jarvis/memory/` — SQLite store (`~/.jarvis/jarvis.db`): conversation persistence + long-term facts with FTS5 recall; recent facts are seeded into the system prompt at startup
- `jarvis/security/` — consent manager, JSONL audit log (`~/.jarvis/audit.jsonl`), path confinement, `SafeExecutor`
- `jarvis/voice/` — TTS (macOS `say`), STT (whisper.cpp), push-to-talk recorder
- `jarvis/interfaces/cli.py` — streaming REPL (`/voice`, `/clear`, `/exit`)

## Voice mode

```sh
uv sync --extra voice                # mic capture (sounddevice)
brew install whisper-cpp             # local speech-to-text
curl -L --create-dirs -o ~/.jarvis/models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

Then type `/voice` in the REPL: Enter starts recording, Enter stops,
transcription runs locally (audio never leaves the Mac), and the reply is
spoken aloud. Wake word and barge-in are planned.

## API server (for the menu bar / iPhone apps)

```sh
uv sync --extra server
jarvis-server                        # http://127.0.0.1:8765, loopback only
```

Auth is a bearer token auto-generated at `~/.jarvis/server.token` (0600).
Endpoints (`/v1`): `POST /sessions`, `POST /sessions/{id}/messages`
(SSE stream: `text`, `tool_use`, `consent_request`, `done`, `error`),
`POST /sessions/{id}/consent/{consent_id}` `{"allow": bool}`,
`DELETE /sessions/{id}`, `GET /health`. One turn per session at a time
(409 while busy). Consent requests unanswered for `JARVIS_CONSENT_TIMEOUT`
(default 300s) are denied.

## Workflows

Drop JSON files in `~/.jarvis/workflows/` and the server runs them on
schedule (`every 15m`, `daily 08:00`, or `weekly mon 09:00`):

```json
{"name": "morning-brief", "schedule": "daily 08:00",
 "prompt": "Summarize my unread email and today's calendar.",
 "allow_tools": ["list_emails", "list_events"], "notify": true}
```

Workflows run unattended, so consent is policy-based: read-only tools run
freely, reversible tools only if listed in `allow_tools`, destructive
calls are always denied. Results arrive as macOS notifications and land in
run history (`GET /v1/workflows/{name}/runs`); trigger manually with
`POST /v1/workflows/{name}/run`. Edits to the JSON files are picked up on
the next scheduler poll (30s) — no restart.

## Meetings

```sh
brew install blackhole-2ch    # system-audio loopback (then create a
                              # Multi-Output Device in Audio MIDI Setup)
```

Type `/meeting` in the REPL: records from the device named by
`JARVIS_MEETING_DEVICE` (default "BlackHole"; set it empty to use the
mic), Enter stops, transcription runs locally, and the agent writes a
summary with decisions and action items. Artifacts per meeting in
`~/.jarvis/meetings/<timestamp>/`: `audio.wav`, `transcript.txt`,
`summary.md`. Only the transcript text reaches the LLM.

## Menu bar app

`apps/macos/JarvisBar` is a SwiftPM package (no Xcode required — CLT is
enough): `JarvisKit` (API client + SSE parsing, reusable by a future iOS
app) and the `JarvisBar` MenuBarExtra UI with streaming replies and
Allow/Deny consent cards.

```sh
jarvis-server &                       # the app talks to this
cd apps/macos/JarvisBar
swift run JarvisBar                   # or: swift build -c release
swift test                            # JARVIS_INTEGRATION=1 adds a live-server test
```

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

_Last updated: 2026-07-20_
