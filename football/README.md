# English Football Prediction Board

This is a self-contained /football/ section of SteveP1111/nfl-prediction-board. It does not modify the NFL homepage, its data or its workflows.

## Features
- A daily searchable HTML board for top X home wins, BTTS, Over/Under 2.5, Over 3.5, 0-0 scores, away wins and draws.
- Five leagues: E0 Premier League, E1 Championship, E2 League One, E3 League Two and EC National League.
- Independent expected-goal Poisson scoreline distributions, all derived market probabilities, and clean-sheet risk.
- Immutable dated pre-kickoff prediction snapshots in football/data/snapshots/YYYY-MM-DD.json.
- Results in football/data/settlements.json (do not rewrite any frozen prediction).
- Performance by market, accuracy, probability Brier scores, and a daily history view.

## Important model integrity
The imported 17 October 2026 snapshot preserves 21 B3.1 qualifiers from the previously corrected comparator and the independent Scoreline Lab outputs.

The scheduled GitHub runner currently calculates the INDEPENDENT SCORELINE MODEL ONLY. It does not yet replicate the established B3.1 calculation. Newly generated matches correctly mark B3.1 as not-calculated; no B3.1 qualifying recommendations are inferred or invented. A tested faithful headless B3.1 port is required before automating established B3.1 selections in GitHub.

The new script is a transparent experimental independent scoreline model, not guaranteed profitable. It uses prior results, home/away weighted attack/defence strength, current season with a lower-weight prior season, Poisson scorelines and sample-size shrinkage. The earlier Scoreline Lab calibration is not used in this newer runtime; generated probabilities are RAW and marked calibrated=false.

No betting odds are used as inputs. The source CSV may contain odds, but only league, date, kickoff, team names and final goals are read.

## Data sources
Source credit: Football-Data.co.uk.
Current season: https://www.football-data.co.uk/mmz4281/2627/E0.csv (also E1, E2, E3 and EC).
Prior season: https://www.football-data.co.uk/mmz4281/2526/E0.csv (also E1, E2, E3 and EC).
Fixtures: https://www.football-data.co.uk/fixtures.csv, with a documented fallback URL.

The fixtures feed may be delayed. The pipeline refuses to issue fresh forecasts after scheduled kickoff, refuses to invent matches and fails without overwriting known-good publication when source coverage is insufficient.

## Refresh and history
GitHub Actions workflow .github/workflows/football-daily.yml runs twice daily UTC and supports manual workflow dispatch. Scheduled timing is approximate and changes by one hour in UK summer time.

On a successful run it validates the board, fetches and checks all five divisions, deduplicates, freezes forecasts for fixtures yet to kick off, separately grades completed matches, writes market accuracy/Brier scores and commits ONLY changes under football/data/.

Forecast history is frozen: past model probabilities never change after a result. Predictions and later settlements are stored separately.

## Hosting
The linked GitHub connector does not expose creation of a new repository. The project is therefore isolated under the existing public NFL repository without changing the NFL front page. Once the repository's existing GitHub Pages source includes its root, a standard project URL is https://stevep1111.github.io/nfl-prediction-board/football/ . This URL must be verified as deployed before it is advertised as live. If Pages is disabled, enable it in Repository Settings > Pages. Do not create a competing Pages deployment workflow that overwrites the NFL site.

A future dedicated football repository can use these same files, with the workflow moved to its own .github/workflows directory.

## Honest reporting
Do not mix different model versions or B3.1 with independent Scoreline Model hit rates. Accuracy is not profit without bookmaker price data. Historical 17 October snapshot is the previously issued pre-match version, not a regenerated or hindsight-adjusted forecast. No personal information, keys or private football datasets should be committed to the public site.
