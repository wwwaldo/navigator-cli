"""Navigator CLI — chat with Claude and learn your preferences."""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .client import build_chat_options, chat_turn
from .config import get_model, get_token, set_api_key, set_model, set_token
from .evaluator import run_learn
from .store import append_conversation, clear_preferences, load_preferences

app = typer.Typer(
    name="navigator",
    help="Chat with Claude through your terminal. Learns your preferences over time.",
)
console = Console()


@app.command()
def chat(
    cwd: Path | None = typer.Option(
        None,
        "--cwd",
        help="Working directory for Claude (default: current directory)",
    ),
):
    """Start a conversation with Claude."""
    token = get_token()
    if not token:
        console.print(
            "[red]No API key configured.[/red]\n"
            "Get one at [bold]console.anthropic.com[/bold], then: [bold]navigator config --api-key sk-ant-...[/bold]"
        )
        raise typer.Exit(1)

    # OAuth/setup-tokens (sk-ant-oat01-) are rejected by the API for programmatic access
    if token.strip().startswith("sk-ant-oat01-"):
        console.print(
            "[yellow]Warning:[/yellow] Setup-token (OAuth) is configured, but the API returns "
            "'OAuth authentication is currently not supported' for programmatic access.\n"
            "Use an API key instead: [bold]navigator config --api-key sk-ant-...[/bold] "
            "(from console.anthropic.com)"
        )
        raise typer.Exit(1)

    working_dir = (cwd if cwd and cwd.exists() else None) or Path.cwd()
    options = build_chat_options(cwd=working_dir)

    conversation_id = str(uuid.uuid4())
    all_messages: list[dict] = []
    conversation_saved = [False]

    async def run_chat():
        from claude_agent_sdk import ClaudeSDKClient

        async with ClaudeSDKClient(options=options) as client:
            console.print(
                Panel(
                    "[dim]Type your message and press Enter. Type 'exit' or press Ctrl+C to end.[/dim]",
                    title="Navigator",
                    border_style="blue",
                )
            )

            while True:
                try:
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: Prompt.ask("\n[bold cyan]You[/bold cyan]"),
                    )
                except (EOFError, KeyboardInterrupt):
                    break

                user_input = (user_input or "").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    if all_messages:
                        with console.status("Saving conversation...", spinner="dots"):
                            append_conversation(conversation_id, all_messages)
                        console.print(f"\n[dim]Conversation saved ({len(all_messages)} messages).[/dim]")
                        conversation_saved[0] = True
                    break

                assistant_label_printed = [False]

                # Anthropic warm brown (#D4A574) from official brand palette
                claude_style = "bold #d4a574"

                def stream_chunk(text: str) -> None:
                    if not assistant_label_printed[0]:
                        console.print(f"[{claude_style}]Claude[/{claude_style}]: ", end="")
                        assistant_label_printed[0] = True
                    console.print(text, end="")

                def stream_tool(name: str, inp: dict, result: str) -> None:
                    if not assistant_label_printed[0]:
                        console.print(f"[{claude_style}]Claude[/{claude_style}]:")
                        assistant_label_printed[0] = True
                    # Brief input summary (e.g. path for Read, command for Bash)
                    inp_preview = ""
                    if name == "Read" and "path" in inp:
                        inp_preview = f" {inp['path']}"
                    elif name == "Bash" and "command" in inp:
                        inp_preview = f" {inp['command'][:60]}{'...' if len(str(inp.get('command',''))) > 60 else ''}"
                    elif name == "Edit" and "path" in inp:
                        inp_preview = f" {inp['path']}"
                    elif name == "Write" and "path" in inp:
                        inp_preview = f" {inp['path']}"
                    elif name == "Glob" and "pattern" in inp:
                        inp_preview = f" {inp['pattern']}"
                    elif name == "Grep" and "pattern" in inp:
                        inp_preview = f" {inp['pattern']}"
                    console.print(Panel(result, title=f"[dim]Tool: {name}{inp_preview}[/dim]", border_style="dim"))
                messages, _ = await chat_turn(client, user_input, on_chunk=stream_chunk, on_tool=stream_tool)
                all_messages.extend(messages)
                console.print()  # newline after response, before next prompt

    try:
        asyncio.run(run_chat())
    except KeyboardInterrupt:
        pass

    # Save on Ctrl+C (exit path saves before breaking)
    if all_messages and not conversation_saved[0]:
        with console.status("Saving conversation...", spinner="dots"):
            append_conversation(conversation_id, all_messages)
        console.print(f"\n[dim]Conversation saved ({len(all_messages)} messages).[/dim]")


