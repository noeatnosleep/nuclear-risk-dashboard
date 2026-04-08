import unittest

from events import classify_event
from risk import apply_updates_with_clamp, clamp, compute_probability


class RiskSystemGuards(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(clamp(99, 0, 10), 10)
        self.assertEqual(clamp(-3, 0, 10), 0)

    def test_state_update_bounds(self):
        state = {"a": 5.0, "b": 9.8}
        updates = {"a": 20.0, "b": -20.0}
        out = apply_updates_with_clamp(state, updates)
        self.assertTrue(0 <= out["a"] <= 10)
        self.assertTrue(0 <= out["b"] <= 10)

    def test_probability_bounds(self):
        state = {
            "us_russia": 10,
            "us_china": 10,
            "china_taiwan": 10,
            "india_pakistan": 10,
            "china_india": 10,
            "iran_us": 10,
            "iran_israel": 10,
            "nk_us": 10,
            "nk_sk": 10,
            "nk_japan": 10,
            "russia_ukraine": 10,
        }
        p = compute_probability(state)
        self.assertTrue(0 <= p <= 100)

    def test_contradiction_penalty_path(self):
        event = {
            "title": "Country launches strike then agrees ceasefire talks",
            "summary": "missile strike followed by ceasefire negotiations",
            "source_weight": 1.0,
            "published": "2026-04-08 00:00:00 UTC",
        }
        result = classify_event(event)
        self.assertIn("ok", result)


if __name__ == "__main__":
    unittest.main()
