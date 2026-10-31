from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    app_root: Path
    projectskill_root: Path
    demos_root: Path
    mcp_root: Path
    afsim_bin: Path
    state_dir: Path
    demo_max_bytes: int = 128 * 1024

    @classmethod
    def discover(cls) -> "Settings":
        app_root = Path(__file__).resolve().parents[2]
        workspace_root = app_root.parent
        afsim_root = workspace_root / "afsim2.9en-src" / "afsim2.9en"
        return cls(
            workspace_root=_env_path("AFSIM_ASSISTANT_WORKSPACE", workspace_root),
            app_root=app_root,
            projectskill_root=_env_path(
                "AFSIM_PROJECTSKILL_DIR",
                workspace_root / "afsim-projectskill" / "afsim-projectskill",
            ),
            demos_root=_env_path("AFSIM_DEMOS_DIR", afsim_root / "demos"),
            mcp_root=_env_path("AFSIM_MCP_DIR", workspace_root / "AFSIM_MCP"),
            afsim_bin=_env_path("AFSIM_BIN", afsim_root / "bin"),
            state_dir=_env_path("AFSIM_ASSISTANT_STATE_DIR", app_root / "state"),
            demo_max_bytes=int(os.environ.get("AFSIM_DEMO_MAX_BYTES", 128 * 1024)),
        )

    @property
    def catalog_path(self) -> Path:
        return self.state_dir / "catalog.json"

    @property
    def index_path(self) -> Path:
        return self.state_dir / "knowledge.db"

    @property
    def mcp_state_dir(self) -> Path:
        return self.state_dir / "mcp"

    @property
    def mcp_config_dir(self) -> Path:
        return self.state_dir / "mcp_config"

    @property
    def staging_dir(self) -> Path:
        return self.app_root / "workspace" / "staging"

    def diagnostics(self) -> dict:
        mission = self.afsim_bin / "mission.exe"
        return {
            "workspace_root": {"path": str(self.workspace_root), "exists": self.workspace_root.is_dir()},
            "projectskill_root": {"path": str(self.projectskill_root), "exists": self.projectskill_root.is_dir()},
            "demos_root": {"path": str(self.demos_root), "exists": self.demos_root.is_dir()},
            "mcp_root": {"path": str(self.mcp_root), "exists": self.mcp_root.is_dir()},
            "afsim_bin": {"path": str(self.afsim_bin), "exists": self.afsim_bin.is_dir()},
            "mission": {"path": str(mission), "exists": mission.is_file()},
            "state_dir": {"path": str(self.state_dir), "exists": self.state_dir.is_dir()},
        }

