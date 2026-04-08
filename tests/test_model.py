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

    def test_deescalation_classification(self):
        cls = events.classify_text("US and Iran announce ceasefire and withdrawal")
        self.assertEqual(cls, "deescalation")

    def test_event_classification_with_fallback(self):
        classified = events.classify_event(
            {
                "title": "Iran missile doctrine discussed in parliament",
                "published": "2026-04-08T11:00:00Z",
            }
        )
        self.assertIsNotNone(classified)
        self.assertIn("iran", classified["actors"])

    def test_apply_updates_clamp(self):
        state = {"us_china": 5.0}
        updates = {"us_china": 99.0}
        new_state = risk.apply_updates_with_clamp(state, updates)
        self.assertEqual(new_state["us_china"], 6.25)

    def test_cross_state_coupling(self):
        updates = {"us_china": 1.0, "china_taiwan": 0.0, "iran_us": 0.0, "iran_israel": 0.0, "russia_ukraine": 0.0, "us_russia": 0.0}
        coupled = risk.apply_cross_state_coupling(updates)
        self.assertAlmostEqual(coupled["china_taiwan"], 0.35, places=6)

    def test_zero_event_decay_path(self):
        probability, state, _ = risk.run([])
        self.assertIsInstance(probability, float)
        self.assertIsInstance(state, dict)


if __name__ == "__main__":
    unittest.main()
