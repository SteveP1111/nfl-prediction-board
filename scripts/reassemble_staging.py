#!/usr/bin/env python3
"""Reassemble readable multipart staging files before publication."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "staging"
READY = STAGING / "READY"
PART_RE = re.compile(r"snapshot-(\d{3})-part-(\d{3})\.json")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
        group = m.group(1)
        doc = load(STAGING / name)
        if not isinstance(doc, dict):
            raise SystemExit(f"Publication refused: {name} is not an object")
        groups.setdefault(group, []).append((int(m.group(2)), name, doc))

    rebuilt_names = []
    for group, items in sorted(groups.items()):
        items.sort()
        expected = list(range(1, len(items) + 1))
        if [i[0] for i in items] != expected:
            raise SystemExit(f"Publication refused: multipart sequence gap for snapshot-{group}")
        declared = {i[2].get("parts") for i in items}
        ids = {i[2].get("snapshot_id") for i in items}
        if declared != {len(items)} or len(ids) != 1 or None in ids:
            raise SystemExit(f"Publication refused: inconsistent multipart metadata for snapshot-{group}")

        snapshot = None
        props = []
        for index, name, doc in items:
            if index == 1:
                snapshot = doc.get("snapshot")
                if not isinstance(snapshot, dict):
                    raise SystemExit(f"Publication refused: {name} missing snapshot metadata")
                snapshot = dict(snapshot)
            elif doc.get("snapshot") not in (None, {}):
                raise SystemExit(f"Publication refused: only first part may contain snapshot metadata")
            chunk = doc.get("props", [])
            if not isinstance(chunk, list):
                raise SystemExit(f"Publication refused: {name}.props must be an array")
            props.extend(chunk)

        if snapshot.get("id") != next(iter(ids)):
            raise SystemExit(f"Publication refused: snapshot id mismatch for snapshot-{group}")
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
