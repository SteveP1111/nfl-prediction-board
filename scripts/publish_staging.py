#!/usr/bin/env python3
"""Validate staged public board data and publish deterministic hosted chunks."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "staging"
READY_PATH = STAGING / "READY"
MANIFEST_PATH = ROOT / "data" / "manifest.json"
CHUNK_SIZE = 7_400
NFL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}
FINAL_RESULTS = {"Correct", "Miss", "Push"}


def fail(message: str) -> None:
    raise SystemExit(f"Publication refused: {message}")


def load_json(path: Path):
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda value: fail(f"non-finite JSON value {value} in {path}"),
        )
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid JSON from {path}: {exc}")


def finite_number(value, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label} must be numeric")
    if not math.isfinite(value):
        fail(f"{label} must be finite")


def valid_rating(value, label: str) -> None:
    if isinstance(value, str) and value.strip():
        return
    finite_number(value, label)


def require_outcome(outcomes: dict, key: str, label: str) -> None:
    outcome = outcomes.get(key)
    if not isinstance(outcome, dict):
        fail(f"{label} is missing outcome {key}")
    if outcome.get("result") not in FINAL_RESULTS:
        fail(f"{label} outcome {key} must be Correct, Miss or Push")
    actual = outcome.get("actual")
    if actual is None or actual == "":
        fail(f"{label} outcome {key} is missing its actual result")
    if isinstance(actual, float) and not math.isfinite(actual):
        fail(f"{label} outcome {key} has a non-finite actual result")


def validate_completed_game_grading(snapshot: dict, prefix: str) -> None:
    """Refuse publication when any marked-final game has partial grading."""
    outcomes = snapshot.get("outcomes", {})
    if not isinstance(outcomes, dict):
        fail(f"{prefix}.outcomes must be an object")
    games = snapshot["games"]
    completed = {
        game["game_id"]
        for game in games
        if f"win:{game['game_id']}" in outcomes
        or f"spread:{game['game_id']}" in outcomes
        or f"total:{game['game_id']}" in outcomes
    }
    for game in games:
        game_id = game["game_id"]
        if game_id not in completed:
            continue
        label = f"{prefix} completed game {game_id}"
        require_outcome(outcomes, f"win:{game_id}", label)
        if game.get("spread_side") and game.get("spread_line") is not None:
            require_outcome(outcomes, f"spread:{game_id}", label)
        if game.get("total_side") and game.get("total_line") is not None:
            require_outcome(outcomes, f"total:{game_id}", label)
        for prop in snapshot["props"]:
            if prop.get("game_id") != game_id:
                continue
            if not prop.get("pick_side") or prop.get("line") is None:
                continue
            player = prop.get("player_id") or prop.get("name")
            require_outcome(outcomes, f"prop:{game_id}:{player}:{prop.get('type')}", label)
        for td in snapshot["tds"]:
            if td.get("game_id") != game_id:
                continue
            player = td.get("player_id") or td.get("name")
            require_outcome(outcomes, f"td:{game_id}:{player}", label)


def validate_payload(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        fail("public.json must contain a JSON object")
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        fail("payload must contain at least one snapshot")

    snapshot_ids: set[str] = set()
    for index, snapshot in enumerate(snapshots):
        prefix = f"snapshots[{index}]"
        if not isinstance(snapshot, dict):
            fail(f"{prefix} must be an object")
        snapshot_id = snapshot.get("id")
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            fail(f"{prefix}.id is missing")
        if snapshot_id in snapshot_ids:
            fail(f"duplicate snapshot id {snapshot_id}")
        snapshot_ids.add(snapshot_id)

        games = snapshot.get("games")
        props = snapshot.get("props")
        tds = snapshot.get("tds")
        if not isinstance(games, list) or len(games) != 16:
            fail(f"{prefix} must contain exactly 16 games")
        if not isinstance(props, list) or len(props) < 50:
            fail(f"{prefix} must contain at least 50 published props")
        if not isinstance(tds, list) or len(tds) < 25:
            fail(f"{prefix} must contain at least 25 touchdown candidates")

        game_ids: set[str] = set()
        scheduled_teams: list[str] = []
        for game_index, game in enumerate(games):
            label = f"{prefix}.games[{game_index}]"
            if not isinstance(game, dict):
                fail(f"{label} must be an object")
            game_id = game.get("game_id")
            if not isinstance(game_id, str) or not game_id:
                fail(f"{label}.game_id is missing")
            if game_id in game_ids:
                fail(f"duplicate game id {game_id} in {snapshot_id}")
            game_ids.add(game_id)
            for side in ("away", "home"):
                team = game.get(side)
                if team not in NFL_TEAMS:
                    fail(f"{label}.{side} has invalid team id {team!r}")
                scheduled_teams.append(team)
            for field in ("away_projection", "home_projection", "total_projection"):
                finite_number(game.get(field), f"{label}.{field}")
            for field in ("winner_rating", "spread_rating", "total_rating"):
                valid_rating(game.get(field), f"{label}.{field}")
        if len(set(scheduled_teams)) != 32:
            fail(f"{prefix} must schedule each of the 32 teams exactly once")

        for collection_name, records in (("props", props), ("tds", tds)):
            for record_index, record in enumerate(records):
                label = f"{prefix}.{collection_name}[{record_index}]"
                if not isinstance(record, dict):
                    fail(f"{label} must be an object")
                if record.get("team") not in NFL_TEAMS:
                    fail(f"{label}.team has invalid team id {record.get('team')!r}")
                if record.get("game_id") not in game_ids:
                    fail(f"{label}.game_id does not match a game in its snapshot")
                if collection_name == "props":
                    for field in ("projection", "rating"):
                        finite_number(record.get(field), f"{label}.{field}")
                else:
                    for field in ("prob", "rating"):
                        finite_number(record.get(field), f"{label}.{field}")
        validate_completed_game_grading(snapshot, prefix)
    return snapshots


def main() -> None:
    ready = load_json(READY_PATH)
    if not isinstance(ready, dict):
        fail("READY must contain a JSON object")
    version = ready.get("version")
    expected_sha = ready.get("payload_sha256")
    model_version = ready.get("model_version")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{5,79}", version):
        fail("READY.version is invalid")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        fail("READY.payload_sha256 must be a lowercase SHA256")
    if not isinstance(model_version, str) or not model_version.strip():
        fail("READY.model_version is missing")

    payload_path = STAGING / "public.json"
    try:
        raw = payload_path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {payload_path}: {exc}")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha:
        fail(f"staged SHA256 {actual_sha} does not match READY {expected_sha}")

    payload = load_json(payload_path)
    snapshots = validate_payload(payload)

    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    encoded = base64.b64encode(compressed).decode("ascii")
    parts = [encoded[i : i + CHUNK_SIZE] for i in range(0, len(encoded), CHUNK_SIZE)]
    if not parts or any(len(part) > 7_500 for part in parts):
        fail("chunk generation produced an invalid part size")

    output_dir = ROOT / "data" / f"live-{version}"
    if output_dir.exists():
        fail(f"output directory already exists: {output_dir.relative_to(ROOT)}")
    output_dir.mkdir(parents=True)
    part_paths: list[str] = []
    for index, part in enumerate(parts, start=1):
        path = output_dir / f"part-{index:03d}.txt"
        path.write_text(part, encoding="ascii")
        part_paths.append(path.relative_to(ROOT).as_posix())

    try:
        rebuilt_b64 = "".join((ROOT / path).read_text(encoding="ascii") for path in part_paths)
        rebuilt = gzip.decompress(base64.b64decode(rebuilt_b64, validate=True))
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        fail(f"read-back reconstruction failed: {exc}")
    if rebuilt != raw or hashlib.sha256(rebuilt).hexdigest() != expected_sha:
        shutil.rmtree(output_dir, ignore_errors=True)
        fail("read-back payload or SHA256 mismatch")

    manifest = load_json(MANIFEST_PATH)
    if not isinstance(manifest, dict):
        fail("manifest.json must contain an object")
    manifest["schema_version"] = 1
    manifest["model_version"] = model_version
    manifest["history"] = {
        "encoding": "base64+gzip",
        "parts": part_paths,
        "sha256": expected_sha,
        "uncompressed_bytes": len(raw),
        "snapshots": len(snapshots),
    }
    manifest["published_version"] = version

    temp_manifest = MANIFEST_PATH.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp_manifest, MANIFEST_PATH)
    print(
        f"Validated and published {len(snapshots)} snapshots as {len(parts)} parts; "
        f"SHA256 {expected_sha}"
    )


if __name__ == "__main__":
    main()
