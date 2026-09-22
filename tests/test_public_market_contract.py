from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_staging


def valid_snapshot():
    teams=["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LA","LAC","LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"]
    games=[]
    for i in range(16):
        games.append({
            "game_id":f"g{i}",
            "away":teams[i*2],
            "home":teams[i*2+1],
            "away_projection":20.0,
            "home_projection":21.0,
            "total_projection":41.0,
            "winner_rating":70,
            "spread_rating":60,
            "total_rating":55,
            "spread_line":1.5,
            "spread_pick":f"{teams[i*2]} +1.5",
            "total_line":42.5,
            "total_pick":"No meaningful edge",
            "spread_side":teams[i*2],
            "total_side":None,
        })
    props=[]
    for team in teams:
        for n in range(8):
            props.append({
                "game_id":games[teams.index(team)//2]["game_id"],
                "player_id":f"{team}-{n}",
                "name":f"{team} Defender {n}",
                "team":team,
                "type":"tackles",
                "label":"Tackles + assists",
                "projection":4.0,
                "rating":50.0,
            })
    tds=[]
    for i,team in enumerate(teams[:25]):
        tds.append({
            "game_id":games[i//2]["game_id"],
            "player_id":f"td-{i}",
            "name":f"TD {i}",
            "team":team,
            "prob":0.2,
            "rating":50.0,
        })
    return {
        "id":"test",
        "season":2026,
        "week":3,
        "slot":"test",
        "capturedAt":"2026-09-23T00:00:00+01:00",
        "games":games,
        "props":props,
        "tds":tds,
        "outcomes":{},
    }


class PublicMarketContractTests(unittest.TestCase):
    def test_rejects_missing_spread_line(self):
        snap=valid_snapshot()
        snap["games"][0]["spread_line"]=None
        with self.assertRaises(SystemExit):
            publish_staging.validate_payload({"snapshots":[snap]})

    def test_rejects_missing_total_pick(self):
        snap=valid_snapshot()
        snap["games"][0]["total_pick"]="—"
        with self.assertRaises(SystemExit):
            publish_staging.validate_payload({"snapshots":[snap]})

    def test_accepts_no_meaningful_edge_total(self):
        snap=valid_snapshot()
        publish_staging.validate_payload({"snapshots":[snap]})


if __name__=="__main__":
    unittest.main()
