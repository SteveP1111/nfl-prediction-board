#!/usr/bin/env python3
"""Copy append-only grading from the private history into the public subset."""

import json
import sys
from pathlib import Path


def main(private_path: Path, public_path: Path, output_path: Path) -> None:
    private = json.loads(private_path.read_text(encoding="utf-8"))
    public = json.loads(public_path.read_text(encoding="utf-8"))
    source = {snapshot["id"]: snapshot for snapshot in private["snapshots"]}
    for snapshot in public["snapshots"]:
        latest = source[snapshot["id"]]
        snapshot["outcomes"] = latest.get("outcomes", {})
        snapshot["gradedAt"] = latest.get("gradedAt")
        # The general public board remains curated, but defensive tackle coverage
        # must be complete so every game/team can be inspected. Replace any
        # previously selected tackle rows with the full frozen tackle pool.
        public_props = [
            prop for prop in snapshot.get("props", [])
            if prop.get("type") != "tackles"
        ]
        tackle_props = [
            prop for prop in latest.get("props", [])
            if prop.get("type") == "tackles"
        ]
        snapshot["props"] = public_props + tackle_props
        # Publish the complete TD pool so rating and position filters are real.
        # QB entries represent only the QB's own rushing/receiving score.
        snapshot["tds"] = latest.get("tds", [])
    output_path.write_text(json.dumps(public, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: update_public_results.py PRIVATE PUBLIC OUTPUT")
    main(*(Path(arg) for arg in sys.argv[1:]))
