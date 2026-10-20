#!/usr/bin/env python3
"""Optional, licence-gated bookmaker odds comparison for the standalone football board.

Uses UK Odds API's official authenticated interface. Does not scrape bookmaker sites
or use odds as model inputs. Never overwrites a pre-kickoff odds snapshot.
"""
from __future__ import annotations
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from edge_finder import MARKETS, assess_edge, no_vig
from refresh import canon

DATA = Path(__file__).resolve().parents[1] / "data"
SNAPS = DATA / "edge-snapshots"
TZ = ZoneInfo("Europe/London")
BASE = "https://api.ukoddsapi.com"
MAX_EVENTS_PER_DAY = 6  # <= 186 metered core-price calls in a 31-day month
SOURCE = "UK Odds API"
STATUS_PATH = DATA / "edge-status.json"

def normalized(text):
    return " ".join(re.sub(r"[^a-z0-9.]+", " ", str(text or "").lower()).split())

def market_name(market):
    """Fail closed rather than inadvertently matching half-time or team-only lines."""
    name = normalized(market.get("market_name") or market.get("name"))
    desc = normalized(market.get("description"))
    if any(s in name for s in ("half", "corner", "card", "booking", "team total",
                                "team goals", "home goals", "away goals",
                                "handicap", "odd even", "correct score", "asian")):
        return None
    if name in {"1x2", "match winner", "match result", "full time result",
                "fulltime result", "full time 1x2"}:
        return "1X2"
    if name in {"btts", "both teams to score", "both teams score",
                "both teams to score match"}:
        return "BTTS"
    if name in {"total goals", "total goals over under", "over under",
                "over under 2.5", "total goals over under 2.5"}:
        if "2.5" in name or "2.5" in desc:
            return "Over/Under 2.5"
        if "3.5" in name or "3.5" in desc:
            return "Over/Under 3.5"
        # Generic total-goals market may contain several lines. Each selection
        # must be explicitly line-labelled and is grouped separately below.
        return "TOTALS"
    if name in {"over under 3.5", "total goals over under 3.5"}:
        return "Over/Under 3.5"
    return None

def selection_name(market, text, home, away):
    value = normalized(text)
    if market == "1X2":
        if value in {"1", "home", normalized(home), "home team"}: return "Home"
        if value in {"x", "draw", "tie"}: return "Draw"
        if value in {"2", "away", normalized(away), "away team"}: return "Away"
    if market == "BTTS":
        if value in {"yes", "y"}: return "Yes"
        if value in {"no", "n"}: return "No"
    if market.startswith("Over/Under "):
        line = market.split()[-1]
        if value in {"over " + line, "o " + line}: return "Over " + line
        if value in {"under " + line, "u " + line}: return "Under " + line
    return None

def same_book_groups(payload, home, away):
    """Extract only complete identical lines per bookmaker; never merge books."""
    groups = {}
    for market in payload.get("markets", []):
        kind = market_name(market)
        if not kind: continue
        for selection in market.get("selections", []):
            raw = normalized(selection.get("selection_name"))
            actual = kind
            if kind == "TOTALS":
                if raw in {"over 2.5", "under 2.5"}: actual = "Over/Under 2.5"
                elif raw in {"over 3.5", "under 3.5"}: actual = "Over/Under 3.5"
                else: continue
            outcome = selection_name(actual, selection.get("selection_name"), home, away)
            code = str(selection.get("bookmaker_code") or "").strip()
            if not outcome or not code: continue
            try: price = float(selection["odds"])
            except (TypeError, KeyError, ValueError): continue
            if not 1.001 < price < 1000: continue
            group = groups.setdefault((actual, code), {})
            if outcome in group and group[outcome] != price:
                # Ambiguous duplicate market: reject instead of cherry-picking.
                group["__invalid__"] = True
            group[outcome] = price
    clean = []
    for (kind, code), prices in sorted(groups.items()):
        if "__invalid__" in prices or set(prices) != set(MARKETS[kind]): continue
        try: market_view = no_vig(prices, kind)
        except (ValueError, TypeError, ZeroDivisionError): continue
        if not -0.05 <= market_view["overround"] <= 0.50: continue
        clean.append((kind, code, prices))
    return clean

def probabilities(game, kind):
    markets = game.get("scoreline", {}).get("markets", {})
    if kind == "1X2":
        keys = {"Home": "home_win", "Draw": "draw", "Away": "away_win"}
    elif kind == "BTTS":
        keys = {"Yes": "btts", "No": "no_btts"}
    elif kind == "Over/Under 2.5":
        keys = {"Over 2.5": "over25", "Under 2.5": "under25"}
    else:
        keys = {"Over 3.5": "over35"}
    if not all(isinstance(markets.get(k), (int, float)) and 0 <= markets[k] <= 1 for k in keys.values()):
        return {}
    result = {selection: float(markets[key]) for selection, key in keys.items()}
    if kind == "Over/Under 3.5": result["Under 3.5"] = 1.0 - result["Over 3.5"]
    return result if abs(sum(result.values()) - 1) < .002 else {}

