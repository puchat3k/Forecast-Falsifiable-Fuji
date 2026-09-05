# Contributing

Forecast Fuji is intentionally small. Contributions should preserve its main invariant: forecasts are prospectively defined and immutable after locking.

## Good contributions

- deterministic bug fixes with tests
- additional proper scoring rules behind explicit APIs
- storage adapters that preserve immutability
- resolution adapters that keep provenance and never rewrite forecasts
- calibration/reporting utilities that operate on resolved forecasts
- documentation and examples

## Changes that require a versioned experiment or design discussion

- changing the default aggregation rule
- allowing members to see one another's forecasts before lock
- modifying evidence cutoffs after forecasting
- automatically changing operational actions from a forecast
- rewriting historical forecasts or resolutions

## Development

```bash
python -m unittest discover -v
python -m examples.basic
```

Please keep the core dependency-free unless a dependency is clearly necessary and justified.
