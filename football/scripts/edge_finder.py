#!/usr/bin/env python3
"""Research-only football bookmaker edge calculations. No network, no betting, no model feedback.

Input probabilities must be independently generated and frozen before kickoff.
This module deliberately does not ingest odds from football-data training CSVs.
"""
from __future__ import annotations
import math
from datetime import datetime

MARKETS = {
    "BTTS": ("Yes", "No"),
    "Over/Under 2.5": ("Over 2.5", "Under 2.5"),
    "Over/Under 3.5": ("Over 3.5", "Under 3.5"),
    "1X2": ("Home", "Draw", "Away"),
}
MIN_PRICE = 1.001

def finite_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def implied(price):
    if not finite_number(price) or price <= MIN_PRICE:
        raise ValueError("Decimal odds must be finite and > 1.001")
    return 1.0 / price

def no_vig(prices, market):
    """Normalize a complete same-book, same-line outcome set, never mixed bookmakers."""
    outcomes = MARKETS[market]
    if set(prices) != set(outcomes):
        raise ValueError("Missing or extra outcomes for " + market)
    raw = {key: implied(prices[key]) for key in outcomes}
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("Invalid market")
    return {"probabilities": {k: v / total for k, v in raw.items()},
            "overround": total - 1.0, "rawImplied": raw}

def assess_edge(*, market, selection, event_probability, quoted_price,
                same_book_prices, bookmaker, observed_at, fixture_id,
                kickoff_at, probability_source, probability_uncertainty=0.05,
                evidence=None):
    """Compute edge without assigning unsupported 'strong' confidence.
    All probabilities are fractions (0..1), not B3.1 pick scores/likelihood composites.
    """
    if market not in MARKETS or selection not in MARKETS[market]:
        raise ValueError("Unsupported market/selection")
    if not finite_number(event_probability) or not 0 <= event_probability <= 1:
        raise ValueError("Event probability must be a valid fraction")
    if not finite_number(probability_uncertainty) or not 0 <= probability_uncertainty <= 1:
        raise ValueError("Invalid uncertainty")
    if not bookmaker or not fixture_id or not probability_source:
        raise ValueError("Source, bookmaker and canonical fixture ID required")
    observed = datetime.fromisoformat(observed_at)
    kickoff = datetime.fromisoformat(kickoff_at)
    if observed.tzinfo is None or kickoff.tzinfo is None or observed >= kickoff:
        raise ValueError("Timezone-aware pre-kickoff odds timestamp required")
    if not same_book_prices or abs(same_book_prices.get(selection, 0) - quoted_price) > 1e-9:
        raise ValueError("Quoted price must belong to same-book complete market")
    market_probs = no_vig(same_book_prices, market)
    p = event_probability
    conservative_p = max(0.0, p - probability_uncertainty)
    breakeven = implied(quoted_price)
    edge_pp = 100.0 * (p - breakeven)
    consensus_edge_pp = 100.0 * (p - market_probs["probabilities"][selection])
    roi = p * quoted_price - 1.0
    conservative_roi = conservative_p * quoted_price - 1.0
    evidence = evidence or {}
    supported = (evidence.get("teamIdentityVerified") is True
                 and evidence.get("marketMatched") is True
                 and evidence.get("independentSupport") is True
                 and evidence.get("sampleCoverageAdequate") is True
                 and evidence.get("calibratedProbability") is True)
    status = ("research-edge" if supported and conservative_roi > 0
              and consensus_edge_pp > 0 else "watchlist-unverified")
    return {
        "fixtureId": fixture_id, "market": market, "selection": selection,
        "bookmaker": bookmaker, "observedAt": observed_at,
        "kickoffAt": kickoff_at, "probabilitySource": probability_source,
        "modelEventProbability": round(p, 6),
        "quotedDecimalOdds": quoted_price, "rawBreakEven": round(breakeven, 6),
        "noVigMarketProbability": round(market_probs["probabilities"][selection], 6),
        "marketOverround": round(market_probs["overround"], 6),
        "fairOdds": round(1 / p, 4) if p else None,
        "edgePercentagePoints": round(edge_pp, 3),
        "noVigDisagreementPP": round(consensus_edge_pp, 3),
        "expectedROI": round(roi, 6),
        "conservativeExpectedROI": round(conservative_roi, 6),
        "probabilityHaircut": probability_uncertainty,
        "classification": status,
        "evidence": evidence,
        "note": "Research only. Not an official B3.1 pick or guarantee."
    }
