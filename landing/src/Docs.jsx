import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './Docs.css'

// README content - kept in sync with navigator/README.md
const DOCS_CONTENT = `# Navigator

A CLI that lets you chat with Claude through your terminal. Behind the scenes, it watches your conversations and learns what you like and don't like, so Claude gets better at talking to *you* over time.

## Install

\`\`\`bash
curl -fsSL https://getnavigator.app/install.sh | sh
\`\`\`

Or from source: \`cd navigator && bash install.sh\`, or \`pip install -e .\`

## Setup

Configure your API key (required for programmatic access):

\`\`\`bash
# Get an API key from console.anthropic.com, then:
navigator config --api-key sk-ant-...
\`\`\`

**Note:** Setup-tokens from \`claude setup-token\` (OAuth) do not work for Navigator—the API returns "OAuth authentication is currently not supported" for programmatic access. Use an API key from the Anthropic Console.

### Local models (Ollama)

Use [Ollama](https://ollama.com) to run local open-weights models with the same tools (Read, Edit, Bash, etc.):

\`\`\`bash
# Install Ollama from ollama.com, then:
navigator model pull llama3.2
navigator model switch ollama:llama3.2
navigator chat
\`\`\`

No API key needed for local models. Tool-capable models (Llama 3.2+, Qwen 2.5+, etc.) work best.

## Commands

| Command | Description |
|---------|-------------|
| \`navigator chat\` | Start a conversation with Claude (supports tools: Read, Edit, Bash, etc.) |
| \`navigator learn\` | Process recent conversations and extract behavioral preferences |
| \`navigator evaluate <file>\` | Evaluate an external \`conversations.json\` file (e.g. Claude desktop export) |
| \`navigator fine-tune\` | Export fine-tuning dataset (JSONL) for open-weights models (Unsloth, Axolotl, etc.) |
| \`navigator persona load <file>\` | Load a JSON/JSONL file as system prompt (e.g. evaluated output) |
| \`navigator persona clear\` | Clear the loaded persona |
| \`navigator preferences\` | View current guidelines. Use \`--clear\` to reset |
| \`navigator model list\` | List Anthropic models (use \`--ollama\` for local) |
| \`navigator model pull <model>\` | Download an Ollama model |
| \`navigator model switch [model]\` | Switch model (e.g. \`ollama:llama3.2\` for local) |
| \`navigator config\` | Set API key or model |
| \`navigator completion\` | Print shell completion script (see below) |

## Shell completion

Enable tab completion for subcommands and options:

\`\`\`bash
# Zsh
eval "$(navigator completion zsh)"

# Bash
eval "$(navigator completion bash)"
\`\`\`

Add the line to your shell config (\`~/.zshrc\` or \`~/.bashrc\`), then restart your shell or run \`source ~/.zshrc\`.

## How it works

1. **Chat** — You talk to Claude. All messages are logged to \`~/.navigator/conversations.jsonl\`.
2. **Learn** — Run \`navigator learn\` (or schedule via cron). An evaluator analyzes your conversations, finds moments of frustration or mismatch, and extracts behavioral guidelines.
3. **Preferences** — Guidelines are stored in \`~/.navigator/preferences.jsonl\` and injected into Claude's system prompt on the next chat.

Over time, Claude becomes personalized to you.

## Data

- \`~/.navigator/config.json\` — Token, model, settings
- \`~/.navigator/conversations.jsonl\` — Raw conversation logs
- \`~/.navigator/preferences.jsonl\` — Extracted behavioral guidelines

Set \`NAVIGATOR_HOME\` to use a different directory (e.g. for testing).

**Debug:** Set \`NAVIGATOR_DEBUG=1\` to log API responses and CLI stderr (e.g. when debugging "Invalid API key").

## Evaluating external conversation files

To run the evaluator on a \`conversations.json\` file (e.g. exported from Claude desktop):

\`\`\`bash
navigator evaluate conversations.json
\`\`\`

Results are written to \`conversations.evaluated.jsonl\`. Use \`--output path.jsonl\` to customize, or \`--limit N\` to process only the first N eligible conversations (useful for testing).

To use the evaluated output as your chat persona:

\`\`\`bash
navigator persona load conversations.evaluated.jsonl
navigator chat
\`\`\`

Persona files can be JSONL (evaluated format), JSON with a \`persona\` or \`system_prompt\` key, or plain text.

## Fine-tuning

Export a fine-tuning dataset for **open-weights models** (Llama, Mistral, Qwen, etc.). Cloud APIs like Claude don't support fine-tuning, so use Unsloth, Axolotl, or LLaMA-Factory with the exported data:

\`\`\`bash
navigator fine-tune -o finetune.jsonl
\`\`\`

This builds prompt-completion pairs from behavioral corrections (issues with \`alternative_response\`).

**Output formats** (\`--format\` / \`-f\`):
- \`messages\` (default) — \`{"messages": [...]}\` for LLaMA-Factory, Axolotl, Unsloth
- \`sharegpt\` — \`{"conversations": [{"from": "human", "value": "..."}, ...]}\`
- \`alpaca\` — \`{"instruction": "...", "input": "", "output": "..."}\`

**Options:**
- \`--input\` / \`-i\` — Preferences or evaluated JSONL file (default: \`~/.navigator/preferences.jsonl\`)
- \`--conversations\` / \`-c\` — Conversations file for matching (default: \`~/.navigator/conversations.jsonl\`)
- \`--output\` / \`-o\` — Output JSONL file (default: \`finetune.jsonl\`)
- \`--json\` — Conversations file is a JSON array (e.g. Claude desktop export) rather than JSONL

For evaluated output from an external file:

\`\`\`bash
navigator fine-tune -i conversations.evaluated.jsonl -c conversations.json --json -o finetune.jsonl
\`\`\`
`

export default function Docs() {
  return (
    <div className="docs">
      <div className="docs-content">
        <Link to="/" className="docs-back">← Back to Navigator</Link>
        <article className="docs-article">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a({ href, children }) {
                return (
                  <a href={href} target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                )
              },
            }}
          >
            {DOCS_CONTENT}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  )
}
