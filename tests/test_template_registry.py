from __future__ import annotations

import unittest

from afsim_assistant.template_registry import PlanningError, select_generation_plan


class TemplateRegistryTests(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "forces": [
                {
                    "side": "blue",
                    "role": "air_defense_site",
                    "domain": "land",
                    "count": 1,
                    "requested_type": None,
                },
                {
                    "side": "red",
                    "role": "aircraft",
                    "domain": "air",
                    "count": 1,
                    "requested_type": None,
                },
            ],
            "capabilities": ["detection", "tracking", "weapon_engagement"],
        }

    def test_template_context_types_win_over_global_candidates(self):
        resolution = [
            {
                "force_index": 0,
                "candidates": [{"name": "SAM_BATTERY"}],
            },
            {
                "force_index": 1,
                "candidates": [{"name": "AIR_TARGET"}],
            },
        ]
        plan = select_generation_plan(self.spec, resolution)
        bindings = {item["role"]: item for item in plan["force_bindings"]}
        self.assertEqual(bindings["air_defense_site"]["selected_type"], "SAM_LAUNCHER")
        self.assertEqual(bindings["aircraft"]["selected_type"], "AIRPLANE")
        self.assertEqual(
            bindings["air_defense_site"]["global_candidates_for_reference"],
            ["SAM_BATTERY"],
        )
        self.assertTrue(
            plan["selection_policy"]["types_must_come_from_selected_template_context"]
        )

    def test_incompatible_explicit_type_is_rejected(self):
        self.spec["forces"][0]["requested_type"] = "SAM_BATTERY"
        with self.assertRaisesRegex(PlanningError, "not available"):
            select_generation_plan(self.spec)

    def test_unsupported_force_shape_is_rejected(self):
        self.spec["forces"][1]["count"] = 2
        with self.assertRaisesRegex(PlanningError, "roles/counts"):
            select_generation_plan(self.spec)


if __name__ == "__main__":
    unittest.main()
