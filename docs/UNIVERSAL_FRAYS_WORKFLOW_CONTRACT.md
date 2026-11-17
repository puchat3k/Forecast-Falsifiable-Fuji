# Forecast Fuji: shared workflow contract (development)

**Canonical architecture:** https://github.com/frays-ai/frays-platform/blob/main/docs/architecture/FORECAST_FUJI_SHARED_AUTHORITY_20261117.md

Fuji remains the only forecast ledger/scorer. Consumer graph, identity, evidence, consent and operational actions stay with Frays Core. Atlas is a separate fully synthetic world.

## API

WorkflowFuji(path, authorize=callback) exposes lock(request), inspect(...) and resolve(request). It uses the existing Fuji ledger/score engine, not a new forecasting model. One forecaster is sufficient for an individual forecast; a valid ensemble requires actual distinct independent estimates.

**Lock request:** workflow, principal_id, purpose, case_key, mode=SHADOW, evidence classification (private/public/synthetic), source_refs, snapshot_sha256, cutoff_at; proposition with key/statement/horizon/resolution_rule/resolution_source/earliest_observable_at; one or more actual probability estimates (member, probability, generated_at, model), baseline and optional conditioning_action.

**Return:** immutable opaque lock receipt with case/proposition ID, forecast count, mean, timestamp and actions_enabled=false. **Resolution:** explicit observed source reference and hash, boolean outcome, verification identity and observation timestamp. Private sources can be a provider namespace (event:) but the caller authorization adapter must verify the exact observed source event.

## Trust boundaries

- Caller authenticates principal and enforces current, purpose-scoped authorization on every evidence reference. Fuji's callback checks do not replace Frays Core RLS; a callback that returns True universally is unsafe.
- Snapshot hash must be recomputed by caller from authoritative source revisions. Hash does not prove consent or source truth.
- Private evidence is permitted, and must never be exposed in a public Atlas export or arbitrary telemetry.
- Individual forecasts are not ensembles. Multiple prompts from the same model are not independent judges. Probability is uncalibrated until measured prospective outcomes exist.
- Fuji SHADOW output never authorizes communication, hiring, payments, approval or production actions.
- Resolve only after genuine observability and from predefined, verifiable evidence. Unobserved/ambiguous outcomes remain pending.

## Current implementation and release

The module is a POSIX-local SQLite SHADOW integration with serialized/atomic publication, immutable receipts and source authorization injection. It is NOT a hosted TypeScript/PostgreSQL production gateway. Tests passed on Python 3.10 and 3.12 at tested commit 0b02a18a1e358db774512bbc7b237359dd343b6f; private Frays integration CI has not produced an execution receipt.

Before production: authenticate the TypeScript/Frays Core caller; verify source snapshot closure; implement current grant rechecks, revocation/erasure, concurrent delivery/rollback, VOID and append-only corrections, intervention/exposure logging and real-world baseline comparisons. Preserve the same Fuji interface and do not create a second forecast or relationship graph. No automatic hosting is authorized.

First operational acceptance: a real Company Zero Mission requests a private future event, locks it prospectively in Fuji, then resolves from an authorized event with a Brier comparison. Atlas runs an isolated synthetic question through the same Fuji contract without sharing any real stakeholder records.
