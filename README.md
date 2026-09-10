# NFL Prediction Board

Hosted public viewer for the NFL Weekly Prediction Board.

## How it works

The full prediction model runs outside this public repository. The approved 05:00 and 15:00 Europe/London refreshes calculate projections, preserve frozen pregame history, validate the output, and then publish a compact viewing dataset here.

The public site contains:

- all game score, winner, spread and total projections
- current comparison market lines, which never influence model projections
- top 50 rated player props plus every prop with a market line
- top 25 touchdown candidates per snapshot
- graded outcomes and weekly review text

The complete unfiltered prediction history and model working data remain in the private project Library and are not published here.

## Safety and publishing rules

No passwords, API keys, credentials, customer information, personal files or local-computer data should ever be committed to this repository. The site is static and requires no software, server or browser extension on the user's computer.

Data chunks are written and validated before `data/manifest.json` is switched to them. If a scheduled publish fails, the previous valid public version should remain available.

## Active model

Smart Signals v4.12, Balanced Scoring + Kickers.

Home field, rest, venue and strength of schedule are margin-only/zero-sum signals. Efficiency, expected-TD regression, OL/front interaction, injuries, weather and kicking may affect scoring but are centred and capped. Sportsbook lines remain comparison-only.
