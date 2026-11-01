from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from afsim_assistant.config import Settings
from afsim_assistant.project_builder import (
    BuildError,
    build_sam_air_intercept,
    enforce_capability_evidence,
)


class ProjectBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        root = Path(self.temp.name)
        demos = root / "demos"
        launcher = demos / "launcher"
        (launcher / "platforms").mkdir(parents=True)
        (launcher / "scenarios").mkdir(parents=True)
        (launcher / "setup.txt").write_text("file_path .\n", encoding="utf-8")
        (launcher / "platforms" / "tactics_processor1.txt").write_text(
            "processor P WSF_TASK_PROCESSOR end_processor\n", encoding="utf-8"
        )
        self.settings = Settings(
            workspace_root=root,
            app_root=root / "app",
            projectskill_root=root / "skill",
            demos_root=demos,
            mcp_root=root / "mcp",
            afsim_bin=root / "bin",
            state_dir=root / "state",
        )
        self.spec = {
            "scenario_name": "sam_test",
            "duration": {"value": 10, "unit": "minutes"},
            "forces": [
                {"role": "air_defense_site", "count": 1},
                {"role": "aircraft", "count": 1},
            ],
            "capabilities": ["detection", "tracking", "weapon_engagement"],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_builds_new_staging_project_and_manifest(self):
        result = build_sam_air_intercept(self.settings, self.spec)
        project = Path(result["project_dir"])
        self.assertIn("end_time 600 sec", Path(result["entry_file"]).read_text(encoding="utf-8"))
        manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "staging")
        self.assertEqual(manifest["selected_context_types"]["air_defense_site"], "SAM_LAUNCHER")
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["template"]["dependency_strategy"], "copy_official_demo_subtree")
        self.assertTrue(manifest["dependency_inventory"])
        self.assertTrue(all(item["sha256"] for item in manifest["dependency_inventory"]))
        with self.assertRaisesRegex(BuildError, "already exists"):
            build_sam_air_intercept(self.settings, self.spec)

    def test_required_capabilities_need_event_evidence(self):
        raw = {
            "ok": True,
            "validated": True,
            "problems": [],
            "outputs": {"evt_categories": {"PLATFORM_ADDED": 2}},
        }
        checked = enforce_capability_evidence(self.spec, raw)
        self.assertFalse(checked["ok"])
        self.assertEqual(len(checked["problems"]), 3)

        raw["outputs"]["evt_categories"].update(
            {"SENSOR_TRACK_INITIATED": 1, "WEAPON_FIRED": 1}
        )
        checked = enforce_capability_evidence(self.spec, raw)
        self.assertTrue(checked["ok"])
        self.assertTrue(checked["capability_evidence"]["tracking"]["satisfied"])


if __name__ == "__main__":
    unittest.main()
