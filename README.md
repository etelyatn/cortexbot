# CortexBot

Telegram bot that orchestrates [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI sessions for Unreal Engine development using the [Cortex](https://github.com/etelyatn/UnrealCortex) ecosystem.

```
User (Telegram) → CortexBot → Claude Code CLI → cortex-toolkit + MCP → Unreal Editor
```

## What it does

- **5-phase guided workflow:** Design → Plan → Implement → Test → Merge
- **Telegram-native:** One thread per task, commands for control (`/task`, `/status`, `/cancel`, `/retry`, `/skip`, `/continue`)
- **Autonomy modes:** Supervised (user approves each phase) or Autonomous (auto-advances with escalation)
- **Crash recovery:** Task state persisted to disk, interrupted tasks detected on restart
- **Budget tracking:** Per-task and per-phase cost limits via `--max-budget-usd`
- **Session rotation:** Detects context growth and bridges to fresh sessions

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Unreal Engine project with [UnrealCortex](https://github.com/etelyatn/UnrealCortex) plugin (for MCP tools)

## Installation

```bash
# Clone the repo
git clone https://github.com/etelyatn/cortexbot.git
cd cortexbot

# Install dependencies
uv sync --all-extras

# Verify installation
uv run cortexbot --help
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

### 4. Set bot permissions

In BotFather, send `/mybots` → select your bot → **Bot Settings**:
- **Group Privacy** → Turn **OFF** (so the bot can read commands in groups)
- **Allow Groups** → Turn **ON**

If using Topics, also grant the bot **admin rights** in the group so it can post to any topic.

</details>

## Configuration

```bash
# Copy example config
mkdir -p ~/.cortexbot
cp config.example.yaml ~/.cortexbot/config.yaml
```

Edit `~/.cortexbot/config.yaml`:

```yaml
telegram:
  bot_token: "${CORTEXBOT_TELEGRAM_TOKEN}"  # set this env var
  group_id: -1001234567890                   # your group ID from step 3 above

projects:
  sandbox:
    path: "D:/UnrealProjects/CortexSandbox"
    mcp_config: ".mcp.json"
    default_branch: "main"

defaults:
  autonomy: "supervised"
  budget_usd: 10.00
```

Set the environment variable:

```bash
export CORTEXBOT_TELEGRAM_TOKEN="your-bot-token-here"
```

## Usage

```bash
# Start the bot
uv run cortexbot

# Or with explicit config path
uv run cortexbot /path/to/config.yaml
```

In Telegram (inside your configured group):

| Command | Description |
|---------|-------------|
| `/task <title>` | Create a new task and start Design phase |
| `/status` | Show current task state |
| `/continue` | Approve phase result, advance to next |
| `/cancel` | Kill running phase |
| `/retry` | Re-run current phase |
| `/skip [phase]` | Skip to a specific phase |
| `/tasks` | List all active tasks |
| `/budget [amount]` | Show or add budget |

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run specific test module
uv run pytest tests/test_stream_parser.py -v
```

## Architecture

CortexBot is a thin orchestrator — it manages lifecycle, routes messages, and enforces gates. Claude Code does all reasoning and code generation.

```
bot/           → Telegram commands and message handling
orchestrator/  → Task state, phase gates, session mutex, autonomy
claude/        → CLI invocation, stream-json parsing, prompt templates
memory/        → Filesystem store, session rotation, artifacts
health/        → Preflight checks (editor alive, git state)
events/        → Event bus and Telegram notifications
```

## License

MIT
