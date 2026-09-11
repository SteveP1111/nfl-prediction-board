#!/usr/bin/env python3
"""Pre-publication audit for the full private NFL prediction history."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


NFL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}
FINAL_RESULTS = {"Correct", "Miss", "Push"}


def fail(message: str) -> None:
    raise SystemExit(f"Refresh audit failed: {message}")


def require_outcome(outcomes: dict, key: str, label: str) -> None:
    outcome = outcomes.get(key)
    if not isinstance(outcome, dict):
        fail(f"{label} is missing outcome {key}")
    if outcome.get("result") not in FINAL_RESULTS:
        fail(f"{label} outcome {key} is not final")
    actual = outcome.get("actual")
    if actual is None or actual == "":
        fail(f"{label} outcome {key} is missing its actual value")
    if isinstance(actual, float) and not math.isfinite(actual):
        fail(f"{label} outcome {key} has a non-finite actual value")


def audit(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        fail("history has no snapshots")

    for snapshot in snapshots:
        snapshot_id = snapshot.get("id", "unknown snapshot")
        games = snapshot.get("games", [])
        props = snapshot.get("props", [])
        tds = snapshot.get("tds", [])
        outcomes = snapshot.get("outcomes", {})
        if len(games) != 16:
            fail(f"{snapshot_id} does not contain 16 games")
        scheduled = {team for game in games for team in (game.get("away"), game.get("home"))}
        if scheduled != NFL_TEAMS:
            fail(f"{snapshot_id} does not schedule all 32 teams exactly once")

        tackles = [prop for prop in props if prop.get("type") == "tackles"]
        tackle_teams = {prop.get("team") for prop in tackles}
        missing = sorted(NFL_TEAMS - tackle_teams)
        if missing:
            fail(f"{snapshot_id} is missing Tackles + assists projections for {', '.join(missing)}")
        for prop in tackles:
            if prop.get("label") != "Tackles + assists":
                fail(f"{snapshot_id} has an incorrectly labelled tackle projection")
            value = prop.get("projection")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                fail(f"{snapshot_id} has a non-finite Tackles + assists projection")

        completed = {
            game["game_id"] for game in games
            if any(f"{market}:{game['game_id']}" in outcomes for market in ("win", "spread", "total"))
        }
        for game in games:
            game_id = game["game_id"]
            if game_id not in completed:
                continue
            label = f"{snapshot_id} completed game {game_id}"
            require_outcome(outcomes, f"win:{game_id}", label)
            if game.get("spread_side") and game.get("spread_line") is not None:
                require_outcome(outcomes, f"spread:{game_id}", label)
            if game.get("total_side") and game.get("total_line") is not None:
                require_outcome(outcomes, f"total:{game_id}", label)
            for prop in props:
                if prop.get("game_id") == game_id and prop.get("pick_side") and prop.get("line") is not None:
                    player = prop.get("player_id") or prop.get("name")
                    require_outcome(outcomes, f"prop:{game_id}:{player}:{prop.get('type')}", label)
            for td in tds:
                if td.get("game_id") == game_id:
                    player = td.get("player_id") or td.get("name")
                    require_outcome(outcomes, f"td:{game_id}:{player}", label)

        print(
            f"{snapshot_id}: PASS | games=16 | tackles+assists={len(tackles)} "
            f"| tackle teams={len(tackle_teams)} | completed games={len(completed)}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_private_refresh.py NFL_Prediction_History.json")
    audit(Path(sys.argv[1]))
