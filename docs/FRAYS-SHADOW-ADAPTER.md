# Frays Core ↔ Forecast Fuji: SHADOW integration contract (draft v0.1)

Forecast Fuji is the **forecast ledger and scorer**. Frays remains the owner of
mission identity, evidence, authorisation, consent, and decisions. Do **not**
introduce a second forecast or Brier engine inside Frays Core.

## Smallest useful integration

1. An authorised Frays owner selects a specific future binary outcome of a
   mission, an unambiguous resolution rule, and a deadline. A generated opaque
   case key references the mission; public reports must not expose mission IDs.
2. The adapter snapshots a **consented and scoped** evidence set at a fixed
   `evidence_cutoff_at`, records its hash and source revisions in Fuji case
   metadata, and preserves any withdrawal semantics in Frays. No hidden or
   revoked evidence becomes part of a different principal's context.
3. Define the propositions and a justified baseline **before** seeing the
   outcome. Baseline selection and provenance are recorded; `NAIVE_50` is only a
   neutral sanity benchmark, not a reference-class estimate.
4. Obtain independent forecasts in isolation (or use separately documented
   independent humans). Fuji v0.1 currently requires three members by default
   before locking; do not pretend three LLM prompts are independent observers.
   An unvalidated ensemble remains experimental.
5. Lock the case. Existing Frays workflows execute separately; Fuji in SHADOW
   mode has **no power to approve, block, message or spend**.
6. Resolve only from a predefined external or owner-authorised observation,
   preserving source, timestamp, ambiguity and any dispute outside the Fuji
   binary ledger. A disputed or unobservable outcome stays unresolved.
7. Report paired Brier comparisons and descriptive calibration using Fuji's
   `compare_to_baseline` and `calibration_report`. Preserve the sample sizes,
   data cutoffs and cohort selection in displayed results.

## Non-goals / deployment boundary

- No changes to Frays' live `mission` schema, write gateway, release candidate or
  production worker. In particular, Frays' current agent prompt expressly bans
  ungrounded numerical success claims; this adapter does not change that.
- No personal employment/relationship outcome scores or public per-person
  forecasts. Sensitive uses require separate consent, policy and validation.
- No automatic web retrieval, no claims of causal advantage, and no model API
  calls in Fuji core.
- No unscored predictions passed to Frays as established facts. Any later
  recommendation influence must be earned by prospective comparison with
  simple baselines across representative resolved cases.

## Suggested first study

Use bounded internal Company Zero operational forecasts (e.g., whether a
particular approved task will finish within seven days under an exact success
rule). Capture one case at task assignment, lock the baseline and forecast
before work starts, then resolve from the actual task receipt. Compare against
the historical base rate where available, or clearly mark that no defensible
reference-class baseline exists. No new paid infrastructure is needed.

The target Frays issue is
[`frays-ai/frays-platform#119`](https://github.com/frays-ai/frays-platform/issues/119).
This is a code-and-method contract, not evidence that production integration
or calibration has already been achieved.
