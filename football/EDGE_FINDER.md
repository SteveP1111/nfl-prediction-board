# Football Edge Finder (experimental, research only)

This optional module compares an **independently calculated, calibrated event probability** with a **verified pre-kickoff bookmaker quote**. It does not change B3.1 or the independent Scoreline Lab, fetch bookmaker prices, place bets, or use odds to train either model.

## The calculation, explained

For decimal odds 1.80, the quoted break-even probability is `1 / 1.80 = 55.56%`. If the calibrated model says the event occurs 65% of the time, the quoted-price edge is **65 - 55.56 = +9.44 percentage points**. The model's fair odds are `1 / 0.65 = 1.54`. Expected ROI is `0.65 * 1.80 - 1 = +17%` per unit staked, **only if the model probability is well calibrated**. This is not a guarantee and should not be confused with hit rate.

To compare with the market's *fair* consensus, first obtain all outcomes of the **same market from the same bookmaker and timestamp**. For example 1X2 home/draw/away. Convert each to `1/price`, then divide each by the sum of all three implied probabilities. The excess of that sum over 1 is the bookmaker's overround. Never mix a home price from one bookmaker with draw and away prices from another to calculate no-vig probability.

Two distinct comparisons are retained:
- **Quoted-price break-even** determines theoretical value at an actual obtainable price.
- **No-vig probability** indicates whether the model genuinely disagrees with that bookmaker's market view.

Neither B3.1 Overall Pick Score, market confidence, nor its composite home-win likelihood is an event probability. Do not insert these as `event_probability`. Use an independently verified calibrated event probability, or mark the edge unverified. Raw uncalibrated Scoreline Model probabilities should remain watchlist only.

## Evidence and caution

A research-edge classification requires an authenticated canonical fixture, identical market/line, independent statistical support, adequate sample coverage, calibrated probability and positive expected value after a conservative probability haircut. The default haircut of five percentage points is an **illustrative risk allowance**, not a statistically estimated confidence interval. Refine it only after prospective calibration analysis.

For each candidate explain home/away form, scoring/conceding trends, shots and xG when actually available, source coverage, bookmaker disagreement, and counterarguments. Mark absent inputs missing, never infer them. Preserve bookmaker/source/timestamp and the complete outcome price set. Use only lawfully licensed or permitted feeds; do not scrape restricted bookmakers. Do not publish unlicensed odds data to the public board.

## Python example (illustrative only)

```python
from edge_finder import assess_edge
result = assess_edge(
    market="1X2", selection="Home",
    event_probability=0.65, quoted_price=1.80,
    same_book_prices={"Home": 1.80, "Draw": 3.60, "Away": 4.80},
    bookmaker="EXAMPLE ONLY", observed_at="2026-10-20T12:00:00+01:00",
    kickoff_at="2026-10-21T19:45:00+01:00",
    fixture_id="2026-10-21|E0|canonical home|canonical away",
    probability_source="verified calibrated independent forecast",
    evidence={"teamIdentityVerified": True, "marketMatched": True,
              "independentSupport": True, "sampleCoverageAdequate": True,
              "calibratedProbability": True}
)
```

## Prospective validation

Freeze probability and quote **before kickoff**. In a separate mutable settlement record, track Win/Loss/Push, flat-unit realized ROI, hit rate, Brier score, by-market and by-league calibration, and closing-line value only when a legitimate closing quote is available. Compare research-edge candidates against ordinary B3.1 picks and bookmaker baseline, accounting for selection count and uncertainty. Never backfill old odds or rewrite frozen forecasts.

**Integration status:** This is a safe standalone calculation library and methodology. Automated odds ingestion, board UI, snapshots, prospective settlement and GitHub Actions integration are **not implemented** by this module. They require a validated permissible feed and tests before enabling publication.