def eligible_kickoff(game, now):
    value = str(game.get("kickoff", ""))
    if not re.fullmatch(r"\d\d:\d\d", value[:5]): return None
    try: at = datetime.combine(datetime.fromisoformat(game["date"]).date(),
                               time.fromisoformat(value[:5]), TZ)
    except (ValueError, KeyError): return None
    return at if at > now else None

def event_for(game, events, now):
    """Require exact team identities, date and time, and reject ambiguous events."""
    kickoff = eligible_kickoff(game, now)
    if not kickoff: return None
    possible = []
    for e in events:
        if e.get("schedule_date") != game["date"]: continue
        if canon(e.get("home_team")) != game["homeKey"]: continue
        if canon(e.get("away_team")) != game["awayKey"]: continue
        try: actual = datetime.fromisoformat(e["kickoff_utc"].replace("Z", "+00:00"))
        except (ValueError, KeyError, AttributeError): continue
        if actual.tzinfo is None or abs((actual - kickoff).total_seconds()) > 3600: continue
        if not e.get("event_id") or not str(e["event_id"]).startswith("evt_"): continue
        possible.append(e)
    return possible[0] if len(possible) == 1 else None

def request_json(path, api_key, params=None):
    url = BASE + path
    if params: url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key,
                                                "Accept": "application/json",
                                                "User-Agent": "EnglishFootballResearch/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200: raise ValueError("Unexpected odds response status")
        data = response.read(4_000_000)
    return json.loads(data.decode("utf-8"))

def export_status(value, detail, **other):
    DATA.mkdir(parents=True, exist_ok=True)
    obj = {"status": value, "detail": detail, "source": SOURCE, **other}
    STATUS_PATH.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def build_snapshot(today_snapshot, event_rows, api_key, now):
    """Called only with verified pre-kickoff scoreline snapshot and licensed public display."""
    games = [g for g in today_snapshot["games"] if eligible_kickoff(g, now)]
    by_game = []
    matched = []
    for g in games:
        e = event_for(g, event_rows, now)
        if e: matched.append((g, e))
    # Give priority to genuinely frozen B3.1 qualifiers without using their
    # scores as event probabilities or changing either model's forecasts.
    official = {}
    bridge = DATA / "b31-snapshots" / (today_snapshot["date"] + ".json")
    if bridge.exists():
        try:
            b = json.loads(bridge.read_text(encoding="utf-8"))
            if b.get("date") == today_snapshot["date"] and b.get("status") == "frozen-prekickoff":
                official = {x["id"]: x["qualifiers"] for x in b.get("fixtures", [])
                            if isinstance(x.get("qualifiers"), list) and x.get("id")}
        except (ValueError, OSError, KeyError): pass
    # Coverage is deliberately capped for the free 300-request/month plan.
    matched.sort(key=lambda pair: (
        1 if official.get(pair[0]["id"]) else 0,
        max((float(q.get("score") or 0) for q in official.get(pair[0]["id"], [])), default=0),
        max(pair[0].get("scoreline", {}).get("markets", {}).values(), default=0)), reverse=True)
    for g, e in matched[:MAX_EVENTS_PER_DAY]:
        try:
            data = request_json("/v1/football/events/" + urllib.parse.quote(e["event_id"], safe="") + "/odds",
                                api_key, {"package": "core", "odds_format": "decimal"})
        except (urllib.error.URLError, ValueError, OSError, json.JSONDecodeError) as exc:
            print("One odds event unavailable (" + type(exc).__name__ + ").", file=sys.stderr)
            continue
        kickoff = eligible_kickoff(g, now)
        if not kickoff: continue
        observed = datetime.now(TZ)
        if observed >= kickoff: continue
        stamp = data.get("captured_at")
        try:
            source_time = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if (source_time.tzinfo is None or source_time > observed or source_time >= kickoff
                    or (observed - source_time).total_seconds() > 36 * 3600):
                continue
        except (ValueError, TypeError, AttributeError): continue
        markets = []
        for kind, book, prices in same_book_groups(data, g["home"], g["away"]):
            probs = probabilities(g, kind)
            if not probs: continue
            for selection, p in probs.items():
                evidence = {"teamIdentityVerified": True, "marketMatched": True,
                            "independentSupport": False,
                            "sampleCoverageAdequate": (g["scoreline"].get("sampleHome", 0) >= 5
                                                       and g["scoreline"].get("sampleAway", 0) >= 5),
                            "calibratedProbability": g["scoreline"].get("calibrated") is True}
                # Independent support is not established by using the model's
                # inputs again. Never label these raw-probability edges strong.
                try:
                    edge = assess_edge(
                        market=kind, selection=selection, event_probability=p,
                        quoted_price=prices[selection], same_book_prices=prices,
                        bookmaker=book, observed_at=observed.isoformat(),
                        fixture_id=g["id"], kickoff_at=kickoff.isoformat(),
                        probability_source="INDEPENDENT_SCORELINE_V1_GITHUB raw (not calibrated)",
                        evidence=evidence)
                except ValueError: continue
                markets.append(edge)
        if markets:
            markets.sort(key=lambda x: x["conservativeExpectedROI"], reverse=True)
            by_game.append({"id": g["id"], "league": g["league"], "division": g["division"],
                            "officialB31Qualifiers": [q.get("key") for q in official.get(g["id"], [])],
                            "home": g["home"], "away": g["away"], "kickoff": kickoff.isoformat(),
                            "sourceCapturedAt": source_time.isoformat(), "comparisons": markets})
    finish = datetime.now(TZ)
    by_game = [item for item in by_game if datetime.fromisoformat(item["kickoff"]) > finish]
    return {
        "date": today_snapshot["date"], "status": "frozen-prekickoff",
        "capturedAt": finish.isoformat(), "provider": SOURCE, "model": "INDEPENDENT_SCORELINE_V1_GITHUB",
        "calibrated": False, "fixtureCount": len(games),
        "matchedEventCount": len(matched), "pricedFixtureCount": len(by_game),
        "requestCap": MAX_EVENTS_PER_DAY, "games": by_game,
        "warning": "All differences are provisional watchlist signals, NOT validated profitable edges. No B3.1 probabilities were used.",
        "sourcePolicy": "Permitted public display must be approved separately; no raw provider response stored."
    }

