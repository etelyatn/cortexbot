"""On-demand UEConnection wrapper for direct TCP communication with CortexCore."""

import asyncio
import os

from cortex_mcp.tcp_client import UEConnection


async def check_ue_health(project_path: str) -> dict:
    """One-shot health check. Returns {"connected": bool, ...}."""
    def _check():
        os.environ["CORTEX_PROJECT_DIR"] = project_path
        conn = UEConnection()
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
        os.environ["CORTEX_PROJECT_DIR"] = project_path
        conn = UEConnection()
        try:
            conn.connect()
            return conn.send_command(f"{domain}.{command}", params)
        finally:
            conn.disconnect()

    return await asyncio.to_thread(_run)
