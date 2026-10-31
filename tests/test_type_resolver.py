from __future__ import annotations

import unittest

from afsim_assistant.type_resolver import resolve_force_types


class FakeCaller:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments=None):
        self.last = (name, arguments)
        self.calls.append((name, arguments))
        keyword = (arguments or {}).get("keyword")
        if keyword == "SAM":
            return {
                "types": [
                    {
                        "name": "RADAR_ONLY_SAM",
                        "domain": "undetermined",
                        "sensors": 1,
                        "weapons": 0,
                        "processors": 1,
                        "can_engage": False,
                    },
                    {
                        "name": "SAM_BATTERY",
                        "domain": "undetermined",
                        "sensors": 1,
                        "weapons": 1,
                        "processors": 3,
                        "can_engage": True,
                        "defined_in": "platforms/sam_battery.txt",
                    },
                    {
                        "name": "BLUE_LR_SAM",
                        "domain": "undetermined",
                        "sensors": 1,
                        "weapons": 1,
                        "processors": 3,
                        "can_engage": True,
                        "defined_in": "weapons/sam/blue_lr_sam_complex.txt",
                    },
                ]
            }
        if keyword == "AIR_TARGET":
            return {
                "types": [
                    {
                        "name": "AIR_TARGET",
                        "domain": "air",
                        "sensors": 0,
                        "weapons": 0,
                        "processors": 0,
                        "can_engage": False,
                        "loads": True,
                    }
                ]
            }
        return {"types": []}


class TypeResolverTests(unittest.TestCase):
    def test_capable_sam_and_exact_air_target_rank_first(self):
        spec = {
            "forces": [
                {
                    "role": "air_defense_site",
                    "domain": "land",
                    "requested_type": None,
                },
                {
                    "role": "aircraft",
                    "domain": "air",
                    "requested_type": None,
                },
            ]
        }
        caller = FakeCaller()
        result = resolve_force_types(caller, spec, limit=3)
        self.assertEqual(result[0]["candidates"][0]["name"], "SAM_BATTERY")
        self.assertIn("can_engage", result[0]["candidates"][0]["reasons"])
        weapon_candidate = next(
            item for item in result[0]["candidates"] if item["name"] == "BLUE_LR_SAM"
        )
        self.assertLess(weapon_candidate["score"], result[0]["candidates"][0]["score"])
        self.assertEqual(result[1]["candidates"][0]["name"], "AIR_TARGET")
        sam_call = next(args for _name, args in caller.calls if args.get("keyword") == "SAM")
        air_call = next(args for _name, args in caller.calls if args.get("keyword") == "AIR_TARGET")
        self.assertNotIn("domain", sam_call)
        self.assertEqual(air_call["domain"], "air")


if __name__ == "__main__":
    unittest.main()
