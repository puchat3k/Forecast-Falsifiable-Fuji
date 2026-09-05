# Forecast Falsifiable Fuji

**FFF / 3F** is the public GitHub identity of **Forecast Fuji**, a small, auditable framework for making **probabilistic predictions before an agent acts**, locking those predictions before outcome exposure, and scoring them against reality.

The name follows the public VAN naming canon: **Forecast** (Verb) + **Falsifiable** (Adjective) + **Fuji** (Noun). The underlying internal/project identity remains Forecast Fuji.

It is designed for operational agents, product experiments, content systems, and other workflows where "we expected this to work" should be a testable statement rather than hindsight.

## Core idea

```text
case + evidence cutoff
        ↓
fixed propositions
        ↓
independent forecasters
        ↓
locked probabilities
        ↓
action happens elsewhere
        ↓
external outcome
        ↓
resolution + Brier score
        ↓
calibration against baselines
```

Forecast Fuji **does not execute the action being forecast**. In `SHADOW` mode it cannot gate or modify the operational system. That separation is deliberate.

## Principles

1. **No retrofit.** Define the proposition and resolution rule before seeing the outcome.
2. **Evidence cutoff.** Record the latest evidence that was allowed into the forecast.
3. **Independent estimates.** Do not let ensemble members see each other's probabilities before locking.
4. **Explicit baselines.** A sophisticated forecaster has to beat something simple.
5. **Proper scoring.** Binary forecasts are evaluated with Brier scores.
6. **Shadow first.** A forecasting system earns influence through prospective calibration, not confidence.
7. **Immutable ledger.** Locked forecasts and resolutions are append-only facts.

## Quick start

```python
from forecast_fuji import Fuji

fuji = Fuji("fuji.db")
exp = fuji.create_experiment("My experiment", mode="SHADOW")
case = fuji.create_case(exp, "case-001", "2026-09-05T10:00:00Z")

p = fuji.add_proposition(
    case,
    "SUCCESS_30D",
    "The project will meet its success threshold within 30 days.",
    "30D",
    "Resolve TRUE iff the threshold fixed in case metadata is met by day 30.",
)

fuji.add_baseline(p, "NAIVE_50", 0.50)
fuji.add_forecast(p, "GENERALIST", 0.64)
fuji.add_forecast(p, "DOMAIN", 0.71)
fuji.add_forecast(p, "REDTEAM", 0.49)

print(fuji.lock_case(case))
# ... the real-world action occurs outside Forecast Fuji ...
print(fuji.resolve(p, True))
print(fuji.leaderboard(exp))
```

## What v0.1 includes

- SQLite-backed experiment/case/proposition ledger
- locked member forecasts
- locked baseline forecasts
- arithmetic-mean ensemble aggregation
- immutable forecasts, baselines, and resolutions
- binary resolution
- Brier scoring for members, aggregate, and baselines
- experiment leaderboard
- zero runtime dependencies outside Python's standard library

## What it intentionally does not include yet

- web research
- LLM provider integrations
- outcome scrapers
- automatic action execution
- calibration transforms
- weighted ensembles
- retrospective forecast editing

Those belong in adapters or later prospectively versioned experiments.

## Relationship to Signal Samar

Forecast Fuji was developed while building Signal Samar, an internal evidence-grounded content system. Samar is one application of the forecasting pattern, not a dependency of Forecast Fuji. The public library is intentionally domain-neutral and contains no private Samar data, LinkedIn analytics, credentials, or GSV-specific schema.

## Status

`0.1.0` — public preview.

The API is intentionally small while the methodology accumulates prospective resolved cases.

## License

MIT.
