from __future__ import annotations

import unittest

from afsim_assistant.scenario_spec import validate_spec


class ScenarioSpecTests(unittest.TestCase):
    def test_search_terms_are_trimmed_and_deduplicated(self):
        spec = {
            "scenario_name": "sam_intercept",
            "summary": "SAM intercepts an aircraft",
            "duration": {"value": 10, "unit": "minutes"},
            "forces": [],
            "capabilities": ["detection", "weapon_engagement"],
            "constraints": [],
            "unknowns": ["duration"],
            "search_terms": [" SAM launcher ", "SAM   launcher", "air target"],
        }
        validated = validate_spec(spec)
        self.assertEqual(validated["search_terms"], ["SAM launcher", "air target"])

    def test_missing_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing fields"):
            validate_spec({"search_terms": ["SAM", "radar"]})

    def test_generic_roles_are_not_accepted_as_closed_types(self):
        spec = {
            "scenario_name": "sam_intercept",
            "summary": "SAM intercepts an aircraft",
            "duration": {"value": 10, "unit": "minutes"},
            "forces": [
                {
                    "side": "blue",
                    "role": "air_defense_site",
                    "domain": "air",
                    "count": 1,
                    "requested_type": "SAM launcher",
                },
                {
                    "side": "red",
                    "role": "aircraft",
                    "domain": "land",
                    "count": 1,
                    "requested_type": "LTE_FIGHTER",
                },
            ],
            "capabilities": ["detection", "detection", "tracking"],
            "constraints": ["Simulate for 10 minutes", "fixed altitude"],
            "unknowns": [],
            "search_terms": ["SAM launcher", "air target"],
        }
        validated = validate_spec(spec)
        self.assertIsNone(validated["forces"][0]["requested_type"])
        self.assertEqual(validated["forces"][1]["requested_type"], "LTE_FIGHTER")
        self.assertEqual(validated["forces"][0]["domain"], "land")
        self.assertEqual(validated["forces"][1]["domain"], "air")
        self.assertEqual(validated["capabilities"], ["detection", "tracking"])
        self.assertEqual(validated["constraints"], ["fixed altitude"])


if __name__ == "__main__":
    unittest.main()

