#!/usr/bin/env python3
"""Validate staged board data and publish one deterministic file per snapshot."""

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
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
NFL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}
FINAL_RESULTS = {"Correct", "Miss", "Push"}
DISPLAY_RESULTS = FINAL_RESULTS | {"Final"}


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


def require_outcome(outcomes: dict, key: str, label: str, allowed=FINAL_RESULTS) -> None:
    outcome = outcomes.get(key)
    if not isinstance(outcome, dict):
        fail(f"{label} is missing outcome {key}")
    if outcome.get("result") not in allowed:
        fail(f"{label} outcome {key} has an invalid settlement state")
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
            player = prop.get("player_id") or prop.get("name")
            if prop.get("type") == "tackles":
                require_outcome(
                    outcomes,
                    f"prop:{game_id}:{player}:tackles",
                    label,
                    DISPLAY_RESULTS,
                )
                continue
            if not prop.get("pick_side") or prop.get("line") is None:
                continue
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

        tackle_counts = {team: 0 for team in NFL_TEAMS}
        for prop_index, prop in enumerate(props):
            if prop.get("type") != "tackles":
                continue
            label = f"{prefix}.props[{prop_index}]"
            if prop.get("label") != "Tackles + assists":
                fail(f"{label} must use the Tackles + assists label")
            tackle_counts[prop["team"]] += 1
        thin_teams = sorted(team for team, count in tackle_counts.items() if count < 8)
        if thin_teams:
            fail(
                f"{prefix} must contain at least eight tackle projections for every team; "
                f"missing/thin coverage: {', '.join(thin_teams)}"
            )
        validate_completed_game_grading(snapshot, prefix)
    return snapshots


def load_staged_payload(ready: dict) -> tuple[dict, bytes]:
    """Load either the legacy single file or safe per-snapshot staging files."""
    payload_path = STAGING / "public.json"
    snapshot_parts = ready.get("snapshot_parts")
    if snapshot_parts is None:
        try:
            raw = payload_path.read_bytes()
        except OSError as exc:
            fail(f"cannot read {payload_path}: {exc}")
        return load_json(payload_path), raw

    if not isinstance(snapshot_parts, list) or not snapshot_parts:
        fail("READY.snapshot_parts must be a non-empty list")
    payload = load_json(payload_path)
    if not isinstance(payload, dict) or payload.get("snapshots") not in (None, []):
        fail("split staging public.json must contain metadata only")
    snapshots = []
    seen_parts: set[str] = set()
    for part in snapshot_parts:
        if not isinstance(part, str) or not re.fullmatch(r"snapshot-[0-9]{3}\.json", part):
            fail(f"invalid snapshot staging part {part!r}")
        if part in seen_parts:
            fail(f"duplicate snapshot staging part {part}")
        seen_parts.add(part)
        snapshot = load_json(STAGING / part)
        if not isinstance(snapshot, dict):
            fail(f"snapshot staging part {part} must contain an object")
        snapshots.append(snapshot)
    payload["snapshots"] = snapshots
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return payload, raw


def publish_snapshot(snapshot: dict) -> dict:
    """Write and read back one content-addressed compressed snapshot."""
    raw = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    snapshot_sha = hashlib.sha256(raw).hexdigest()
    encoded = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode("ascii")
    path = SNAPSHOT_DIR / f"{snapshot_sha}.txt"
    if path.exists():
        if path.read_text(encoding="ascii") != encoded:
            fail(f"existing snapshot file does not match its content hash: {path.name}")
    else:
        path.write_text(encoded, encoding="ascii")

    try:
        rebuilt = gzip.decompress(base64.b64decode(path.read_text(encoding="ascii"), validate=True))
    except Exception as exc:
        fail(f"snapshot read-back reconstruction failed for {snapshot['id']}: {exc}")
    if rebuilt != raw or hashlib.sha256(rebuilt).hexdigest() != snapshot_sha:
        fail(f"snapshot read-back checksum mismatch for {snapshot['id']}")

    return {
        "id": snapshot["id"],
        "season": snapshot["season"],
        "week": snapshot["week"],
        "slot": snapshot["slot"],
        "capturedAt": snapshot["capturedAt"],
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": snapshot_sha,
        "uncompressed_bytes": len(raw),
        "encoded_bytes": len(encoded),
        "games": len(snapshot["games"]),
        "props": len(snapshot["props"]),
        "tds": len(snapshot["tds"]),
    }


def main() -> None:
    ready = load_json(READY_PATH)
    if not isinstance(ready, dict):
        fail("READY must contain a JSON object")
    version = ready.get("version")
    expected_sha = ready.get("payload_sha256")
    model_version = ready.get("model_version")
    mode = ready.get("mode", "replace_all")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{5,79}", version):
        fail("READY.version is invalid")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        fail("READY.payload_sha256 must be a lowercase SHA256")
    if not isinstance(model_version, str) or not model_version.strip():
        fail("READY.model_version is missing")
    if mode not in {"replace_all", "upsert"}:
        fail("READY.mode must be replace_all or upsert")

    payload, raw = load_staged_payload(ready)
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha:
        fail(f"staged SHA256 {actual_sha} does not match READY {expected_sha}")

    snapshots = validate_payload(payload)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    staged_catalogue = [publish_snapshot(snapshot) for snapshot in snapshots]
    manifest = load_json(MANIFEST_PATH)
    if not isinstance(manifest, dict):
        fail("manifest.json must contain an object")
    existing_catalogue = manifest.get("history", {}).get("snapshots", [])
    if mode == "upsert":
        if not isinstance(existing_catalogue, list):
            fail("upsert requires an existing per-snapshot catalogue")
        catalogue_by_id = {entry["id"]: entry for entry in existing_catalogue}
        catalogue_by_id.update({entry["id"]: entry for entry in staged_catalogue})
        catalogue = sorted(catalogue_by_id.values(), key=lambda entry: entry["capturedAt"])
    else:
        catalogue = staged_catalogue
    referenced = {Path(entry["path"]).name for entry in catalogue}
    for path in SNAPSHOT_DIR.glob("*.txt"):
        if path.name not in referenced:
            path.unlink()

    manifest["schema_version"] = 2
    manifest["model_version"] = model_version
    manifest["history"] = {
        "encoding": "per-snapshot-base64+gzip",
        "last_staging_sha256": expected_sha,
        "snapshot_count": len(catalogue),
        "snapshots": catalogue,
    }
    manifest["weekly_reviews"] = payload.get("weekly_reviews", [])
    manifest["published_version"] = version

    temp_manifest = MANIFEST_PATH.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp_manifest, MANIFEST_PATH)

    # These cumulative legacy directories are no longer referenced. Removing
    # them in the same commit as the manifest switch keeps Pages compact.
    for legacy_dir in (ROOT / "data").glob("live-*"):
        if legacy_dir.is_dir():
            shutil.rmtree(legacy_dir)
    for part in ready.get("snapshot_parts", []):
        (STAGING / part).unlink(missing_ok=True)
    print(
        f"Validated {len(snapshots)} staged snapshots and published {len(catalogue)} total; "
        f"SHA256 {expected_sha}"
    )


if __name__ == "__main__":
    main()
