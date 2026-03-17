"""cortexbot init — interactive setup wizard."""

import re
import shutil
import subprocess
from pathlib import Path

import yaml


def validate_token_format(token: str) -> bool:
    """Check if string looks like a Telegram bot token."""
    return bool(re.match(r"^\d+:[A-Za-z0-9_-]{30,}$", token))


def check_claude_binary(binary: str = "claude") -> bool:
    """Check if claude CLI is accessible."""
    return shutil.which(binary) is not None


def check_superpowers() -> bool:
    """Check if superpowers plugin is installed in Claude Code."""
    try:
        result = subprocess.run(
            ["claude", "-p", "echo test", "--allowedTools", ""],
            capture_output=True, text=True, timeout=15,
        )
        result = subprocess.run(
            ["claude", "skills", "list"],
            capture_output=True, text=True, timeout=15,
        )
        return "superpowers" in result.stdout.lower()
    except Exception:
        return False


def run_init(bot_dir: Path) -> None:
    """Run the interactive init wizard."""
    print("CortexBot V2 Setup\n")

    # 1. Telegram token
    token = input("Enter your Telegram bot token: ").strip()
    if not validate_token_format(token):
        print("ERROR: Invalid token format. Expected: 123456789:ABCdef...")
        return

    # 2. Claude binary
    if not check_claude_binary("claude"):
        print("ERROR: 'claude' not found in PATH.")
        print("Install Claude Code: https://docs.anthropic.com/en/docs/claude-code")
        return

    # 3. Claude authentication
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"ERROR: claude --version failed: {result.stderr}")
            return
        print(f"Claude CLI: {result.stdout.strip()}")
    except Exception as e:
        print(f"ERROR: Could not run claude: {e}")
        return

    # 4. Check superpowers plugin
    if not check_superpowers():
        print("WARNING: superpowers plugin not detected in Claude Code.")
        print("Install it before using pipeline commands: https://github.com/obra/superpowers")

    # 5. Create directories
    bot_dir.mkdir(parents=True, exist_ok=True)
    (bot_dir / "tasks").mkdir(exist_ok=True)
    (bot_dir / "chats").mkdir(exist_ok=True)
    (bot_dir / "logs").mkdir(exist_ok=True)

    # 6. Write .env
    env_path = bot_dir / ".env"
    env_path.write_text(f"CORTEXBOT_TELEGRAM_TOKEN={token}\n")

    # 7. Write config.yaml
    config = {
        "telegram": {"bot_token": "${CORTEXBOT_TELEGRAM_TOKEN}"},
        "projects": {},
        "defaults": {
            "token_budget": 500000,
            "timeouts": {
                "brainstorm": 900,
                "plan": 900,
                "execute": 1800,
                "review": 900,
                "chat": 600,
                "default": 900,
            },
            "session_rotation": {"execute": 100},
            "max_cycles": 3,
            "chat": {"inactivity_timeout": 7200},
        },
        "logging": {"invocation_logs": True, "retention_days": 30},
        "claude": {"binary": "claude"},
    }
    config_path = bot_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"\nBot ready. Start with `cortexbot run`.")
    print(f"Register projects from Telegram with `/project-add`.")
