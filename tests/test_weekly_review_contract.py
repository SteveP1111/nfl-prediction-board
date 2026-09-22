from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from weekly_review_contract import normalise_weekly_review


def final_review():
    games=[]
    for i in range(16):
        gid=f"2026_02_A{i:02d}_B{i:02d}"
        games.append({
            "game_id":gid,
            "final":f"A{i:02d} 20 · B{i:02d} 17",
            "actual_total":37,
            "winner_result":"Correct" if i<9 else "Miss",
            "spread_result":"Correct" if i<9 else "Miss",
            "total_result":"Correct" if i<7 else "Miss",
        })
    return {
        "type":"weekly_model_review",
        "review_scope":"game_lines_final",
        "season":2026,
        "week":2,
        "games":games,
        "authoritative_metrics":{
            "winner":{"correct":9,"miss":7,"decisions":16},
            "spread":{"correct":9,"miss":7,"push":0,"decisions":16},
            "total":{"correct":7,"miss":9,"push":0,"decisions":16},
        },
    }


class WeeklyReviewContractTests(unittest.TestCase):
    def test_derives_all_48_game_outcomes(self):
        review=normalise_weekly_review(final_review())
        self.assertEqual(len(review["game_outcomes"]),48)
        self.assertEqual(review["game_outcomes"]["win:2026_02_A00_B00"]["result"],"Correct")
        self.assertEqual(review["game_outcomes"]["total:2026_02_A15_B15"]["actual"],"37 points")

    def test_refuses_partial_final_review(self):
        review=final_review()
        review["games"]=review["games"][:15]
        with self.assertRaises(ValueError):
            normalise_weekly_review(review)

    def test_refuses_metric_mismatch(self):
        review=final_review()
        review["authoritative_metrics"]["winner"]["correct"]=8
        with self.assertRaises(ValueError):
            normalise_weekly_review(review)


if __name__ == "__main__":
    unittest.main()
