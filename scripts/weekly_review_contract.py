from __future__ import annotations

FINAL_RESULTS = {"Correct", "Miss", "Push"}


def _require_outcome(outcomes: dict, key: str, label: str) -> None:
    outcome = outcomes.get(key)
    if not isinstance(outcome, dict):
        raise ValueError(f"{label} is missing {key}")
    if outcome.get("result") not in FINAL_RESULTS:
        raise ValueError(f"{label} has invalid result for {key}")
    if outcome.get("actual") in (None, ""):
        raise ValueError(f"{label} is missing actual value for {key}")


def _grade_counts(outcomes: dict, prefix: str, game_ids: set[str]) -> tuple[int, int, int]:
    values = [outcomes[f"{prefix}:{gid}"]["result"] for gid in game_ids]
    return (
        sum(v == "Correct" for v in values),
        sum(v == "Miss" for v in values),
        sum(v == "Push" for v in values),
    )


def is_final_review(review: dict) -> bool:
    return (
        review.get("review_scope") == "game_lines_final"
        or str(review.get("status") or "").strip().lower() == "final"
    )


def review_identity(review: dict) -> tuple:
    return (
        review.get("season"),
        review.get("week"),
        review.get("type"),
        review.get("review_scope"),
        review.get("status"),
        review.get("as_of"),
    )


def normalise_weekly_review(review: dict) -> dict:
    """Make final weekly reviews self-sufficient for historical board grading."""
    if not isinstance(review, dict):
        raise ValueError("weekly review must be an object")
    out = dict(review)
    if not is_final_review(out):
        return out

    label = f"final review {out.get('season')} W{out.get('week')}"
    outcomes = dict(out.get("game_outcomes") or {})
    games = out.get("games")

    if isinstance(games, list) and games:
        if len(games) != 16:
            raise ValueError(f"{label} must contain exactly 16 graded games")
        seen: set[str] = set()
        for game in games:
            if not isinstance(game, dict):
                raise ValueError(f"{label} contains a non-object game")
            gid = str(game.get("game_id") or "")
            if not gid or gid in seen:
                raise ValueError(f"{label} has a missing or duplicate game_id")
            seen.add(gid)
            final = game.get("final")
            actual_total = game.get("actual_total")
            if final in (None, "") or actual_total in (None, ""):
                raise ValueError(f"{label} game {gid} is missing final score data")
            for market, field, actual in (
                ("win", "winner_result", final),
                ("spread", "spread_result", final),
                ("total", "total_result", f"{actual_total} points"),
            ):
                result = game.get(field)
                if result not in FINAL_RESULTS:
                    raise ValueError(f"{label} game {gid} has invalid {field}")
                outcomes[f"{market}:{gid}"] = {"result": result, "actual": actual}

    prefixes = ("win", "spread", "total")
    ids_by_prefix: dict[str, set[str]] = {}
    for prefix in prefixes:
        ids = {
            key.split(":", 1)[1]
            for key in outcomes
            if isinstance(key, str) and key.startswith(prefix + ":")
        }
        if len(ids) != 16:
            raise ValueError(f"{label} must contain 16 {prefix} outcomes; found {len(ids)}")
        ids_by_prefix[prefix] = ids
        for gid in ids:
            _require_outcome(outcomes, f"{prefix}:{gid}", label)

    if not (ids_by_prefix["win"] == ids_by_prefix["spread"] == ids_by_prefix["total"]):
        raise ValueError(f"{label} winner/spread/total game sets do not match")

    metrics = out.get("authoritative_metrics") or {}
    game_metrics = metrics.get("games") if isinstance(metrics.get("games"), dict) else metrics
    game_ids = ids_by_prefix["win"]
    for market, prefix in (("winner", "win"), ("spread", "spread"), ("total", "total")):
        metric = game_metrics.get(market) if isinstance(game_metrics, dict) else None
        if not isinstance(metric, dict):
            continue
        correct, miss, push = _grade_counts(outcomes, prefix, game_ids)
        if metric.get("correct") not in (None, correct):
            raise ValueError(f"{label} {market} correct count disagrees with outcomes")
        if metric.get("miss") not in (None, miss):
            raise ValueError(f"{label} {market} miss count disagrees with outcomes")
        if metric.get("push") not in (None, push):
            raise ValueError(f"{label} {market} push count disagrees with outcomes")
        decisions = correct + miss
        if metric.get("decisions") not in (None, decisions):
            raise ValueError(f"{label} {market} decision count disagrees with outcomes")

    out["game_outcomes"] = outcomes
    return out


def normalise_weekly_reviews(reviews: list[dict]) -> list[dict]:
    if not isinstance(reviews, list):
        raise ValueError("weekly_reviews must be an array")
    return [normalise_weekly_review(item) for item in reviews]
