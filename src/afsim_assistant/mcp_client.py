from __future__ import annotations

import json
import os
import subprocess
import sys

from .config import Settings


class McpError(RuntimeError):
    pass


class McpStdioClient:
    """Small synchronous JSON-RPC client for the local AFSIM MCP server."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.process: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self) -> "McpStdioClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def start(self) -> None:
        if self.process is not None:
            return
        entry = self.settings.mcp_root / "transport" / "stdio.py"
        if not entry.is_file():
            raise McpError(f"AFSIM MCP entry not found: {entry}")
        self.settings.mcp_state_dir.mkdir(parents=True, exist_ok=True)
        self.settings.mcp_config_dir.mkdir(parents=True, exist_ok=True)
        self.settings.staging_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update(
            {
                "AFSIM_ROOT": str(self.settings.afsim_bin.parent),
                "AFSIM_DEMOS_DIR": str(self.settings.demos_root),
                "AFSIM_BIN": str(self.settings.afsim_bin),
                "AFSIM_PROJECT_ROOT": str(self.settings.staging_dir),
                "AFSIM_MCP_STATE_DIR": str(self.settings.mcp_state_dir),
                "AFSIM_MCP_CONFIG_DIR": str(self.settings.mcp_config_dir),
            }
        )
        self.process = subprocess.Popen(
            [sys.executable, str(entry)],
            cwd=str(self.settings.mcp_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        self.request(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}},
        )

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            if process.stdin:
                process.stdin.close()
            process.wait(timeout=3)
        except Exception:
            process.terminate()
            try:
                process.wait(timeout=2)
            except Exception:
                process.kill()

    def request(self, method: str, params: dict | None = None) -> dict:
        process = self.process
        if process is None or process.stdin is None or process.stdout is None:
            raise McpError("AFSIM MCP client is not started")
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()

        while True:
            line = process.stdout.readline()
            if line == "":
                raise McpError(f"AFSIM MCP server exited while waiting for {method}")
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if "error" in response:
                error = response["error"]
                raise McpError(f"AFSIM MCP {method} failed: {error.get('message')}: {error.get('data')}")
            return response.get("result") or {}

    def list_tools(self) -> list[dict]:
        return self.request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        result = self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        content = result.get("content") or []
        for item in content:
            if item.get("type") == "text":
                try:
                    payload = json.loads(item.get("text") or "{}")
                except json.JSONDecodeError as exc:
                    raise McpError(f"AFSIM MCP tool {name} returned invalid JSON") from exc
                if result.get("isError") or payload.get("error"):
                    raise McpError(f"AFSIM MCP tool {name} failed: {payload.get('error')}")
                return payload
        raise McpError(f"AFSIM MCP tool {name} returned no text payload")

