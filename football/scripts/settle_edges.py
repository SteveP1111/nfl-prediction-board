#!/usr/bin/env python3
"""Grade immutable pre-kickoff odds comparisons against independently verified match finals.

Settlement file is mutable; input odds/forecast snapshots never are.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
TRUTH = {
    ("1X2", "Home"): "home_win",
    ("1X2", "Draw"): "draw",
    ("1X2", "Away"): "away_win",
    ("BTTS", "Yes"): "btts",
    ("BTTS", "No"): "no_btts",
    ("Over/Under 2.5", "Over 2.5"): "over25",
    ("Over/Under 2.5", "Under 2.5"): "under25",
    ("Over/Under 3.5", "Over 3.5"): "over35",
}

def grade(record, result):
    if not isinstance(result, dict) or not result.get("score"):
        return None
    try:
        home, away = map(int, result["score"].split("-"))
    except (ValueError, AttributeError): return None
    kind = record.get("market")
    sel = record.get("selection")
    key = TRUTH.get((kind, sel))
    if key == "over35":
        won = home + away >= 4
    elif (kind, sel) == ("Over/Under 3.5", "Under 3.5"):
        won = home + away <= 3
    elif key:
        outcome = result.get("outcomes", {})
        if key not in outcome or not isinstance(outcome[key], bool): return None
        won = outcome[key]
    else:
        return None
    try:
        prob = float(record["modelEventProbability"])
        odds = float(record["quotedDecimalOdds"])
        at = datetime.fromisoformat(record["observedAt"])
        kickoff = datetime.fromisoformat(record["kickoffAt"])
        if not 0 <= prob <= 1 or odds <= 1.001 or at.tzinfo is None or kickoff.tzinfo is None or at >= kickoff:
            return None
    except (ValueError, TypeError, KeyError): return None
    return {"outcome": "Win" if won else "Loss", "win": won,
            "finalScore": result["score"],
            "flatUnitROI": round(odds - 1 if won else -1.0, 4),
            "brier": round((prob - int(won)) ** 2, 6)}

def performance(records):
    summary = defaultdict(lambda: {"graded": 0, "wins": 0, "units": 0.0, "brierSum": 0.0})
    for r in records:
        group = r["division"] + "|" + r["market"]
        for key in ["all", "league:" + r["division"], "market:" + r["market"],
                    "leagueMarket:" + group,
                    "positiveEdge" if r["edgePercentagePoints"] > 0 else "nonPositiveEdge"]:
            s=summary[key];s["graded"]+=1;s["wins"]+=int(r["win"])
            s["units"]+=r["flatUnitROI"];s["brierSum"]+=r["brier"]
    return {k: {"graded": v["graded"], "wins": v["wins"],
                "hitRate": round(v["wins"] / v["graded"], 4),
                "flatUnitProfit": round(v["units"], 4),
                "flatUnitROI": round(v["units"] / v["graded"], 4),
                "brier": round(v["brierSum"] / v["graded"], 5)}
            for k,v in sorted(summary.items())}

def main():
    folder = DATA / "edge-snapshots"
    if not folder.exists(): return
    settled_path = DATA / "settlements.json"
    if not settled_path.exists(): return
    settled = json.loads(settled_path.read_text(encoding="utf-8"))
    rows=[]
    for file in sorted(folder.glob("????-??-??.json")):
        try: shot=json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError): continue
        if shot.get("date") != file.stem or shot.get("status") != "frozen-prekickoff": continue
        for match in shot.get("games", []):
            fixture_id=match.get("id")
            if not fixture_id or not fixture_id.startswith(shot["date"]+"|"): continue
            result=settled.get(fixture_id)
            if not result: continue
            for record in match.get("comparisons", []):
                if record.get("fixtureId") != fixture_id: continue
                outcome=grade(record,result)
                if not outcome: continue
                rows.append({"fixtureId":fixture_id, "date":shot["date"],
                             "division":match.get("division"), "market":record["market"],
                             "selection":record["selection"], "bookmaker":record["bookmaker"],
                             "quotedDecimalOdds":record["quotedDecimalOdds"],
                             "modelEventProbability":record["modelEventProbability"],
                             "edgePercentagePoints":record["edgePercentagePoints"],
                             "classification":record["classification"],
                             **outcome})
    out = {"status":"prospective-only", "model":"INDEPENDENT_SCORELINE_V1_GITHUB",
           "graded":len(rows), "byGroup":performance(rows), "results":rows,
           "warning":"Comparisons are clustered by fixture and bookmaker. Raw probabilities are uncalibrated. ROI assumes unchanged quoted odds and equal one-unit stakes; this is not actual betting performance."}
    (DATA/"edge-settlements.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Graded",len(rows),"previously frozen bookmaker research comparisons")

if __name__=="__main__":
    main()
