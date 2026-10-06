import unittest
from pathlib import Path


class AskModelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("index.html").read_text(encoding="utf-8")

    def test_natural_query_routes_exist(self):
        for marker in (
            "function askWeather(",
            "function askInjuries(",
            "function askPlayer(",
            "function askMixed(",
            "function askModel(",
        ):
            self.assertIn(marker, self.html)

    def test_free_snapshot_only_contract_is_visible(self):
        self.assertIn("No paid API or public secret is used.", self.html)
        self.assertIn("The Ask box does not browse the web.", self.html)

    def test_context_fields_are_consumed(self):
        self.assertIn("S?.weather?.games", self.html)
        self.assertIn("S?.availability?.official_injury_report", self.html)
        self.assertIn("injury matchup", self.html)
        self.assertIn("g.signals||{}", self.html)


if __name__ == "__main__":
    unittest.main()
