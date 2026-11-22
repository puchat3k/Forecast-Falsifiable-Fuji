# Forecast history: is there a defensible historical reference rate?

`forecast_fuji.history.reference_rate()` is a **read-only, evidence-only** reader over a Fuji ledger. You give it an event definition, a horizon and a decision cutoff. It returns:
- the matching cohort;
- eligible, resolved and unresolved counts;
- the observed rate, or the reason it is withheld;
- provenance for every contributing record.

The result never changes an approval status and never selects a negotiation move. These flags are always set: `use: EVIDENCE_ONLY`, `actions_enabled: false`, `may_change_approval_status: false`, `may_select_move: false`.

**How it reads the ledger:**
- It opens the ledger with SQLite `mode=ro` and `query_only`.
- It hashes the ledger file before and after the read.
- It goes through the same `authorize(principal, purpose, refs)` contract as `WorkflowFuji`, with the scope `fuji-history:<family>`.

## One event family: `offer_approval` (v1)
- **Question:** was the offer approved by the named approver within `horizon_days` of being submitted for approval (`anchor_at`)?
- **Match fields (exact):**
  - `approver_role`: one of deal_desk, cfo, procurement, credit_committee, legal;
  - `offer_side`: vendor or buyer.
- **Horizons:** 7, 14 or 30 days.

**How records get labelled:** a record carries `proposition.event = {family, version, approver_role, offer_side, horizon_days, anchor_at}`.
- `WorkflowFuji.lock` now accepts this optional label.
- It validates the label against the same rules.
- It rejects an anchor time later than the evidence cutoff.

Unlabelled records never match.

## Matching and visibility rules (returned verbatim in every result as `rules` and `family_rules`)
**A record matches only if all of these hold:**
- same family and version;
- identical match fields;
- identical `horizon_days` (other horizons are counted under `other_horizons`, never pooled);
- same classification (synthetic, public and private records are never mixed);
- not one of the query's own cases.

**At the cutoff:**
- **Visible:** the record's forecast was locked at or before the cutoff.
- **Eligible:** its window (`anchor_at + horizon_days`) closed at or before the cutoff. Windows that are still open are reported but not counted.
- **Resolved:** both the observed outcome time (`observed_at`, written by `WorkflowFuji.resolve`) and the time the resolution was recorded are at or before the cutoff.
- **Unresolved:** eligible but not resolved. These are reported separately, with the reason, and never counted as approved or not approved.
- **Excluded:** resolutions with no `observed_at` (timing cannot be verified), and outcomes observed after the window end.

**When the rate is withheld:**
- `WITHHELD_INCOMPATIBLE`: the query is outside the family rules.
- `WITHHELD_SPARSE`: fewer than 10 resolved records.
- `WITHHELD_CENSORED`: more than 25% of eligible records are unresolved.

When the rate is available, it is reported as k/n with a 95% Wilson interval.

## Synthetic replay
```bash
python3 -m examples.history_replay --out examples/history_replay_output --legacy-db tests/fixtures/next_move_round2_fuji.sqlite
python3 -m unittest discover -v
```
The replay builds a synthetic ledger through the real `WorkflowFuji.lock` and `resolve` calls, using a replay clock. It then asks for reference rates. The exact analyst-facing text is in `examples/history_replay_output/ANALYST-OUTPUT.txt`.

**What the replay shows:**
- **Usable cohort** (deal_desk / vendor / 14 days, cutoff 2027-03-15): 9/12 = 0.75 (0.47–0.91), status AVAILABLE.
  - 1 eligible record is unresolved: its approval was observed on 03-05 but recorded on 03-20.
  - 1 record's window is still open.
  - The 5 records with a 30-day horizon are not pooled.
- **Same query at 2027-04-01:** the late resolution and the formerly open window now count: 10/14 = 0.71.
- **Sparse cohort** (cfo): 4 resolved, so the rate is WITHHELD_SPARSE.
- **Incompatible query** (approver_role=board): WITHHELD_INCOMPATIBLE.
- **Existing records** (the Next Move round-2 ledger, frays-platform #310): all 54 propositions are unlabelled, so nothing matches.
  - Those records also show why `observed_at` is required: their resolutions were recorded on 2026-11-22, *before* their own 2027 case cutoffs, because they are retrospective replays. A reader that trusted the recording time alone would leak hindsight into history.

**What is not stable between runs:** the ledger sha256 changes on each replay, because core Fuji uses random row ids. Proposition ids, counts and rates are deterministic.

## What it does not do
- It does not infer labels from free text.
- It does not pool horizons or classifications.
- It does not produce a recommendation.
- It is not connected to any product surface.