@app.command()
def learn():
    """Process recent conversations and extract behavioral preferences."""
    try:
        count, compressed = run_learn()
        if count == 0:
            console.print("[dim]No new conversations to evaluate.[/dim]")
        else:
            console.print(f"[green]Evaluated {count} conversation(s).[/green]")
            if compressed:
                console.print("[green]Preferences compressed (exceeded threshold).[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if __import__("os").environ.get("NAVIGATOR_DEBUG"):
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def preferences(
    clear: bool = typer.Option(False, "--clear", help="Clear all preferences"),
):
    """View current behavioral guidelines."""
    if clear:
        if typer.confirm("Clear all preferences?"):
            clear_preferences()
            console.print("[green]Preferences cleared.[/green]")
        return

    prefs = load_preferences()
    if not prefs:
        console.print("[dim]No preferences yet. Run 'navigator chat' and 'navigator learn'.[/dim]")
        return

    console.print(Panel("Behavioral Guidelines", border_style="blue"))
    for i, p in enumerate(prefs, 1):
        guidelines = p.get("behavioral_guidelines", "")
        pairs = p.get("example_pairs", [])
        if guidelines:
            console.print(f"\n[bold]{i}.[/bold] {guidelines}")
        for pair in pairs:
            instead = pair.get("instead_of", "")
            do_this = pair.get("do_this", "")
            if instead and do_this:
                console.print(f"   [dim]Instead of:[/dim] {instead}")
                console.print(f"   [dim]Do this:[/dim] {do_this}")


@app.command()
def completion(
    shell: str = typer.Argument(
        ...,
        help="Shell type: bash, zsh, fish, or pwsh",
    ),
):
    """Print shell completion script for subcommands and options.

    Add to your shell config (e.g. ~/.zshrc):

        eval \"$(navigator completion zsh)\"

    Or for bash:

        eval \"$(navigator completion bash)\"

    Restart your shell or run `source ~/.zshrc` for changes to take effect.
    """
    from typer._completion_shared import get_completion_script

    prog_name = "navigator"
    complete_var = "_{}_COMPLETE".format(prog_name.replace("-", "_").upper())
    script = get_completion_script(prog_name=prog_name, complete_var=complete_var, shell=shell)
    console.print(script)


@app.command()
def config(
    api_key: str = typer.Option(None, "--api-key", help="Set API key (from console.anthropic.com)"),
    token: str = typer.Option(None, "--token", help="Set setup-token (from claude setup-token; may not work for API)"),
    model: str = typer.Option(None, "--model", help="Set model (e.g. claude-sonnet-4-5-20250929)"),
):
    """Set API key, token, or model."""
    if api_key:
        set_api_key(api_key)
        console.print("[green]API key saved.[/green]")
    if token:
        set_token(token)
        console.print("[green]Token saved.[/green]")
    if model:
        set_model(model)
        console.print(f"[green]Model set to {model}.[/green]")

    if not api_key and not token and not model:
        m = get_model()
        has_auth = bool(get_token())
        console.print(f"Model: {m}")
        console.print(f"Auth: {'set' if has_auth else 'not set'}")


if __name__ == "__main__":
    app()
