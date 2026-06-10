import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from campaign_brain.goal_parser import parse_goal


class TestGoalParser(unittest.TestCase):
    """Tests for marketer goal interpretation."""

    def test_reactivation_phrases(self):
        phrases = [
            "bring back inactive customers",
            "win back dormant users",
            "reduce churn among inactive shoppers",
        ]

        for phrase in phrases:
            with self.subTest(goal=phrase):
                result = parse_goal(phrase)
                self.assertEqual(
                    result["objective"],
                    "REACTIVATION",
                )

    def test_loyalty_phrases(self):
        phrases = [
            "reward loyal customers",
            "retain our best customers",
            "increase loyalty among repeat buyers",
        ]

        for phrase in phrases:
            with self.subTest(goal=phrase):
                result = parse_goal(phrase)
                self.assertEqual(
                    result["objective"],
                    "LOYALTY",
                )

    def test_upsell_phrases(self):
        phrases = [
            "increase average order value",
            "upsell premium products",
            "encourage customers to buy higher value items",
        ]

        for phrase in phrases:
            with self.subTest(goal=phrase):
                result = parse_goal(phrase)
                self.assertEqual(
                    result["objective"],
                    "UPSELL",
                )

    def test_cross_sell_phrases(self):
        phrases = [
            "recommend complementary products",
            "suggest related products",
            "cross sell relevant items",
        ]

        for phrase in phrases:
            with self.subTest(goal=phrase):
                result = parse_goal(phrase)
                self.assertEqual(
                    result["objective"],
                    "CROSS_SELL",
                )

    def test_unknown_goal_returns_manual_review(self):
        result = parse_goal(
            "launch a campaign on mars next week"
        )

        self.assertEqual(
            result["objective"],
            "MANUAL_REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
