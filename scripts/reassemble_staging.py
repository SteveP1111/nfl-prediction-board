#!/usr/bin/env python3
"""Reassemble readable multipart staging or correction patches before publication."""
from __future__ import annotations

import base64
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "staging"
READY = STAGING / "READY"
MANIFEST = ROOT / "data" / "manifest.json"
PART_RE = re.compile(r"snapshot-(\d{3})-part-(\d{3})\.json")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_published_snapshot(snapshot_id: str) -> dict:
    manifest = load(MANIFEST)
    entries = manifest.get("history", {}).get("snapshots", [])
    match = next((e for e in entries if e.get("id") == snapshot_id), None)
    if not match:
        raise SystemExit(f"Publication refused: base snapshot {snapshot_id} not found")
    path = ROOT / match["path"]
    try:
        raw = gzip.decompress(base64.b64decode(path.read_text(encoding="ascii"), validate=True))
        snapshot = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise SystemExit(f"Publication refused: cannot reconstruct base snapshot: {exc}")
    return snapshot


def main() -> None:
    ready = load(READY)
    names = ready.get("snapshot_parts")
    if not isinstance(names, list) or not names:
        return
    if all(re.fullmatch(r"snapshot-[0-9]{3}\.json", n or "") for n in names):
        return
    if not all(PART_RE.fullmatch(n or "") for n in names):
        raise SystemExit("Publication refused: invalid multipart staging filename")

    groups = {}
    for name in names:
        m = PART_RE.fullmatch(name)
        doc = load(STAGING / name)
        if not isinstance(doc, dict):
            raise SystemExit(f"Publication refused: {name} is not an object")
        groups.setdefault(m.group(1), []).append((int(m.group(2)), name, doc))

    rebuilt_names = []
    for group, items in sorted(groups.items()):
        items.sort()
        if [x[0] for x in items] != list(range(1, len(items) + 1)):
            raise SystemExit(f"Publication refused: multipart sequence gap for snapshot-{group}")
        declared = {x[2].get("parts") for x in items}
        if declared != {len(items)}:
            raise SystemExit(f"Publication refused: inconsistent part count for snapshot-{group}")

        patch_mode = all(x[2].get("mode") == "patch" for x in items)
        if patch_mode:
            bases = {x[2].get("base_snapshot_id") for x in items}
            new_ids = {x[2].get("snapshot_id") for x in items}
            if len(bases) != 1 or None in bases or len(new_ids) != 1 or None in new_ids:
                raise SystemExit(f"Publication refused: inconsistent patch ids for snapshot-{group}")
            snapshot = load_published_snapshot(next(iter(bases)))
            updates = items[0][2].get("updates", {})
            if not isinstance(updates, dict):
                raise SystemExit("Publication refused: patch updates must be an object")
            snapshot.update(updates)
            games = []
            for _, _, doc in items:
                chunk = doc.get("games", [])
                if not isinstance(chunk, list):
                    raise SystemExit("Publication refused: patch games must be an array")
                games.extend(chunk)
            if len(games) != 16 or len({g.get("game_id") for g in games}) != 16:
                raise SystemExit("Publication refused: correction patch must provide all 16 unique games")
            snapshot["games"] = games
            if snapshot.get("id") != next(iter(new_ids)):
                raise SystemExit("Publication refused: corrected snapshot id mismatch")
        else:
            ids = {x[2].get("snapshot_id") for x in items}
            if len(ids) != 1 or None in ids:
                raise SystemExit(f"Publication refused: inconsistent multipart snapshot ids for snapshot-{group}")
            snapshot = items[0][2].get("snapshot")
            if not isinstance(snapshot, dict):
                raise SystemExit("Publication refused: first multipart file missing snapshot metadata")
            snapshot = dict(snapshot)
            props = []
            for _, _, doc in items:
                chunk = doc.get("props", [])
                if not isinstance(chunk, list):
                    raise SystemExit("Publication refused: multipart props must be an array")
                props.extend(chunk)
            snapshot["props"] = props

        out_name = f"snapshot-{group}.json"
        (STAGING / out_name).write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        rebuilt_names.append(out_name)

    for name in names:
        (STAGING / name).unlink(missing_ok=True)
    ready["snapshot_parts"] = rebuilt_names
    READY.write_text(json.dumps(ready, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Reassembled {len(names)} readable staging parts into {len(rebuilt_names)} snapshot file(s)")


if __name__ == "__main__":
    main()
