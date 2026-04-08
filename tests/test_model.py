import unittest

import events
import risk
from actors import extract_actors, has_conflict_signal


class TestModel(unittest.TestCase):
    def test_extract_actors(self):
        text = "US and China hold emergency talks after missile drill"
        actors = extract_actors(text)
        self.assertIn("us", actors)
        self.assertIn("china", actors)

    def test_conflict_signal_detection(self):
        self.assertTrue(has_conflict_signal("Iran and Israel agree to ceasefire talks"))
        self.assertFalse(has_conflict_signal("Iran and Israel cultural exchange event"))

    def test_rfc822_timestamp_parse(self):
        hours = events.hours_since("Wed, 08 Apr 2026 12:00:00 GMT")
        self.assertGreaterEqual(hours, 0)

    def test_mixed_signal_ambiguity_penalty(self):
        event = {
            "title": "Israel strikes after ceasefire talks with Iran",
            "summary": "Both active attacks and negotiations reported.",
            "published": "2026-04-08T11:00:00Z",
            "source_weight": 1.0,
        }
        classified = events.classify_event(event)
        self.assertTrue(classified["ok"])
        self.assertGreater(classified["impact"], 0)
        self.assertLessEqual(classified["confidence"], 1.0)

    def test_single_actor_fallback_disabled(self):
        event = {
            "title": "Iran conducts missile test",
            "summary": "No other state explicitly named.",
            "published": "2026-04-08T11:00:00Z",
            "source_weight": 1.0,
        }
        classified = events.classify_event(event)
        self.assertFalse(classified["ok"])
        self.assertEqual(classified["reason"], "invalid_pair")

    def test_deterministic_pair_selection(self):
        actors = ["us", "china", "russia"]
        state_key = events.choose_state_key_from_actors(actors)
        self.assertEqual(state_key, "us_russia")

    def test_apply_updates_clamp(self):
        state = {"us_china": 5.0}
        updates = {"us_china": 99.0}
        new_state = risk.apply_updates_with_clamp(state, updates)
        self.assertEqual(new_state["us_china"], 6.0)

    def test_cross_state_coupling(self):
        updates = {
            "us_china": 1.0,
            "china_taiwan": 0.0,
            "iran_us": 0.0,
            "iran_israel": 0.0,
            "russia_ukraine": 0.0,
            "us_russia": 0.0,
        }
        coupled = risk.apply_cross_state_coupling(updates)
        self.assertAlmostEqual(coupled["china_taiwan"], 0.2, places=6)

    def test_uncertainty_output(self):
        probability, state, drivers = risk.run([])
        self.assertIsInstance(probability, float)
        self.assertIsInstance(state, dict)
        self.assertIsInstance(drivers, list)


if __name__ == "__main__":
    unittest.main()
