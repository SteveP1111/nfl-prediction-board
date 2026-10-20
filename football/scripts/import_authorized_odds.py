#!/usr/bin/env python3
"""Validate a manually supplied or licensed pre-kickoff odds JSON file and freeze edge analysis.

Usage: python football/scripts/import_authorized_odds.py INPUT.json
No scraping or odds API calls. Do not import source data without permission.
INPUT: {"date":"YYYY-MM-DD","quotes":[{"fixtureId":"...","market":"1X2",
"bookmaker":"...","observedAt":"ISO offset","kickoffAt":"ISO offset",
"prices":{"Home":2.0,"Draw":3.4,"Away":4.0},"source":"permitted source name"}]}
"""
import json, sys
from datetime import datetime
from pathlib import Path
from edge_finder import MARKETS, assess_edge, no_vig

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KEYS = {"1X2":{"Home":"home_win","Draw":"draw","Away":"away_win"},
        "BTTS":{"Yes":"btts","No":"no_btts"},
        "Over/Under 2.5":{"Over 2.5":"over25","Under 2.5":"under25"},
        "Over/Under 3.5":{"Over 3.5":"over35"}}

def main(path):
    inp=json.loads(Path(path).read_text(encoding="utf-8"))
    day=inp["date"]
    datetime.strptime(day,"%Y-%m-%d")
    forecast_file=DATA/"snapshots"/(day+".json")
    if not forecast_file.exists():raise ValueError("No existing frozen independent forecast")
    snap=json.loads(forecast_file.read_text(encoding="utf-8"))
    if snap.get("date")!=day or snap.get("status")!="frozen-prekickoff":
        raise ValueError("Forecast is not a valid frozen pre-kickoff snapshot")
    games={g["id"]:g for g in snap.get("games",[])}
    output=DATA/"edge-snapshots"/(day+".json")
    if output.exists():raise ValueError("Immutable dated edge snapshot already exists")
    rows=[]; now=datetime.now().astimezone()
    for quote in inp["quotes"]:
        fid=quote["fixtureId"];market=quote["market"];prices=quote["prices"]
        if fid not in games or not fid.startswith(day+"|"):raise ValueError("Unknown canonical fixture: "+fid)
        if market not in MARKETS:raise ValueError("Unsupported market: "+market)
        observed=datetime.fromisoformat(quote["observedAt"])
        kickoff=datetime.fromisoformat(quote["kickoffAt"])
        if observed.tzinfo is None or kickoff.tzinfo is None or not observed<kickoff or not now<kickoff:
            raise ValueError("Must freeze before fixture kickoff")
        if not quote.get("source") or not quote.get("bookmaker"):
            raise ValueError("Verified source and bookmaker required")
        no_vig(prices,market) # reject incomplete markets
        g=games[fid];probs=g.get("scoreline",{}).get("markets",{})
        for selection in MARKETS[market]:
            key=KEYS.get(market,{}).get(selection)
            if not key or key not in probs:continue
            p=probs[key]
            if not isinstance(p,(int,float)):continue
            result=assess_edge(
                market=market,selection=selection,event_probability=p,
                quoted_price=prices[selection],same_book_prices=prices,
                bookmaker=quote["bookmaker"],observed_at=quote["observedAt"],
                kickoff_at=quote["kickoffAt"],fixture_id=fid,
                probability_source="INDEPENDENT_SCORELINE_V1_GITHUB (uncalibrated)",
                evidence={"teamIdentityVerified":True,"marketMatched":True,
                          "independentSupport":False,"sampleCoverageAdequate":False,
                          "calibratedProbability":False})
            result["source"]=quote["source"]
            result["reason"]="Raw independent Scoreline Model probability is uncalibrated; research watchlist only."
            rows.append(result)
    if not rows:raise ValueError("No comparable markets; no snapshot written")
    output.parent.mkdir(parents=True,exist_ok=True)
    payload={"date":day,"status":"frozen-prekickoff","capturedAt":now.isoformat(),
             "model":"EXPERIMENTAL_EDGE_WATCHLIST_V1","entries":rows,
             "sourcePolicy":"User-provided or expressly licensed odds only; no automated scraping"}
    output.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Frozen",len(rows),"research watchlist comparisons to",output)
if __name__=="__main__":main(sys.argv[1])
