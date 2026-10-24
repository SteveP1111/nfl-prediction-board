#!/usr/bin/env python3
"""Under 3.5 research report, separate from B3.1 and Edge Finder.
Reads only existing immutable pre-kickoff snapshots and independently settled results.
Never creates or revises forecasts, odds, or model weights.
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
THRESHOLDS = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80)

def report(data=DATA):
    settlements_path = data / "settlements.json"
    settlements = json.loads(settlements_path.read_text()) if settlements_path.exists() else {}
    edge_dir = data / "edge-snapshots"
    edge_files = {p.stem: p for p in edge_dir.glob("????-??-??.json")} if edge_dir.exists() else {}
    rows = []
    exclusions = defaultdict(int)
    for path in sorted((data / "snapshots").glob("????-??-??.json")):
        shot = json.loads(path.read_text())
        try:
            captured = datetime.fromisoformat(shot["capturedAt"])
        except (ValueError, KeyError, TypeError):
            exclusions["missing_snapshot_capture_time"] += 1
            continue
        edge = json.loads(edge_files[path.stem].read_text()) if path.stem in edge_files else {}
        edge_by_id = {g["id"]: g for g in edge.get("games", []) if g.get("id")}
        for game in shot.get("games", []):
            ident = game.get("id")
            if not ident or ident not in settlements:
                exclusions["not_settled"] += 1
                continue
            try:
                # Resolve fixture kickoff in the UK timezone, including BST/GMT.
                from zoneinfo import ZoneInfo
                kickoff = datetime.fromisoformat(game["date"] + "T" + game["kickoff"][:5]).replace(tzinfo=ZoneInfo("Europe/London"))
                if captured.tzinfo is None or captured >= kickoff:
                    exclusions["unverified_prekickoff"] += 1
                    continue
            except (KeyError, ValueError, TypeError):
                exclusions["unknown_kickoff"] += 1
                continue
            score = settlements[ident].get("score")
            try:
                h, a = map(int, score.split("-"))
                if h < 0 or a < 0: raise ValueError()
            except (ValueError, AttributeError, TypeError):
                exclusions["invalid_result"] += 1
                continue
            scoreline = game.get("scoreline", {})
            p = scoreline.get("markets", {}).get("under35")
            if p is None:
                over = scoreline.get("markets", {}).get("over35")
                p = 1 - over if isinstance(over, (int, float)) else None
            if not isinstance(p, (float, int)) or not 0 <= p <= 1:
                exclusions["missing_probability"] += 1
                continue
            outcome = int(h + a <= 3)
            # Quoted bookmaker prices are not inferred from market averages.
            prices = []
            for c in edge_by_id.get(ident, {}).get("comparisons", []):
                if c.get("market") == "Over/Under 3.5" and c.get("selection") == "Under 3.5":
                    prices.append(c)
            rows.append({"fixture": ident, "division": game.get("division"),
                         "p": float(p), "won": outcome, "brier": (p-outcome)**2,
                         "calibrated": scoreline.get("calibrated") is True,
                         "bookmakerComparisons": prices})
    def metrics(items):
        n = len(items)
        return {"n": n, "hits": sum(x["won"] for x in items),
                "hitRate": round(sum(x["won"] for x in items)/n, 4) if n else None,
                "meanPredicted": round(sum(x["p"] for x in items)/n, 4) if n else None,
                "brier": round(sum(x["brier"] for x in items)/n, 5) if n else None,
                "pricedFixtures": sum(bool(x["bookmakerComparisons"]) for x in items)}
    by_league = {div: metrics([r for r in rows if r["division"] == div])
                 for div in ("E0", "E1", "E2", "E3", "EC")}
    bands = {str(round(t*100)): metrics([r for r in rows if r["p"] >= t]) for t in THRESHOLDS}
    # Research odds must not be converted into realized ROI unless provenance,
    # licence, timestamps, and complete market matching are independently verified.
    return {"study": "UNDER_3_5_PROSPECTIVE_AUDIT", "model": "independent-scoreline-only",
            "status": "research_not_verified_edge", "overall": metrics(rows),
            "byLeague": by_league, "minimumProbabilityThresholds": bands,
            "exclusions": dict(exclusions),
            "edgeFinder": {"verifiedResearchEdges": None, "realizedROI": None,
                           "reason": "No calibrated probability and independently verified executable pre-kickoff quote lineage established by this audit"},
            "warnings": ["Observed hit rate is not betting ROI.",
                         "Raw independent scoreline probabilities are uncalibrated; do not label research edges.",
                         "No historical odds or predictions reconstructed.",
                         "B3.1 official qualifiers and frozen forecasts unchanged."]}

def main():
    result = report()
    out = DATA / "under35-research.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(out), "overall": result["overall"], "status": result["status"]}))

if __name__ == "__main__":
    main()
