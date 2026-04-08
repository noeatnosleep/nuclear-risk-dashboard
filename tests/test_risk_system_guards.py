import unittest

from events import classify_event
from risk import apply_updates_with_clamp, compute_probability, merge_driver_clusters
from states import BASELINE_STATE


class RiskSystemGuardsTests(unittest.TestCase):
    def test_apply_updates_with_clamp_bounds(self):
        state = {"a": 9.8, "b": 0.2}
        updates = {"a": 5.0, "b": -5.0}
        out = apply_updates_with_clamp(state, updates)
        self.assertLessEqual(out["a"], 10)
        self.assertGreaterEqual(out["b"], 0)

    def test_probability_is_bounded(self):
        low_state = {k: 0 for k in BASELINE_STATE}
        high_state = {k: 10 for k in BASELINE_STATE}
        self.assertGreaterEqual(compute_probability(low_state), 0)
        self.assertLessEqual(compute_probability(high_state), 100)

    def test_classify_event_contradiction_is_still_bounded(self):
        event = {
            "title": "US and Iran missile strike announced during ceasefire talks",
            "summary": "Officials discuss withdrawal while new strike rhetoric escalates.",
            "published": "2026-04-08T00:00:00Z",
            "source_weight": 1.0,
        }
        result = classify_event(event)
        if result.get("ok"):
            self.assertGreaterEqual(result["impact"], -1.25)
            self.assertLessEqual(result["impact"], 1.25)

    def test_driver_cluster_merging_counts_corroboration(self):
        drivers = [
            {
                "title": "US and China hold emergency nuclear talks",
                "state_key": "us_china",
                "impact": 0.5,
                "confidence": 0.6,
                "source_domain": "a.com",
                "link": "https://a.com/1",
            },
            {
                "title": "US-China hold emergency nuclear talks",
                "state_key": "us_china",
                "impact": 0.4,
                "confidence": 0.65,
                "source_domain": "b.com",
                "link": "https://b.com/2",
            },
        ]
        merged = merge_driver_clusters(drivers)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["corroboration_count"], 2)


if __name__ == "__main__":
    unittest.main()
