"""Read-only forecast history: is there a defensible historical reference rate for a new forecast?

SHADOW / EVIDENCE ONLY. The result is a piece of evidence for an analyst. It never changes an approval
status, never selects a negotiation move, and enables no action. The reader opens the ledger read-only
and refuses to write.

The matching rules are data (``FAMILIES`` and ``RULES``), returned verbatim in every result, so an analyst
or reviewer can see exactly why each record was or was not counted.

Only one event family is defined so far: ``offer_approval``.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

RULES_VERSION = "fuji.history.v1"

# Event families. A record's proposition carries metadata {"event": {...}} written at lock time
# (WorkflowFuji.lock validates it with validate_event). Records without a valid label never match.
FAMILIES = {
    "offer_approval": {
        "version": 1,
        "question": "Was the offer approved by the named approver within horizon_days of being submitted for approval?",
        "outcome_true": "the named approver approved the offer as submitted, or with conditions the offering side accepted, "
                        "within horizon_days of anchor_at",
        "outcome_false": "the approver rejected it, or no approval was observed by the end of the window",
        "match_exact": ["approver_role", "offer_side"],
        "allowed": {"approver_role": ["deal_desk", "cfo", "procurement", "credit_committee", "legal"],
                    "offer_side": ["vendor", "buyer"]},
        "horizon_days_allowed": [7, 14, 30],
        "anchor": "anchor_at = when the offer was submitted for approval (UTC)",
    },
}

RULES = {
    "version": RULES_VERSION,
    "match": [
        "same event family and family version",
        "identical values for every field in the family's match_exact list",
        "identical horizon_days (horizons are never pooled; other horizons are reported separately)",
        "same evidence classification as the query (synthetic, public and private records are never mixed)",
        "the record is not one of the query's own cases (exclude_case_keys)",
    ],
    "visible_at_cutoff": [
        "the record's forecast was locked at or before the cutoff",
        "its window (anchor_at + horizon_days) closed at or before the cutoff; otherwise it is 'window open'",
    ],
    "resolved_at_cutoff": [
        "the resolution's observed_at AND its recorded time (resolved_at) are both at or before the cutoff",
        "the resolution records an observed_at (records whose outcome time cannot be verified are excluded)",
        "the observed outcome time is not after the window end (otherwise the label is inconsistent; excluded)",
        "eligible records that are not resolved at the cutoff are reported as unresolved and are never counted "
        "as approved or not approved",
    ],
    "withhold": {
        "WITHHELD_INCOMPATIBLE": "the query is outside the family's rules (unknown family/version, field value or horizon)",
        "WITHHELD_SPARSE": "fewer than min_resolved resolved records in the cohort",
        "WITHHELD_CENSORED": "unresolved records exceed max_unresolved_share of eligible records "
                             "(late outcomes may differ systematically)",
    },
    "min_resolved": 10,
    "max_unresolved_share": 0.25,
    "interval": "Wilson score interval, 95%",
}

EVIDENCE_ONLY = {
    "use": "EVIDENCE_ONLY",
    "mode": "SHADOW",
    "actions_enabled": False,
    "may_change_approval_status": False,
    "may_select_move": False,
}


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone_required")
    return parsed.astimezone(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def validate_event(event):
    """Return a list of problems with an event label (empty list = valid). Used at lock time and query time."""
    if not isinstance(event, dict):
        return ["event_object_required"]
    fam = FAMILIES.get(event.get("family"))
    if fam is None:
        return ["unknown_family"]
    problems = []
    if event.get("version") != fam["version"]:
        problems.append("unsupported_family_version")
    for field in fam["match_exact"]:
        if event.get(field) not in fam["allowed"][field]:
            problems.append(f"{field}_not_allowed")
    if type(event.get("horizon_days")) is not int or event["horizon_days"] not in fam["horizon_days_allowed"]:
        problems.append("horizon_days_not_allowed")
    return problems


def validate_record_event(event):
    """A stored label additionally needs its anchor time."""
    problems = validate_event(event)
    try:
        _instant(event.get("anchor_at") if isinstance(event, dict) else None)
    except (ValueError, TypeError):
        problems.append("anchor_at_required")
    return problems


def _wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _open_read_only(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("forecast_db_not_found")
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def reference_rate(db_path, query, *, principal_id: str, purpose: str,
                   authorize: Callable[[str, str, list[str]], bool]):
    """Return the historical reference rate for one event definition, horizon and decision cutoff.

    query = {"event": {"family", "version", <match_exact fields>, "horizon_days"},
             "cutoff_at": ISO-8601 with timezone, "classification": "synthetic"|"public"|"private",
             "exclude_case_keys": [...]}  (optional)
    """
    if not isinstance(query, dict):
        raise ValueError("query_object_required")
    event = query.get("event")
    family = event.get("family") if isinstance(event, dict) else None
    # Same authority contract as WorkflowFuji: the caller decides who may read which history scope.
    if authorize(principal_id, purpose, [f"fuji-history:{family}"]) is not True:
        raise PermissionError("history_access_denied")
    cutoff = _instant(query.get("cutoff_at"))
    classification = query.get("classification")
    if classification not in {"private", "public", "synthetic"}:
        raise ValueError("classification_required")
    exclude = set(query.get("exclude_case_keys") or [])

    sha = _file_sha256(db_path)
    base = {**EVIDENCE_ONLY, "rules": RULES, "family_rules": FAMILIES.get(family),
            "query": {"event": event, "cutoff_at": _iso(cutoff), "classification": classification,
                      "exclude_case_keys": sorted(exclude)},
            "query_sha256": hashlib.sha256(_canonical(query).encode()).hexdigest(),
            "ledger_sha256": sha}
    problems = validate_event(event)
    if problems:
        return {**base, "status": "WITHHELD_INCOMPATIBLE", "reasons": problems, "rate": None,
                "counts": None, "cohort": [], "other_horizons": {}, "excluded": {}}
    fam = FAMILIES[family]
    horizon = event["horizon_days"]

    conn = _open_read_only(db_path)
    try:
        rows = conn.execute(
            """SELECT p.proposition_id, p.metadata_json AS pmeta, c.case_id, c.case_key, c.metadata_json AS cmeta,
                      (SELECT MAX(f.locked_at) FROM forecasts f WHERE f.proposition_id=p.proposition_id) AS locked_at,
                      r.outcome, r.notes, r.resolved_at
               FROM propositions p JOIN cases c ON c.case_id=p.case_id
               LEFT JOIN resolutions r ON r.proposition_id=p.proposition_id
               ORDER BY p.proposition_id""").fetchall()
    finally:
        conn.close()
    if _file_sha256(db_path) != sha:  # defence in depth: the read must not have changed the ledger
        raise RuntimeError("ledger_changed_during_read")

    excluded = {"unlabelled_or_invalid_label": 0, "other_family_or_version": 0, "other_field_values": 0,
                "other_classification": 0, "own_case": 0, "not_locked_by_cutoff": 0,
                "outcome_time_unverifiable": 0, "outcome_after_window": 0}
    other_h = {}
    cohort, window_open, unresolved = [], [], []
    for r in rows:
        try:
            pmeta, cmeta = json.loads(r["pmeta"] or "{}"), json.loads(r["cmeta"] or "{}")
        except ValueError:
            excluded["unlabelled_or_invalid_label"] += 1
            continue
        ev = pmeta.get("event")
        if not isinstance(ev, dict) or validate_record_event(ev):
            excluded["unlabelled_or_invalid_label"] += 1
            continue
        if ev["family"] != family or ev["version"] != fam["version"]:
            excluded["other_family_or_version"] += 1
            continue
        if any(ev[k] != event[k] for k in fam["match_exact"]):
            excluded["other_field_values"] += 1
            continue
        if cmeta.get("classification") != classification:
            excluded["other_classification"] += 1
            continue
        if r["case_key"] in exclude:
            excluded["own_case"] += 1
            continue
        if not r["locked_at"] or _instant(_z(r["locked_at"])) > cutoff:
            excluded["not_locked_by_cutoff"] += 1
            continue
        anchor = _instant(ev["anchor_at"])
        closes = anchor + timedelta(days=ev["horizon_days"])
        resolved, observed, recorded, source_hash = False, None, None, None
        if r["resolved_at"] is not None:
            try:
                notes = json.loads(r["notes"] or "{}")
            except ValueError:
                notes = {}
            if not isinstance(notes, dict) or not notes.get("observed_at"):
                excluded["outcome_time_unverifiable"] += 1
                continue
            observed, recorded = _instant(notes["observed_at"]), _instant(_z(r["resolved_at"]))
            source_hash = notes.get("source_sha256")
            if observed > closes:
                excluded["outcome_after_window"] += 1
                continue
            resolved = observed <= cutoff and recorded <= cutoff
        if ev["horizon_days"] != horizon:
            # Horizons are kept distinct: counted for transparency, never pooled.
            h = other_h.setdefault(str(ev["horizon_days"]), {"eligible": 0, "resolved": 0, "unresolved": 0})
            if closes <= cutoff:
                h["eligible"] += 1
                h["resolved" if resolved else "unresolved"] += 1
            continue
        item = {"proposition_id": r["proposition_id"], "case_id": r["case_id"], "anchor_at": _iso(anchor),
                "window_closes_at": _iso(closes), "locked_at": _iso(_instant(_z(r["locked_at"])))}
        if closes > cutoff:
            window_open.append(item)
            continue
        if not resolved:
            item["why_unresolved"] = ("resolution recorded after the cutoff" if recorded and recorded > cutoff
                                      else "outcome observed after the cutoff" if observed and observed > cutoff
                                      else "no resolution recorded")
            unresolved.append(item)
            continue
        cohort.append({**item, "outcome": bool(r["outcome"]), "observed_at": _iso(observed),
                       "recorded_at": _iso(recorded), "resolution_source_sha256": source_hash})

    n_res, n_unres = len(cohort), len(unresolved)
    eligible = n_res + n_unres
    k = sum(1 for x in cohort if x["outcome"])
    counts = {"eligible": eligible, "resolved": n_res, "unresolved": n_unres, "approved": k,
              "not_approved": n_res - k, "window_open": len(window_open)}
    reasons = []
    if n_res < RULES["min_resolved"]:
        status = "WITHHELD_SPARSE"
        reasons.append(f"{n_res} resolved < min_resolved {RULES['min_resolved']}")
    elif eligible and n_unres / eligible > RULES["max_unresolved_share"]:
        status = "WITHHELD_CENSORED"
        reasons.append(f"unresolved share {n_unres}/{eligible} > {RULES['max_unresolved_share']}")
    else:
        status = "AVAILABLE"
    rate = None
    if status == "AVAILABLE":
        rate = {"observed": round(k / n_res, 4), "numerator": k, "denominator": n_res, "interval_95": _wilson(k, n_res)}
    return {**base, "status": status, "reasons": reasons, "rate": rate, "counts": counts,
            "cohort": cohort, "unresolved_records": unresolved, "window_open_records": window_open,
            "other_horizons": other_h, "excluded": excluded}


def _z(value):
    """Fuji core stores naive-looking isoformat with +00:00; accept both."""
    return value if ("+" in value[10:] or value.endswith("Z")) else value + "+00:00"


def render(result):
    """The exact analyst-facing text. Deliberately contains no recommendation and no approval status."""
    q = result["query"]
    ev = q["event"] or {}
    fam = result.get("family_rules") or {}
    lines = ["HISTORICAL REFERENCE RATE: evidence only (does not change approval status or choose a move)",
             f"Question: {fam.get('question', '(unknown event family)')}"]
    lines.append("Event: " + ", ".join(f"{k}={ev.get(k)}" for k in ["family", "version", *fam.get("match_exact", []), "horizon_days"]))
    lines.append(f"Decision cutoff: {q['cutoff_at']} | classification: {q['classification']} | rules: {result['rules']['version']}")
    lines.append(f"Status: {result['status']}" + (f" ({'; '.join(result['reasons'])})" if result["reasons"] else ""))
    c = result["counts"]
    if result["rate"]:
        r = result["rate"]
        lo, hi = r["interval_95"]
        lines.append(f"Observed rate: {r['numerator']}/{r['denominator']} approved = {r['observed']:.2f} (95% interval {lo:.2f}-{hi:.2f})")
    else:
        lines.append("Observed rate: withheld")
    if c:
        lines.append(f"Cohort: eligible {c['eligible']} | resolved {c['resolved']} ({c['approved']} approved, {c['not_approved']} not) | "
                     f"unresolved at cutoff {c['unresolved']} (not counted either way) | window still open {c['window_open']} (not counted)")
        for u in result["unresolved_records"]:
            lines.append(f"  unresolved: {u['proposition_id'][:12]} window closed {u['window_closes_at']}: {u['why_unresolved']}")
    if result["other_horizons"]:
        lines.append("Other horizons (not pooled): " + "; ".join(
            f"{h} days: {v['resolved']} resolved, {v['unresolved']} unresolved" for h, v in sorted(result["other_horizons"].items(), key=lambda x: int(x[0]))))
    ex = {k: v for k, v in (result["excluded"] or {}).items() if v}
    if ex:
        lines.append("Not matched: " + ", ".join(f"{k} {v}" for k, v in ex.items()))
    lines.append(f"Provenance: ledger sha256 {result['ledger_sha256'][:16]} | query sha256 {result['query_sha256'][:16]} | "
                 f"{len(result['cohort'])} contributing records" + (
                     ": " + ", ".join(x["proposition_id"][:8] for x in result["cohort"]) if result["cohort"] else ""))
    return "\n".join(lines)
