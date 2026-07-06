"""Terminal REPL — the first interface to the agent core."""

import sys

import anthropic

from jarvis.core.agent import Agent
from jarvis.core.config import Settings
from jarvis.core.llm.claude import ClaudeProvider
from jarvis.memory.store import MemoryStore
from jarvis.memory.tools import RecallTool, RememberTool
from jarvis.security.audit import AuditLog
from jarvis.security.consent import CliConsent, ConsentManager
from jarvis.security.executor import SafeExecutor
from jarvis.tools.base import ToolRegistry
from jarvis.tools.builtin.time import GetTimeTool
from jarvis.tools.calendar import CreateEventTool, ListEventsTool
from jarvis.tools.email import ListEmailsTool, ReadEmailTool, SendEmailTool
from jarvis.tools.files import EditFileTool, ReadFileTool, WriteFileTool
from jarvis.tools.github import GitHubTool
from jarvis.tools.shell import ShellTool
from jarvis.voice.base import VoiceError
from jarvis.voice.recorder import record_push_to_talk
from jarvis.voice.stt import WhisperCppSTT
from jarvis.voice.tts import MacSayTTS


def build_agent(
    settings: Settings,
    store: MemoryStore | None = None,
    consent: ConsentManager | None = None,
) -> Agent:
    roots = settings.permitted_roots
    registry = ToolRegistry()
    registry.register(GetTimeTool())
    registry.register(ShellTool(roots, timeout=settings.shell_timeout))
    registry.register(ReadFileTool(roots))
    registry.register(WriteFileTool(roots))
    registry.register(EditFileTool(roots))
    registry.register(GitHubTool(roots))
    if settings.enable_personal_tools:
        for tool_cls in (ListEventsTool, CreateEventTool, ListEmailsTool,
                         ReadEmailTool, SendEmailTool):
            registry.register(tool_cls())

    system_prompt = settings.system_prompt
    on_message = None
    if store is not None:
        registry.register(RememberTool(store))
        registry.register(RecallTool(store))
        facts = store.recent_facts(settings.seed_facts)
        if facts:
            system_prompt += "\n\nKnown facts from previous sessions:\n" + "\n".join(
                f"- {f}" for f in facts
            )
        conversation_id = store.create_conversation()
        on_message = lambda m: store.add_message(  # noqa: E731
            conversation_id, m["role"], m["content"]
        )

    executor = SafeExecutor(registry, consent or CliConsent(), AuditLog(settings.audit_log_path))
    provider = ClaudeProvider(model=settings.model, max_tokens=settings.max_tokens)
    return Agent(provider, executor, system_prompt, on_message=on_message)


def run_agent_turn(agent: Agent, user_input: str) -> str | None:
    """One turn with streaming output and typed error handling.

    Returns the final reply text, or None on error.
    """
    print("jarvis> ", end="", flush=True)
    try:
        reply = agent.run_turn(
            user_input,
            on_text=lambda t: print(t, end="", flush=True),
            on_tool_use=lambda name, params: print(f"\n[tool: {name} {params}]", file=sys.stderr),
        )
    except anthropic.APIConnectionError:
        print("\nNetwork error — check your connection and retry.", file=sys.stderr)
        return None
    except anthropic.AuthenticationError:
        print(
            "\nNo valid credentials. Set ANTHROPIC_API_KEY or run `ant auth login`.",
            file=sys.stderr,
        )
        return None
    except anthropic.APIStatusError as exc:
        print(f"\nAPI error {exc.status_code}: {exc.message}", file=sys.stderr)
        return None
    print()
    return reply


def voice_loop(agent: Agent, settings: Settings) -> None:
    """Push-to-talk conversation: Enter records, Enter stops, reply is spoken."""
    stt = WhisperCppSTT(settings.stt_model_path, settings.stt_binary)
    tts = MacSayTTS(settings.tts_voice, settings.tts_rate)
    print("(voice mode — Enter to talk, 'q' + Enter to leave)")

    while True:
        if input("\n[voice] Enter=talk, q=quit> ").strip().lower() == "q":
            return
        try:
            wav = record_push_to_talk()
            try:
                text = stt.transcribe(wav)
            finally:
                wav.unlink(missing_ok=True)
        except VoiceError as exc:
            print(f"Voice error: {exc}", file=sys.stderr)
            return
        if not text:
            print("(heard nothing)")
            continue
        print(f"you> {text}")
        reply = run_agent_turn(agent, text)
        if reply:
            try:
                tts.speak(reply)
            except KeyboardInterrupt:
                tts.stop()
            except VoiceError as exc:
                print(f"Voice error: {exc}", file=sys.stderr)


def main() -> int:
    settings = Settings()
    store = MemoryStore(settings.db_path)
    agent = build_agent(settings, store)
    print(f"Jarvis ({settings.model}) — /voice talks, /clear resets, /exit quits.")

    while True:
        try:
            user_input = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            return 0
        if user_input == "/clear":
            agent.reset()
            print("(conversation cleared)")
            continue
        if user_input == "/voice":
            voice_loop(agent, settings)
            continue

        run_agent_turn(agent, user_input)


if __name__ == "__main__":
    raise SystemExit(main())
