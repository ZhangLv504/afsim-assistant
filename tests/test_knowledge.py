from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from afsim_assistant.catalog import build_catalog
from afsim_assistant.config import Settings
from afsim_assistant.search import rebuild_index, search


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        # Keep test data inside the writable project tree. On managed Windows
        # environments the process can read, but cannot create children in,
        # the system TEMP directory.
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        root = Path(self.temp.name)
        self.skill = root / "skill"
        self.demos = root / "demos"
        self.state = root / "state"
        (self.skill / "templates").mkdir(parents=True)
        (self.skill / "blocks" / "leo_constellation").mkdir(parents=True)
        (self.demos / "launcher").mkdir(parents=True)
        (self.demos / "six_dof" / "data").mkdir(parents=True)
        (self.skill / "templates" / "main.txt").write_text(
            "include setup.txt\nend_time 120 secs\n", encoding="utf-8"
        )
        (self.skill / "INDEX.md").write_text(
            "# Index\nLEO_SAT navigation entry\n", encoding="utf-8"
        )
        (self.skill / "blocks" / "sam.txt").write_text(
            "sensor SAM_RADAR WSF_RADAR_SENSOR\nend_sensor\n", encoding="utf-8"
        )
        (self.skill / "blocks" / "leo_constellation" / "satellite.txt").write_text(
            "platform_type LEO_SAT WSF_PLATFORM\n", encoding="utf-8"
        )
        (self.demos / "launcher" / "sam_launcher.txt").write_text(
            "processor SAM_TASKS WSF_TASK_PROCESSOR\nend_processor\n", encoding="utf-8"
        )
        (self.demos / "six_dof" / "data" / "table.txt").write_text(
            "SAM numeric table should not be indexed\n", encoding="utf-8"
        )
        self.settings = Settings(
            workspace_root=root,
            app_root=root,
            projectskill_root=self.skill,
            demos_root=self.demos,
            mcp_root=root / "mcp",
            afsim_bin=root / "bin",
            state_dir=self.state,
            demo_max_bytes=1024,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_statuses_and_leo_exclusion(self):
        catalog = build_catalog(self.settings)
        by_id = {item["id"]: item for item in catalog["entries"]}
        self.assertEqual(by_id["projectskill:templates/main.txt"]["status"], "validated")
        self.assertEqual(by_id["projectskill:blocks/sam.txt"]["status"], "unverified")
        self.assertEqual(
            by_id["projectskill:blocks/leo_constellation/satellite.txt"]["status"],
            "excluded",
        )
        self.assertEqual(by_id["projectskill:INDEX.md"]["status"], "excluded")
        self.assertEqual(by_id["demo:launcher/sam_launcher.txt"]["status"], "official")
        self.assertNotIn("demo:six_dof/data/table.txt", by_id)

    def test_default_search_excludes_unverified(self):
        catalog = build_catalog(self.settings)
        rebuild_index(self.settings, catalog)
        official = search(self.settings, "SAM TASKS")
        self.assertEqual(len(official), 1)
        self.assertEqual(official[0]["source"], "demo")
        self.assertEqual(search(self.settings, "SAM RADAR"), [])
        with_unverified = search(
            self.settings,
            "SAM RADAR",
            statuses=("official", "validated", "verified", "unverified"),
        )
        self.assertEqual(len(with_unverified), 1)
        self.assertEqual(with_unverified[0]["status"], "unverified")
        self.assertEqual(
            search(
                self.settings,
                "LEO SAT",
                statuses=("official", "validated", "verified", "unverified"),
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()

