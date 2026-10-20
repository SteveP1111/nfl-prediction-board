import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from edge_finder import assess_edge, no_vig
from odds_refresh import same_book_groups, market_name, probabilities, event_for, eligible_kickoff
from settle_edges import grade

UK = ZoneInfo("Europe/London")

class EdgeFinderTests(unittest.TestCase):
    def test_no_vig_complete_same_book(self):
        x = no_vig({"Home": 1.80, "Draw": 3.60, "Away": 4.80}, "1X2")
        self.assertAlmostEqual(sum(x["probabilities"].values()), 1)
        self.assertGreater(x["overround"], 0)
        with self.assertRaises(ValueError):
            no_vig({"Home": 1.8, "Away": 4.8}, "1X2")

    def test_edge_break_even_and_roi(self):
        info = assess_edge(
            market="1X2", selection="Home", event_probability=.65,
            quoted_price=1.80, same_book_prices={"Home":1.8, "Draw":3.6, "Away":4.8},
            bookmaker="EXAMPLE", observed_at="2026-10-20T10:00:00+01:00",
            fixture_id="2026-10-20|E0|home|away",
            kickoff_at="2026-10-20T19:45:00+01:00",
            probability_source="fixture-blind",
            evidence={"calibratedProbability": False})
        self.assertAlmostEqual(info["edgePercentagePoints"], 9.444, places=2)
        self.assertAlmostEqual(info["expectedROI"], .17)
        self.assertAlmostEqual(info["conservativeExpectedROI"], .08)
        self.assertEqual(info["classification"], "watchlist-unverified")

    def test_no_post_kickoff_price(self):
        with self.assertRaises(ValueError):
            assess_edge(
                market="BTTS", selection="Yes", event_probability=.6,
                quoted_price=1.8, same_book_prices={"Yes":1.8,"No":2.1},
                bookmaker="EXAMPLE", observed_at="2026-10-20T20:00:00+01:00",
                kickoff_at="2026-10-20T19:45:00+01:00",
                fixture_id="x", probability_source="model")

    def test_only_exact_main_game_market(self):
        self.assertEqual(market_name({"market_name":"Total Goals Over/Under",
                                      "description":"Over 2.5 vs Under 2.5"}), "Over/Under 2.5")
        self.assertIsNone(market_name({"market_name":"1st Half Total Goals"}))
        self.assertEqual(market_name({"market_name":"Both Teams to Score"}), "BTTS")

    def test_complete_prices_not_cross_book(self):
        data = {"markets": [
            {"market_name":"Match Winner", "selections":[
                {"selection_name":"Home","odds":1.8,"bookmaker_code":"UO001"},
                {"selection_name":"Draw","odds":3.6,"bookmaker_code":"UO001"},
                {"selection_name":"Away","odds":4.8,"bookmaker_code":"UO001"},
                {"selection_name":"Home","odds":1.9,"bookmaker_code":"UO002"}]},
            {"market_name":"1st Half Match Winner", "selections":[
                {"selection_name":"Home","odds":1.4,"bookmaker_code":"UO001"}]}]}
        sets = same_book_groups(data, "Home FC", "Away FC")
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0][1], "UO001")

    def test_exact_identity_and_time(self):
        game = {"id":"2026-10-21|E2|milton keynes dons|luton town",
                "date":"2026-10-21", "homeKey":"milton keynes dons",
                "awayKey":"luton town", "home":"MK Dons",
                "away":"Luton", "kickoff":"19:45"}
        now = datetime(2026,10,20,17,0,tzinfo=UK)
        event = {"event_id":"evt_example", "schedule_date":"2026-10-21",
                 "home_team":"Milton Keynes Dons","away_team":"Luton Town",
                 "kickoff_utc":"2026-10-21T18:45:00Z"}
        self.assertEqual(event_for(game,[event],now),event)
        self.assertIsNone(event_for(game,[event,{**event,"event_id":"evt_duplicate"}],now))
        self.assertIsNone(event_for(game,[{**event,"away_team":"Other"}],now))
        self.assertIsNone(eligible_kickoff(game, datetime(2026,10,21,20,0,tzinfo=UK)))

    def test_raw_probability_complement(self):
        game={"scoreline":{"markets":{"over35":.42}}}
        self.assertEqual(probabilities(game,"Over/Under 3.5"),
                         {"Over 3.5":.42,"Under 3.5":.58})

    def test_settlement_from_frozen_odds_and_result(self):
        record={"fixtureId":"x", "market":"BTTS", "selection":"Yes",
                "modelEventProbability":.65, "quotedDecimalOdds":1.8,
                "observedAt":"2026-10-20T10:00:00+01:00",
                "kickoffAt":"2026-10-20T19:45:00+01:00"}
        result={"score":"2-1","outcomes":{"btts":True}}
        g=grade(record,result)
        self.assertEqual(g["outcome"],"Win")
        self.assertAlmostEqual(g["flatUnitROI"],.8)
        self.assertAlmostEqual(g["brier"],.1225)
        self.assertIsNone(grade({**record,"observedAt":"2026-10-20T20:00:00+01:00"},result))

if __name__ == "__main__":
    unittest.main()
