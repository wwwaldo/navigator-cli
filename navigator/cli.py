"""Navigator CLI — chat with Claude and learn your preferences."""

import asyncio
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .client import build_chat_options, chat_turn
from .config import (
    CONVERSATIONS_PATH,
    PREFERENCES_PATH,
    get_model,
    get_ollama_model_name,
    get_persona_file,
    get_persona_summary,
    get_token,
    is_ollama_model,
    set_api_key,
    set_model,
    set_token,
    set_persona_file,
    set_persona_summary,
)
from .evaluator import run_learn
from .evaluate_file import run_evaluate_file
from .fine_tune import build_dataset
from .persona import summarize_persona
from .ollama_client import _build_system_prompt, ollama_chat_turn
from .store import append_conversation, clear_preferences, load_preferences, load_persona_from_file

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
    """Start a conversation with Claude or a local Ollama model."""
    use_ollama = is_ollama_model()
    if not use_ollama:
        token = get_token()
        if not token:
            console.print(
                "[red]No API key configured.[/red]\n"
                "Get one at [bold]console.anthropic.com[/bold], then: [bold]navigator config --api-key sk-ant-...[/bold]"
            )
            raise typer.Exit(1)
        if token.strip().startswith("sk-ant-oat01-"):
            console.print(
                "[yellow]Warning:[/yellow] Setup-token (OAuth) is configured, but the API returns "
                "'OAuth authentication is currently not supported' for programmatic access.\n"
                "Use an API key instead: [bold]navigator config --api-key sk-ant-...[/bold] "
                "(from console.anthropic.com)"
            )
            raise typer.Exit(1)

    working_dir = (cwd if cwd and cwd.exists() else None) or Path.cwd()
    conversation_id = str(uuid.uuid4())
    all_messages: list[dict] = []
    conversation_saved = [False]

    async def run_chat():
        if use_ollama:
            await _run_chat_ollama(working_dir, all_messages, conversation_saved)
        else:
            await _run_chat_anthropic(working_dir, all_messages, conversation_saved)

    async def _run_chat_ollama(cwd: Path, msg_acc: list, saved: list):
        from ollama import AsyncClient

        client = AsyncClient()
        model = get_ollama_model_name()
        if not model:
            console.print("[red]Invalid Ollama model. Use: navigator model switch ollama:llama3.2[/red]")
            raise typer.Exit(1)
        system_prompt = _build_system_prompt(cwd)

        console.print(
            Panel(
                f"[dim]Type your message and press Enter. Type 'exit' or press Ctrl+C to end. (Ollama: {model})[/dim]",
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
                if msg_acc:
                    with console.status("Saving conversation...", spinner="dots"):
                        append_conversation(conversation_id, msg_acc)
                    console.print(f"\n[dim]Conversation saved ({len(msg_acc)} messages).[/dim]")
                    saved[0] = True
                break
            assistant_label_printed = [False]
            claude_style = "bold #d4a574"

            def stream_chunk(text: str) -> None:
                if not assistant_label_printed[0]:
                    console.print(f"[{claude_style}]Assistant[/{claude_style}]: ", end="")
                    assistant_label_printed[0] = True
                console.print(text, end="")

            def stream_tool(name: str, inp: dict, result: str) -> None:
                if not assistant_label_printed[0]:
                    console.print(f"[{claude_style}]Assistant[/{claude_style}]:")
                    assistant_label_printed[0] = True
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

            messages, _ = await ollama_chat_turn(
                client, model,
                [{"role": "user", "content": user_input}],
                cwd,
                system_prompt=system_prompt,
                on_chunk=stream_chunk,
                on_tool=stream_tool,
            )
            msg_acc.extend(messages)
            console.print()

    async def _run_chat_anthropic(cwd: Path, msg_acc: list, saved: list):
        from claude_agent_sdk import ClaudeSDKClient

        options = build_chat_options(cwd=cwd)
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
                    if msg_acc:
                        with console.status("Saving conversation...", spinner="dots"):
                            append_conversation(conversation_id, msg_acc)
                        console.print(f"\n[dim]Conversation saved ({len(msg_acc)} messages).[/dim]")
                        saved[0] = True
                    break
                assistant_label_printed = [False]
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
                msg_acc.extend(messages)
                console.print()

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


persona_app = typer.Typer(help="Load a persona from a JSON/JSONL file into the system prompt.")


@persona_app.command("load")
def persona_load(
    file: Path = typer.Argument(
        ...,
        help="Path to JSON or JSONL file (evaluated output, or JSON with persona/system_prompt key)",
        exists=True,
    ),
):
    """Load a persona file. Its content will be injected into the system prompt when chatting."""
    content = load_persona_from_file(file)
    set_persona_file(file)

    with console.status("Summarizing persona..."):
        summary = summarize_persona(content)
    if summary:
        set_persona_summary(summary)
        console.print(f"[green]Persona loaded from {file}[/green]")
    else:
        set_persona_summary(None)
        console.print(f"[green]Persona loaded from {file}[/green]")
        console.print("[dim]Could not generate summary (API key required).[/dim]")
    console.print("[dim]Use 'navigator persona clear' to remove.[/dim]")


@persona_app.command("clear")
def persona_clear():
    """Clear the loaded persona."""
    set_persona_file(None)
    console.print("[green]Persona cleared.[/green]")


@persona_app.command("show")
def persona_show():
    """Show the currently loaded persona file and its summary."""
    path = get_persona_file()
    if not path:
        console.print("[dim]No persona loaded.[/dim]")
        return
    console.print(f"Persona: [bold]{path}[/bold]")
    summary = get_persona_summary()
    if summary:
        console.print()
        console.print(Panel(summary, title="Summary", border_style="dim"))


app.add_typer(persona_app, name="persona")


model_app = typer.Typer(help="Model selection and switching.")


@model_app.command("list")
def model_list(
    ollama: bool = typer.Option(
        False,
        "--ollama",
        "-o",
        help="List local Ollama models instead of Anthropic models",
    ),
):
    """List available models (Anthropic or Ollama)."""
    if ollama:
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            current = get_ollama_model_name()
            if result.returncode != 0:
                console.print("[red]Ollama not running or not installed.[/red]")
                raise typer.Exit(1)
            lines = (result.stdout or "").strip().split("\n")[1:]  # skip header
            count = sum(1 for line in lines if line.strip())
            console.print(Panel(f"Ollama Models ({count})", border_style="blue"))
            for line in lines:
                parts = line.split()
                if parts:
                    tag = parts[0]
                    is_current = current and (tag == current or tag.startswith(current + ":"))
                    marker = " ← current" if is_current else ""
                    console.print(f"  [bold]{tag}[/bold]{marker}")
        except FileNotFoundError:
            console.print("[red]Ollama not found. Install from ollama.com[/red]")
            raise typer.Exit(1)
        except subprocess.TimeoutExpired:
            console.print("[red]Ollama timed out.[/red]")
            raise typer.Exit(1)
        return

    token = get_token()
    if not token:
        console.print(
            "[yellow]No API key configured.[/yellow] Run [bold]navigator config --api-key sk-ant-...[/bold] to fetch live list.\n"
            "[dim]Common models: claude-sonnet-4-5-20250929, claude-opus-4-6, claude-haiku-4-5-20251001[/dim]"
        )
        return

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=token)
        current = get_model()
        page = client.models.list(limit=50)
        models = getattr(page, "data", None) or list(page)
        if not models:
            console.print("[dim]No models returned.[/dim]")
            return
        console.print(Panel("Available Models", border_style="blue"))
        for m in models:
            mid = getattr(m, "id", str(m))
            name = getattr(m, "display_name", "") or mid
            marker = " ← current" if mid == current else ""
            console.print(f"  [bold]{mid}[/bold]{marker}")
            if name != mid:
                console.print(f"    [dim]{name}[/dim]")
    except Exception as e:
        console.print(f"[red]Error listing models: {e}[/red]")
        console.print("[dim]Common models: claude-sonnet-4-5-20250929, claude-opus-4-6, claude-haiku-4-5-20251001[/dim]")


@model_app.command("pull")
def model_pull(
    model: str = typer.Argument(
        ...,
        help="Ollama model to download (e.g. llama3.2, qwen2.5:7b)",
    ),
):
    """Download an Ollama model (runs ollama pull)."""
    try:
        subprocess.run(["ollama", "pull", model], check=True)
        console.print(f"[green]Pulled {model}. Switch with: navigator model switch ollama:{model}[/green]")
    except FileNotFoundError:
        console.print(
            "[red]Ollama not found.[/red]\n"
            "Install from [bold]ollama.com[/bold], then run: [bold]navigator model pull " + model + "[/bold]"
        )
        raise typer.Exit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]ollama pull failed: {e}[/red]")
        raise typer.Exit(1)


