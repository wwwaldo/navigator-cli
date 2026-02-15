# Navigator

A CLI that lets you chat with Claude through your terminal. Behind the scenes, it watches your conversations and learns what you like and don't like, so Claude gets better at talking to *you* over time.

## Install

```bash
cd navigator
pip install -e .
```

## Setup

Configure your API key (required for programmatic access):

```bash
# Get an API key from console.anthropic.com, then:
navigator config --api-key sk-ant-...
```

**Note:** Setup-tokens from `claude setup-token` (OAuth) do not work for Navigator—the API returns "OAuth authentication is currently not supported" for programmatic access. Use an API key from the Anthropic Console.

## Commands

| Command | Description |
|---------|-------------|
| `navigator chat` | Start a conversation with Claude (supports tools: Read, Edit, Bash, etc.) |
| `navigator learn` | Process recent conversations and extract behavioral preferences |
| `navigator evaluate <file>` | Evaluate an external `conversations.json` file (e.g. Claude desktop export) |
| `navigator persona load <file>` | Load a JSON/JSONL file as system prompt (e.g. evaluated output) |
| `navigator persona clear` | Clear the loaded persona |
| `navigator preferences` | View current guidelines. Use `--clear` to reset |
| `navigator config` | Set API key or model |
| `navigator completion` | Print shell completion script (see below) |

## Shell completion

Enable tab completion for subcommands and options:

```bash
# Zsh
eval "$(navigator completion zsh)"

# Bash
eval "$(navigator completion bash)"
```

Add the line to your shell config (`~/.zshrc` or `~/.bashrc`), then restart your shell or run `source ~/.zshrc`.

## How it works

1. **Chat** — You talk to Claude. All messages are logged to `~/.navigator/conversations.jsonl`.
2. **Learn** — Run `navigator learn` (or schedule via cron). An evaluator analyzes your conversations, finds moments of frustration or mismatch, and extracts behavioral guidelines.
3. **Preferences** — Guidelines are stored in `~/.navigator/preferences.jsonl` and injected into Claude's system prompt on the next chat.

Over time, Claude becomes personalized to you.

## Data

- `~/.navigator/config.json` — Token, model, settings
- `~/.navigator/conversations.jsonl` — Raw conversation logs
- `~/.navigator/preferences.jsonl` — Extracted behavioral guidelines

Set `NAVIGATOR_HOME` to use a different directory (e.g. for testing).

**Debug:** Set `NAVIGATOR_DEBUG=1` to log API responses and CLI stderr (e.g. when debugging "Invalid API key").

## Evaluating external conversation files

To run the evaluator on a `conversations.json` file (e.g. exported from Claude desktop):

```bash
navigator evaluate conversations.json
```

Results are written to `conversations.evaluated.jsonl`. Use `--output path.jsonl` to customize, or `--limit N` to process only the first N eligible conversations (useful for testing).

To use the evaluated output as your chat persona:

```bash
navigator persona load conversations.evaluated.jsonl
navigator chat
```

Persona files can be JSONL (evaluated format), JSON with a `persona` or `system_prompt` key, or plain text.
