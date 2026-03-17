# CortexBot

Telegram bot that orchestrates [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI sessions for Unreal Engine development using the [Cortex](https://github.com/etelyatn/UnrealCortex) ecosystem.

```
User (Telegram) → CortexBot → Claude Code CLI → cortex-toolkit + cortex-mcp → Unreal Editor
```

## What it does

- **Artifact-driven orchestration:** Brainstorm → Plan → Implement → Review → Test → Finish — each phase produces a concrete artifact that gates the next
- **Freeform `/chat`:** Talk to Claude Code with full MCP access, outside the task pipeline
- **Editor lifecycle:** Start, stop, and monitor the Unreal Editor directly from Telegram
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

## Quick Start

```bash
git clone https://github.com/etelyatn/cortexbot.git
cd cortexbot
uv sync --all-extras
uv run cortexbot init     # Interactive setup wizard
uv run cortexbot           # Start the bot
```

## Project Model

CortexBot manages **multiple Unreal Engine projects**. Each project is bound to a **Telegram group chat** — all commands in that group target that project.

### How it works

```
Telegram Group A  ←→  Project "sandbox"   (D:/UnrealProjects/CortexSandbox)
Telegram Group B  ←→  Project "shooter"   (D:/UnrealProjects/ShooterGame)
Telegram Group C  ←→  Project "rpg"       (D:/UnrealProjects/RPGDemo)
```

- **One group = one project.** When you send `/task` in Group A, the bot knows it's for `sandbox`.
- The binding is created when you run `/project_add` — the bot captures the group's chat ID automatically.
- Each group is independent: tasks, chat sessions, and editor commands all scope to that group's project.

### Setting up a new project

1. **Create a Telegram group** for the project (or use an existing one with Topics enabled)
2. **Add the bot** to the group
3. **Register the project:**
   ```
   /project_add myproject D:/UnrealProjects/MyProject
   ```
   The bot validates: `.git` exists, `.mcp.json` exists, `CLAUDE.md` exists (cortex-toolkit installed)
4. **Check health:**
   ```
   /project_validate
   ```
5. **Start the editor if needed:**
   ```
   /editor start
   ```

### Config file

Projects can also be configured manually in `~/.cortexbot/config.yaml`:

```yaml
telegram:
  bot_token: "${CORTEXBOT_TELEGRAM_TOKEN}"

projects:
  sandbox:
    path: "D:/UnrealProjects/CortexSandbox"
    mcp_config: ".mcp.json"
    default_branch: "main"
    group_id: -1001234567890    # Telegram group chat ID
  shooter:
    path: "D:/UnrealProjects/ShooterGame"
    mcp_config: ".mcp.json"
    default_branch: "main"
    group_id: -1009876543210    # Different group

defaults:
  token_budget: 500000
  max_cycles: 3
  chat:
    inactivity_timeout: 7200
```

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

Or just run `/project_add` — the bot captures the group ID automatically.

### 4. Set bot permissions

In BotFather, send `/mybots` → select your bot → **Bot Settings**:
- **Group Privacy** → Turn **OFF** (so the bot can read commands in groups)
- **Allow Groups** → Turn **ON**

If using Topics, also grant the bot **admin rights** in the group so it can post to any topic.

</details>

## Commands

### Editor Management

| Command | Description |
|---------|-------------|
| `/editor` or `/editor status` | Show editor status (running, port, domains) |
| `/editor start` | Start the Unreal Editor and wait for MCP connection |
| `/editor stop` | Gracefully shut down the editor |

The editor auto-starts during task execution (cortex-toolkit's PreToolUse hook handles this). Use `/editor start` for explicit control or to pre-warm before creating tasks.

### Project Management

| Command | Description |
|---------|-------------|
| `/project_add <name> <path>` | Register a project for this group |
| `/project_validate` | Full health check (editor, git, MCP, CLAUDE.md) |
| `/ping` | Check if the bot is alive |

### Task Pipeline

| Command | Description |
|---------|-------------|
| `/task <description>` | Create a new task, start artifact pipeline |
| `/task <desc> --spec path` | Skip brainstorm — use existing spec |
| `/task <desc> --plan path` | Skip brainstorm + plan — use existing plan |
| `/continue` | Execute the next action in the pipeline |
| `/auto on\|off` | Toggle auto mode (chains actions automatically) |
| `/cancel` | Kill running subprocess, pause or cancel task |
| `/answer <text>` | Reply to brainstorm questions |
| `/status` | Show current task state and artifacts |
| `/budget [amount]` | Show or set token budget |
| `/tasks` | List all active tasks |
| `/test` | Run all tests (Unreal + Python) directly |
| `/test Cortex.Data+` | Run specific Unreal test namespace |
| `/test python` | Run Python tests only |

### Freeform Chat

| Command | Description |
|---------|-------------|
| `/chat <message>` | Start or continue a freeform Claude Code session |
| `/chat_end` | End the current chat session |
| `/chat_history` | List active chat sessions |

## Architecture

CortexBot is a thin orchestrator — it manages lifecycle, routes messages, and enforces gates. Claude Code does all reasoning and code generation.

```
bot/           → Telegram commands and application setup
orchestrator/  → Task state machine, action tools, session mutex
claude/        → CLI invocation, stream-json parsing, prompt builder
memory/        → Filesystem task store, session records
chat/          → Freeform chat sessions (separate from task pipeline)
events/        → Event bus and Telegram notifications
services/      → Unreal Editor lifecycle (status, start, stop, health)
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
uv run pytest tests/ -v            # Run all tests
uv run pytest tests/test_*.py -v   # Run specific module
```

## License

MIT