@model_app.command("switch")
def model_switch(
    model: str | None = typer.Argument(
        None,
        help="Model to switch to (e.g. claude-sonnet-4-5-20250929)",
    ),
):
    """Switch the active model for chat and learn."""
    if model:
        set_model(model)
        console.print(f"[green]Switched to {model}[/green]")
    else:
        current = get_model()
        console.print(f"Current model: [bold]{current}[/bold]")
        console.print(
            "[dim]To switch: navigator model switch <model>[/dim]\n"
            "[dim]Cloud: claude-sonnet-4-5-20250929[/dim]\n"
            "[dim]Local: ollama:llama3.2, ollama:qwen2.5:7b[/dim]"
        )


app.add_typer(model_app, name="model")


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
def evaluate(
    input_file: Path = typer.Argument(
        ...,
        help="Path to conversations.json (JSON array of conversations with chat_messages)",
        exists=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSONL file (default: input.evaluated.jsonl)",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Max number of conversations to evaluate (for testing)",
    ),
):
    """Evaluate an external conversations.json file and extract behavioral preferences."""
    try:
        evaluated, with_issues = run_evaluate_file(
            input_path=input_file,
            output_path=output,
            limit=limit,
        )
        out_path = output or input_file.with_suffix(".evaluated.jsonl")
        console.print(f"[green]Evaluated {evaluated} conversation(s).[/green]")
        console.print(f"[green]{with_issues} had extractable preferences → {out_path}[/green]")
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
def fine_tune(
    input_file: Path | None = typer.Option(
        None,
        "--input",
        "-i",
        help="Preferences/evaluated JSONL file (default: ~/.navigator/preferences.jsonl)",
    ),
    conversations: Path | None = typer.Option(
        None,
        "--conversations",
        "-c",
        help="Conversations file for matching (default: ~/.navigator/conversations.jsonl). Use with evaluated output from external JSON.",
    ),
    output: Path = typer.Option(
        Path("finetune.jsonl"),
        "--output",
        "-o",
        help="Output JSONL file",
    ),
    json_conversations: bool = typer.Option(
        False,
        "--json",
        help="Conversations file is JSON array (e.g. Claude desktop export) not JSONL",
    ),
    output_format: str = typer.Option(
        "messages",
        "--format",
        "-f",
        help="Output format: messages (LLaMA-Factory/Axolotl/Unsloth), sharegpt, or alpaca",
    ),
):
    """Export a fine-tuning dataset for open-weights models.

    Builds prompt-completion pairs from behavioral corrections (issues with
    alternative_response). Use with Unsloth, Axolotl, LLaMA-Factory, etc.
    """
    try:
        prefs_path = input_file or PREFERENCES_PATH
        conv_path = conversations or CONVERSATIONS_PATH
        count = build_dataset(
            preferences_path=prefs_path,
            conversations_path=conv_path,
            output_path=output,
            use_json_conversations=json_conversations,
            output_format=output_format,
        )
        if count == 0:
            console.print(
                "[dim]No training examples found.[/dim]\n"
                "Run [bold]navigator learn[/bold] first, or use [bold]--input[/bold] with an evaluated JSONL file."
            )
        else:
            console.print(f"[green]Wrote {count} example(s) to {output}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if __import__("os").environ.get("NAVIGATOR_DEBUG"):
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def teach():
    """Explicitly teach behavioral preferences (stub)."""
    console.print("[dim]Navigator Teach — coming soon.[/dim]")


@app.command()
def parrot():
    """Echo/repeat mode for voice learning (stub)."""
    console.print("[dim]Navigator Parrot — coming soon.[/dim]")


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
        persona = get_persona_file()
        console.print(f"Model: {m}")
        console.print(f"Auth: {'set' if has_auth else 'not set'}")
        console.print(f"Persona: {persona or 'none'}")


if __name__ == "__main__":
    app()
