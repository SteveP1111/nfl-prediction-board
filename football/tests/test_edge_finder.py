import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from edge_finder import no_vig, assess_edge

class EdgeTests(unittest.TestCase):
    def test_no_vig_normalized(self):
        p=no_vig({"Home":1.8,"Draw":3.6,"Away":4.8},"1X2")
        self.assertAlmostEqual(sum(p["probabilities"].values()),1.0)
        self.assertGreater(p["overround"],0)
    def test_incomplete_market_fails(self):
        with self.assertRaises(ValueError):no_vig({"Home":1.8},"1X2")
    def test_example_math(self):
        q=assess_edge(market="1X2",selection="Home",event_probability=.65,
            quoted_price=1.8,same_book_prices={"Home":1.8,"Draw":3.6,"Away":4.8},
            bookmaker="EXAMPLE",observed_at="2026-10-20T10:00:00+01:00",
            kickoff_at="2026-10-21T19:45:00+01:00",
            fixture_id="2026-10-21|E0|home|away",probability_source="test")
        self.assertAlmostEqual(q["expectedROI"],.17)
        self.assertAlmostEqual(q["edgePercentagePoints"],9.444,places=2)
        self.assertEqual(q["classification"],"watchlist-unverified")
    def test_after_kickoff_fails(self):
        with self.assertRaises(ValueError):
            assess_edge(market="BTTS",selection="Yes",event_probability=.6,
                quoted_price=1.8,same_book_prices={"Yes":1.8,"No":2.0},
                bookmaker="EXAMPLE",observed_at="2026-10-21T20:00:00+01:00",
                kickoff_at="2026-10-21T19:45:00+01:00",
                fixture_id="2026-10-21|E0|home|away",probability_source="test")
if __name__=="__main__":unittest.main()
