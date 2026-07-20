# Project notes

Internal working notes for Jarvis. Not user-facing — see README.md for that.

## Current state (as of 2026-07-20)

Milestones M1 through M8 are done (see git log): agent core + safe execution +
memory + GitHub tools, voice mode, calendar/email via AppleScript, the local
FastAPI/SSE server, the SwiftUI menu bar app, and automation workflows +
meeting transcription. 114 tests pass, ruff is clean, no TODO/FIXME markers
anywhere in the tree — the codebase is in a tidy state right now, not
mid-refactor.

Test/lint baseline to reproduce before starting new work:

```sh
uv run pytest      # 114 passed
uv run ruff check .  # All checks passed
```

## Architecture decisions worth remembering

- **SafeExecutor wraps ToolRegistry via duck typing**, not inheritance
  (`jarvis/security/executor.py`). The Agent only ever sees something with
  `schemas()`/`execute()` — it doesn't know a consent/audit layer exists.
  Keep this indirection if adding new tool-execution paths (e.g. workflow
  runner) — don't let them bypass SafeExecutor and call the registry
  directly, or consent/audit silently stop applying.
- **Risk classification is per-call, not per-tool.** `tool.classify(params)`
  runs on every invocation (see `executor.py`), so the same tool can be
  `read_only` for a `list_events` and `destructive` for `send_email`-style
  calls. Don't cache risk level per tool name anywhere.
- **Workflows use policy-based consent, not interactive consent** — by
  design, since nothing is watching a terminal at 8am when a scheduled
  workflow fires. Read-only tools run free, reversible tools need
  `allow_tools`, destructive is always denied outright. This is a
  deliberately different trust model from the REPL/server paths and should
  stay that way — don't try to unify them.
- **Shell auto-allow is intentionally narrow**: only commands that parse
  cleanly with no shell metacharacters and use a short allowlisted binary
  set (`ls`, `pwd`, `date`, ...) skip confirmation. Resist the urge to grow
  that allowlist casually — it's the one place a mistake turns into
  arbitrary code execution without a prompt.
- **Voice and meetings both do local-only STT** (whisper.cpp / `whisper-cli`
  binary) — audio and transcripts never touch the LLM API except as the
  final text. This is a stated privacy property in the README; don't
  introduce a cloud STT fallback without flagging that it changes this
  guarantee.
- **The env var is literally `ANTHROPIC_API_KEY`** — hardcoded expectation
  in `config.py`, `core/llm/claude.py`, and `interfaces/cli.py`. If a second
  LLM provider is ever added behind the `core/llm/base.py` abstraction,
  this naming will need to become provider-scoped.

## Known gaps / TODOs (not tracked as code comments, so noting here)

- Wake word and barge-in for voice mode are explicitly unimplemented
  (mentioned in README as "planned"). No scaffolding for either exists yet
  in `jarvis/voice/`.
- No CI workflow file (no `.github/workflows/`) — tests and ruff are run
  manually. Worth adding a basic GitHub Actions job (pytest + ruff) given
  how easy the test suite already is to run.
- `apps/macos/JarvisBar` has its own `swift test` suite gated behind
  `JARVIS_INTEGRATION=1` for the live-server test; that variable is not
  documented anywhere except the README's one-liner and the Swift test
  file itself — easy to forget when running the full check locally.
- No packaging/release story yet (no PyInstaller/py2app, no signed macOS
  app bundle for JarvisBar) — currently everything runs from source via
  `uv run` / `swift run`.
- `jarvis/tools/builtin/` currently only has `time.py` (`get_time`) — most
  tools actually live directly under `jarvis/tools/`, not `builtin/`. The
  split between the two directories doesn't currently mean anything
  functionally; worth deciding whether `builtin/` is going to be the future
  home for all first-party tools or should just be collapsed.

## Ideas for next steps

- CI: GitHub Actions matrix running `uv run pytest` + `uv run ruff check`
  on push, given zero setup cost.
- A packaged menu-bar app build (notarized .app) once JarvisBar stabilizes,
  so it doesn't require `swift run` from a checkout.
- Consider whether workflow run history (`~/.jarvis` runs) needs pruning —
  no retention/rotation policy currently exists for it, the audit log
  (`audit.jsonl`), or meeting artifacts (`~/.jarvis/meetings/<timestamp>/`).
  All three grow unbounded today.
- An iPhone companion app is on the original project roadmap but nothing
  exists for it yet beyond `JarvisKit` being deliberately structured as a
  reusable API client for that purpose.
