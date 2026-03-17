"""On-demand UEConnection wrapper for direct TCP communication with CortexCore."""

import asyncio
import glob
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from cortex_mcp.tcp_client import UEConnection

logger = logging.getLogger(__name__)

# Serialize env var mutation — UEConnection reads CORTEX_PROJECT_DIR at construction time
_ue_lock = threading.Lock()


def _make_connection(project_path: str) -> UEConnection:
    """Create a UEConnection with thread-safe env var handling."""
    with _ue_lock:
        old = os.environ.get("CORTEX_PROJECT_DIR")
        os.environ["CORTEX_PROJECT_DIR"] = project_path
        conn = UEConnection()
        if old is not None:
            os.environ["CORTEX_PROJECT_DIR"] = old
        else:
            os.environ.pop("CORTEX_PROJECT_DIR", None)
    return conn


async def check_ue_health(project_path: str) -> dict:
    """One-shot health check. Returns {"connected": bool, ...}."""
    def _check():
        conn = _make_connection(project_path)
        try:
            conn.connect()
            result = conn.send_command("get_status", {})
            return {"connected": True, "status": result}
        except Exception as e:
            return {"connected": False, "error": str(e)}
        finally:
            conn.disconnect()

    return await asyncio.to_thread(_check)


async def run_ue_command(project_path: str, domain: str, command: str, params: dict) -> dict:
    """One-shot command execution for direct UE commands."""
    def _run():
        conn = _make_connection(project_path)
        try:
            conn.connect()
            return conn.send_command(f"{domain}.{command}", params)
        finally:
            conn.disconnect()

    return await asyncio.to_thread(_run)


def _find_port_file(project_path: str) -> Path | None:
    """Find the most recent CortexPort-*.txt file."""
    saved = Path(project_path) / "Saved"
    files = sorted(saved.glob("CortexPort-*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_port(port_file: Path) -> int | None:
    """Read port number from port file (supports plain number and JSON formats)."""
    try:
        raw = port_file.read_text().strip()
        if raw.isdigit():
            return int(raw)
        if raw.startswith("{"):
            data = json.loads(raw)
            return int(data["port"])
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        pass
    return None


def _tcp_probe(port: int) -> bool:
    """Quick TCP probe to check if a port is listening."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


async def check_editor_status(project_path: str) -> dict:
    """Detailed editor status check. Returns status dict with actionable info.

    Result keys:
        running (bool): Editor process is alive and TCP responds
        port (int|None): Port number if found
        pid (int|None): Editor PID if found
        domains (list): Registered domains if connected
        can_start (bool): Whether we have enough info to start the editor
        engine_path (str|None): UE engine path if available
        uproject (str|None): .uproject file path if found
    """
    def _check():
        result = {
            "running": False,
            "port": None,
            "pid": None,
            "domains": [],
            "can_start": False,
            "engine_path": None,
            "uproject": None,
        }

        # Find .uproject
        uproject_files = glob.glob(os.path.join(project_path, "*.uproject"))
        if uproject_files:
            result["uproject"] = uproject_files[0]

        # Check engine path
        engine_path = os.environ.get("UE_56_PATH", "")
        if engine_path and os.path.isdir(engine_path):
            result["engine_path"] = engine_path

        result["can_start"] = bool(result["uproject"] and result["engine_path"])

        # Check port file
        port_file = _find_port_file(project_path)
        if not port_file:
            return result

        port = _read_port(port_file)
        if not port:
            return result
        result["port"] = port

        # Extract PID from filename
        name = port_file.stem  # CortexPort-12345
        parts = name.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            result["pid"] = int(parts[1])

        # TCP probe
        if not _tcp_probe(port):
            return result

        # Full MCP check
        conn = _make_connection(project_path)
        try:
            conn.connect()
            status = conn.send_command("get_status", {})
            result["running"] = True
            data = status.get("data", {})
            domains = data.get("subsystems", data.get("domains", {}))
            if isinstance(domains, dict):
                result["domains"] = list(domains.keys())
            elif isinstance(domains, list):
                result["domains"] = domains
        except Exception:
            pass
        finally:
            conn.disconnect()

        return result

    return await asyncio.to_thread(_check)


async def start_editor(project_path: str, timeout: int = 120) -> dict:
    """Start the Unreal Editor and wait for CortexCore TCP to become ready.

    Returns:
        Dict with keys: started (bool), port, pid, domains, error, elapsed_seconds
    """
    def _start():
        engine_path = os.environ.get("UE_56_PATH", "")
        if not engine_path or not os.path.isdir(engine_path):
            return {"started": False, "error": "UE_56_PATH not set or invalid"}

        uproject_files = glob.glob(os.path.join(project_path, "*.uproject"))
        if not uproject_files:
            return {"started": False, "error": f"No .uproject found in {project_path}"}

        uproject = uproject_files[0]
        editor_exe = os.path.join(engine_path, "Engine", "Binaries", "Win64", "UnrealEditor.exe")
        if not os.path.isfile(editor_exe):
            return {"started": False, "error": f"Editor not found: {editor_exe}"}

        # Clean stale port files
        saved = Path(project_path) / "Saved"
        for pf in saved.glob("CortexPort-*.txt"):
            try:
                # Check if PID is still alive
                parts = pf.stem.split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    pid = int(parts[1])
                    import psutil
                    if psutil.pid_exists(pid):
                        continue  # Still alive, keep it
                pf.unlink()
            except (ValueError, OSError):
                pass

        # Launch
        start_time = time.monotonic()
        logger.info("Starting editor: %s %s", editor_exe, uproject)
        subprocess.Popen(
            [editor_exe, uproject, "-nosplash", "-nopause", "-AutoDeclinePackageRecovery"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Poll for port file + TCP
        while (time.monotonic() - start_time) < timeout:
            time.sleep(5)
            port_file = _find_port_file(project_path)
            if not port_file:
                continue
            port = _read_port(port_file)
            if not port:
                continue
            if not _tcp_probe(port):
                continue

            # Verify MCP responds
            conn = _make_connection(project_path)
            try:
                conn.connect()
                status = conn.send_command("get_status", {})
                data = status.get("data", {})
                domains = data.get("subsystems", data.get("domains", {}))
                domain_list = list(domains.keys()) if isinstance(domains, dict) else domains

                # Extract PID
                pid = None
                parts = port_file.stem.split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    pid = int(parts[1])

                elapsed = round(time.monotonic() - start_time, 1)
                return {
                    "started": True,
                    "port": port,
                    "pid": pid,
                    "domains": domain_list,
                    "elapsed_seconds": elapsed,
                }
            except Exception:
                continue
            finally:
                conn.disconnect()

        elapsed = round(time.monotonic() - start_time, 1)
        return {
            "started": False,
            "error": f"Editor did not become ready within {timeout}s",
            "elapsed_seconds": elapsed,
        }

    return await asyncio.to_thread(_start)
