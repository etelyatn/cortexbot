# CortexBot

Telegram bot that orchestrates [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI sessions for Unreal Engine development using the [Cortex](https://github.com/etelyatn/UnrealCortex) ecosystem.

```
User (Telegram) → CortexBot → Claude Code CLI → cortex-toolkit + cortex-mcp → Unreal Editor
```

## What it does

- **Artifact-driven orchestration:** Brainstorm → Plan → Implement → Review → Test → Finish — each phase produces a concrete artifact that gates the next
- **Freeform `/chat`:** Talk to Claude Code with full MCP access, outside the task pipeline
- **Telegram-native:** One thread per task, commands for control (`/task`, `/status`, `/cancel`, `/continue`, `/auto`, `/test`, `/answer`)
- **Auto mode:** `/auto on` chains phases automatically, pausing only on escalation or budget limits
- **Crash recovery:** Task state persisted to disk, dead subprocess PIDs detected and cleared on restart
- **Token-based budgeting:** Per-task token budgets with real-time tracking from stream events
- **Session rotation:** Detects context growth and bridges to fresh Claude Code sessions

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Unreal Engine project with [UnrealCortex](https://github.com/etelyatn/UnrealCortex) plugin and [cortex-mcp](https://github.com/etelyatn/UnrealCortex/tree/main/MCP) server configured

## Installation

```bash
# Clone the repo
git clone https://github.com/etelyatn/cortexbot.git
cd cortexbot

# Install dependencies
uv sync --all-extras

# Run the init wizard to configure bot directory, token, and projects
uv run cortexbot init
```

The init wizard creates `~/.cortexbot/` with:
- `config.yaml` — bot configuration
- `.env` — Telegram bot token (loaded automatically on startup)
- `tasks/` — persistent task state
- `chats/` — chat session state

## Telegram Setup

<details>
<summary>Create a bot and configure your Telegram group (click to expand)</summary>

### 1. Create a bot with BotFather

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow the prompts to choose a name and username
3. Copy the **bot token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Create a Telegram group

1. Create a new group in Telegram (or use an existing one)
2. **Enable Topics** (optional but recommended): Group Settings → Topics → toggle on. This gives each task its own thread.
3. Add your bot to the group

### 3. Get the group ID

The easiest way to find your group chat ID:

1. Add [@RawDataBot](https://t.me/RawDataBot) to your group temporarily
2. It will reply with a JSON message — look for `"chat": {"id": -100...}`
3. Copy that number (including the `-100` prefix)
4. Remove RawDataBot from the group

### 4. Set bot permissions

In BotFather, send `/mybots` → select your bot → **Bot Settings**:
- **Group Privacy** → Turn **OFF** (so the bot can read commands in groups)
- **Allow Groups** → Turn **ON**

If using Topics, also grant the bot **admin rights** in the group so it can post to any topic.

</details>

## Configuration

After running `cortexbot init`, edit `~/.cortexbot/config.yaml` if needed:

```yaml
telegram:
  bot_token: "${CORTEXBOT_TELEGRAM_TOKEN}"
  group_id: -1001234567890

projects:
  sandbox:
    path: "D:/UnrealProjects/CortexSandbox"
    mcp_config: ".mcp.json"
    default_branch: "main"
    group_id: -1001234567890

defaults:
  token_budget: 500000
  max_cycles: 3
  chat_inactivity_timeout: 7200
```

## Usage

```bash
# Start the bot
uv run cortexbot

# Or with explicit config path
uv run cortexbot /path/to/config.yaml
```

### Task Commands

In Telegram (inside your configured group):

| Command | Description |
|---------|-------------|
| `/task <description>` | Create a new task, start artifact pipeline |
| `/task <desc> --spec path` | Create task with existing spec (skip brainstorm) |
| `/task <desc> --plan path` | Create task with existing plan (skip brainstorm + plan) |
| `/continue` | Execute the next action in the pipeline |
| `/auto on\|off` | Toggle auto mode (chains actions automatically) |
| `/cancel` | Kill running subprocess, pause or cancel task |
| `/answer <text>` | Reply to brainstorm questions |
| `/status` | Show current task state and artifacts |
| `/budget [amount]` | Show or set token budget |
| `/tasks` | List all active tasks |

### Chat Commands

| Command | Description |
|---------|-------------|
| `/chat <message>` | Start or continue a freeform Claude Code session |
| `/chat_end` | End the current chat session |
| `/chat_history` | List active chat sessions |

### Test Commands

| Command | Description |
|---------|-------------|
| `/test` | Run all tests (Unreal + Python) directly |
| `/test Cortex.Data+` | Run specific Unreal test namespace directly |
| `/test python` | Run Python tests only |
| `/test <instructions>` | Run tests via Claude Code (freeform) |

### Project Commands

| Command | Description |
|---------|-------------|
| `/project_add <name> <path>` | Register a project at runtime |
| `/project_validate` | Health check (editor, git, MCP config) |

## Architecture

CortexBot is a thin orchestrator — it manages lifecycle, routes messages, and enforces gates. Claude Code does all reasoning and code generation.

```
bot/           → Telegram commands and application setup
orchestrator/  → Task state machine, action tools, session mutex
claude/        → CLI invocation, stream-json parsing, prompt builder
memory/        → Filesystem task store, session records
chat/          → Freeform chat sessions (separate from task pipeline)
events/        → Event bus and Telegram notifications
services/      → Unreal Engine health checks
cli/           → Init wizard and CLI entry points
config.py      → YAML config with env var interpolation
```

### Task Pipeline

Each task progresses through artifact-producing actions:

```
brainstorm → plan → implement → review → test → finish
                         ↑         │       │
                         └─────────┘       │
                         fix-review    fix-tests
```

- **brainstorm**: Generates a spec document (may ask clarifying questions first)
- **plan**: Produces an implementation plan from the spec
- **implement**: Writes code on a feature branch
- **review**: Self-reviews the implementation, may trigger fix-review cycle
- **test**: Runs tests, may trigger fix-tests cycle
- **finish**: Final cleanup and summary

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run specific test module
uv run pytest tests/test_stream_parser.py -v
```

## License

MIT
