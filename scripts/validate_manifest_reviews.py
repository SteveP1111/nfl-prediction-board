#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from weekly_review_contract import is_final_review, normalise_weekly_reviews

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reviews = manifest.get("weekly_reviews", [])
    normalised = normalise_weekly_reviews(reviews)
    final_reviews = [r for r in normalised if is_final_review(r)]
    history = manifest.get("history", {}).get("snapshots", [])
    available = {(x.get("season"), x.get("week")) for x in history}
    for review in final_reviews:
        key = (review.get("season"), review.get("week"))
        if key not in available:
            raise SystemExit(f"Final weekly review {key} has no published historical snapshot")
    print(f"Validated {len(reviews)} weekly reviews including {len(final_reviews)} final game-line review(s)")


if __name__ == "__main__":
    main()