def main():
    now = datetime.now(TZ)
    api_key = os.environ.get("UKODDSAPI_KEY", "").strip()
    display_licence = os.environ.get("FOOTBALL_ODDS_PUBLIC_DISPLAY_ALLOWED") == "true"
    if not api_key:
        export_status("not-configured", "Set repository secret UKODDSAPI_KEY to enable the optional feed.")
        return 0
    if not display_licence:
        export_status("publication-not-authorised",
                      "Public odds display is disabled pending permission under the data provider licence.")
        return 0
    path = DATA / "latest.json"
    if not path.exists():
        export_status("no-forecast", "Independent forecast snapshot not available.")
        return 0
    shot = json.loads(path.read_text(encoding="utf-8"))
    if shot.get("status") != "frozen-prekickoff" or shot.get("date") != now.date().isoformat():
        export_status("no-prekickoff-forecast", "No genuine frozen forecast for the current date.")
        return 0
    if not shot.get("games"):
        export_status("no-prekickoff-fixtures", "No frozen fixture probabilities to compare.")
        return 0
    SNAPS.mkdir(parents=True, exist_ok=True)
    out = SNAPS / (shot["date"] + ".json")
    if out.exists():
        export_status("already-frozen", "Immutable pre-kickoff edge snapshot retained.", date=shot["date"])
        return 0
    if not any(eligible_kickoff(g, now) for g in shot["games"]):
        export_status("kickoff-passed", "No unstarted fixtures with verified kickoff times.")
        return 0
    try:
        events = []
        for page in range(1, 5):
            payload = request_json("/v1/football/events", api_key, {
                "schedule_date": shot["date"], "page": page, "per_page": 200})
            batch = payload.get("events", [])
            if not isinstance(batch, list): raise ValueError("Unexpected event catalog")
            events.extend(batch)
            meta = payload.get("meta", {})
            if page >= int(meta.get("total_pages") or 1): break
        result = build_snapshot(shot, events, api_key, now)
    except (urllib.error.URLError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        export_status("source-unavailable", "Odds API request or validation failed; no substitute prices used.")
        print("Odds refresh skipped: " + type(exc).__name__, file=sys.stderr)
        return 0
    if not result["games"]:
        export_status("no-verified-markets",
                      "Source returned no complete, identity-matched pre-kickoff markets; no edge file published.",
                      date=shot["date"])
        return 0
    # Exclusive-create: never replace any immutable day's research record.
    with out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    export_status("frozen", "Verified pre-kickoff price comparisons frozen separately.",
                  date=shot["date"], pricedFixtures=result["pricedFixtureCount"])
    print("Edge odds snapshot frozen for", result["pricedFixtureCount"], "fixtures.")

if __name__ == "__main__":
    main()
