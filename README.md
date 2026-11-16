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
- descriptive calibration bins (forecast probability versus observed event frequency)
- paired comparison against an explicitly locked baseline on the **same resolved propositions**
- zero runtime dependencies outside Python's standard library

## Measuring whether forecasts help

After enough cases have resolved, inspect a method's calibration and compare it
against the baseline that was locked *before* the outcome. These are deterministic
analyses of the existing ledger; they do not generate predictions or consume model tokens.

```python
calibration = fuji.calibration_report(exp, "AGGREGATE", "mean", bins=5)
comparison = fuji.compare_to_baseline(exp, "AGGREGATE", "mean", "NAIVE_50")
```

Both reports distinguish `insufficient_data` from `descriptive_only`. Their default
minimum of 20 resolved or paired propositions is a conservative **display threshold,
not a statistical significance criterion**. Reports include the actual sample
size; even larger samples can be correlated, selected or unrepresentative. A
positive Brier improvement does not establish causality, business value or that
the forecasting system generalises. Absent baseline pairs are never silently
substituted with unrelated historical questions.

For Frays integration, see [the SHADOW adapter contract](docs/FRAYS-SHADOW-ADAPTER.md).

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
