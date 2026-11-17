"""Workflow-neutral, SHADOW-only Forecast Fuji integration.

Fuji owns forecasts/scoring. Callers own identity, evidence, consent and actions.
No external networking, model calls, or permission inheritance are performed here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .core import Fuji

try:
    import fcntl
except ImportError:  # Fail closed rather than run an unlocked writer.
    fcntl = None

HEX = re.compile(r"^[0-9a-f]{64}$")
KINDS = {"private", "public", "synthetic"}


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(data):
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timezone_required")
    return parsed.astimezone(timezone.utc)


class WorkflowFuji:
    """Single Fuji ledger for many workflows; no domain- or Atlas-specific policies.

    authorize(principal_id, purpose, source_refs) MUST check the current, exact
    permission of the requesting principal against canonical source evidence.
    Permissions are checked again at resolution and never inferred from hashes.
    """

    def __init__(self, path: str | Path, *,
                 authorize: Callable[[str, str, list[str]], bool]):
        if fcntl is None:
            raise RuntimeError("POSIX_file_lock_required")
        if not callable(authorize):
            raise ValueError("authorizer_required")
        self.path = Path(path)
        self.authorize = authorize
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink() or self.path.exists() and not self.path.is_file():
            raise ValueError("unsafe_forecast_db")
        self.lockpath = self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _transaction(self):
        """Stage all of Fuji's internally committing writes before atomic publication."""
        with self.lockpath.open("a+b") as guard:
            os.fchmod(guard.fileno(), 0o600)
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
            disk = Fuji(self.path)
            os.chmod(self.path, 0o600)
            work = Fuji(":memory:")
            try:
                disk.conn.backup(work.conn)
                self._install_guards(work.conn)
                yield work
                work.conn.commit()
                work.conn.backup(disk.conn)
            finally:
                work.close()
                disk.close()
                fcntl.flock(guard.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _install_guards(db):
        db.executescript("""
          CREATE TABLE IF NOT EXISTS workflow_receipts(
            key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
            result_json TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS workflow_receipts_up BEFORE UPDATE
            ON workflow_receipts BEGIN SELECT RAISE(ABORT,'immutable_receipt'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_receipts_del BEFORE DELETE
            ON workflow_receipts BEGIN SELECT RAISE(ABORT,'immutable_receipt'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_propositions_up BEFORE UPDATE
            ON propositions BEGIN SELECT RAISE(ABORT,'immutable_proposition'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_propositions_del BEFORE DELETE
            ON propositions BEGIN SELECT RAISE(ABORT,'immutable_proposition'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_cases_def_up BEFORE UPDATE
            ON cases WHEN NEW.case_key<>OLD.case_key
              OR NEW.evidence_cutoff_at<>OLD.evidence_cutoff_at
              OR NEW.metadata_json<>OLD.metadata_json
              OR NEW.experiment_id<>OLD.experiment_id
              OR NEW.case_id<>OLD.case_id
            BEGIN SELECT RAISE(ABORT,'immutable_case_definition'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_cases_del BEFORE DELETE
            ON cases BEGIN SELECT RAISE(ABORT,'immutable_case'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_scores_up BEFORE UPDATE
            ON scores BEGIN SELECT RAISE(ABORT,'immutable_score'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_scores_del BEFORE DELETE
            ON scores BEGIN SELECT RAISE(ABORT,'immutable_score'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_forecasts_late BEFORE INSERT
            ON forecasts WHEN
              (SELECT c.forecast_status FROM cases c
               JOIN propositions p ON p.case_id=c.case_id
               WHERE p.proposition_id=NEW.proposition_id)<>'PENDING'
            BEGIN SELECT RAISE(ABORT,'late_forecast'); END;
          CREATE TRIGGER IF NOT EXISTS workflow_baselines_late BEFORE INSERT
            ON baselines WHEN
              (SELECT c.forecast_status FROM cases c
               JOIN propositions p ON p.case_id=c.case_id
               WHERE p.proposition_id=NEW.proposition_id)<>'PENDING'
            BEGIN SELECT RAISE(ABORT,'late_baseline'); END;
        """)

    @staticmethod
    def _read(db, key, request_hash):
        row = db.execute(
            "SELECT request_hash,result_json FROM workflow_receipts WHERE key=?",
            (key,)).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise ValueError("replay_conflict")
        return json.loads(row["result_json"])

    @staticmethod
    def _write(db, key, request_hash, result):
        db.execute("INSERT INTO workflow_receipts VALUES(?,?,?)",
                   (key, request_hash, _canonical(result)))

    @staticmethod
    def _scope(request):
        if not isinstance(request, dict):
            raise ValueError("request_object_required")
        for field in ("workflow", "principal_id", "purpose", "case_key"):
            if not isinstance(request.get(field), str) or not request[field].strip():
                raise ValueError("missing_" + field)
        key = _hash([request["workflow"], request["principal_id"], request["case_key"]])
        return key

    def _access(self, principal, purpose, refs):
        if not isinstance(refs, list) or not refs or any(
                not isinstance(s, str) or not s.strip() for s in refs):
            raise ValueError("explicit_source_refs_required")
        if self.authorize(principal, purpose, refs) is not True:
            raise PermissionError("source_access_denied")

    def lock(self, request):
        """Lock one or more genuine estimates BEFORE the first observable outcome."""
        key = self._scope(request)
        scope = request.get("evidence")
        definition = request.get("proposition")
        estimates = request.get("forecasts")
        baseline = request.get("baseline")
        if not all(isinstance(x, dict) for x in (scope, definition, baseline)):
            raise ValueError("evidence_proposition_and_baseline_required")
        if request.get("mode") != "SHADOW" or scope.get("classification") not in KINDS:
            raise ValueError("shadow_classification_required")
        if not HEX.fullmatch(str(scope.get("snapshot_sha256", ""))):
            raise ValueError("snapshot_hash_required")
        refs = scope.get("source_refs")
        self._access(request["principal_id"], request["purpose"], refs)
        if not isinstance(estimates, list) or not 1 <= len(estimates) <= 20:
            raise ValueError("one_or_more_forecasts_required")
        for field in ("key", "statement", "horizon", "resolution_rule",
                      "resolution_source", "earliest_observable_at"):
            if not isinstance(definition.get(field), str) or not definition[field].strip():
                raise ValueError("missing_proposition_" + field)
        cutoff = _instant(scope.get("cutoff_at"))
        now = datetime.now(timezone.utc)
        observable = _instant(definition["earliest_observable_at"])
        if not cutoff <= now < observable:
            raise ValueError("cutoff_or_observation_deadline")
        if baseline.get("name") is None or not baseline.get("derivation"):
            raise ValueError("baseline_and_derivation_required")
        bp = baseline.get("probability")
        if type(bp) not in (float, int) or not math.isfinite(bp) or not 0 <= bp <= 1:
            raise ValueError("invalid_baseline")
        members = set()
        for estimate in estimates:
            if not isinstance(estimate, dict) or not isinstance(estimate.get("member"), str):
                raise ValueError("member_required")
            member = estimate["member"]
            if not member or member in members:
                raise ValueError("duplicate_or_empty_member")
            members.add(member)
            ep = estimate.get("probability")
            if type(ep) not in (float, int) or not math.isfinite(ep) or not 0 <= ep <= 1:
                raise ValueError("invalid_probability")
            if not cutoff <= _instant(estimate.get("generated_at")) <= now:
                raise ValueError("forecast_outside_evidence_window")
        request_hash = _hash(request)
        receipt_key = "lock:" + key
        with self._transaction() as fuji:
            old = self._read(fuji.conn, receipt_key, request_hash)
            if old is not None:
                return old
            exp_id = _hash(["experiment", request["workflow"], "SHADOW"])
            if fuji.conn.execute("SELECT 1 FROM experiments WHERE experiment_id=?",
                                 (exp_id,)).fetchone() is None:
                fuji.create_experiment("Workflow " + request["workflow"], mode="SHADOW",
                                       experiment_id=exp_id)
            case_id = _hash(["case", key])
            fuji.create_case(exp_id, key, scope["cutoff_at"],
                case_id=case_id,
                metadata={"evidence_hash": scope["snapshot_sha256"],
                          "source_refs_hash": _hash(refs),
                          "classification": scope["classification"],
                          "purpose": request["purpose"],
                          "earliest_observable_at": definition["earliest_observable_at"],
                          "request_hash": request_hash,
                          "conditioning_action": request.get("conditioning_action"),
                          "exposure": "SEALED"})
            proposition_id = _hash(["proposition", key, definition["key"]])
            fuji.add_proposition(case_id, definition["key"],
                definition["statement"], definition["horizon"],
                definition["resolution_rule"],
                proposition_id=proposition_id,
                metadata={"resolution_source": definition["resolution_source"]})
            fuji.add_baseline(proposition_id, baseline["name"], bp,
                              derivation=baseline["derivation"])
            for estimate in estimates:
                fuji.add_forecast(proposition_id, estimate["member"],
                    estimate["probability"],
                    evidence_basis=scope["snapshot_sha256"],
                    model_name=estimate.get("model", "unspecified"))
            aggregate = fuji.lock_case(case_id, min_members=1)
            # Final wall-clock check after Fuji's several writes.
            if datetime.now(timezone.utc) >= observable:
                raise ValueError("observation_deadline_passed_during_lock")
            result = {"status": "LOCKED", "mode": "SHADOW",
                      "workflow": request["workflow"], "case_id": case_id,
                      "proposition_id": proposition_id,
                      "evidence_hash": scope["snapshot_sha256"],
                      "forecast_count": len(estimates),
                      "kind": "individual" if len(estimates) == 1 else "multiple_unvalidated",
                      "mean_probability": aggregate[0].probability,
                      "locked_at": datetime.now(timezone.utc).isoformat(),
                      "earliest_observable_at": definition["earliest_observable_at"],
                      "request_hash": request_hash, "actions_enabled": False}
            self._write(fuji.conn, receipt_key, request_hash, result)
            return result

    def resolve(self, request):
        """Resolve only from separately authorized, observed source evidence."""
        key = self._scope(request)
        if type(request.get("outcome")) is not bool:
            raise ValueError("binary_outcome_required")
        for field in ("source_ref", "source_sha256", "observed_at", "verified_by"):
            if not isinstance(request.get(field), str) or not request[field].strip():
                raise ValueError("missing_" + field)
        if not HEX.fullmatch(request["source_sha256"]):
            raise ValueError("resolution_source_hash")
        self._access(request["principal_id"], request["purpose"],
                     [request["source_ref"]])
        observed = _instant(request["observed_at"])
        now = datetime.now(timezone.utc)
        if observed > now:
            raise ValueError("future_resolution")
        request_hash = _hash(request)
        receipt_key = "resolution:" + key
        with self._transaction() as fuji:
            old = self._read(fuji.conn, receipt_key, request_hash)
            if old is not None:
                return old
            locked = fuji.conn.execute(
                "SELECT result_json FROM workflow_receipts WHERE key=?",
                ("lock:" + key,)).fetchone()
            if locked is None:
                raise ValueError("forecast_not_locked")
            prev = json.loads(locked[0])
            definition = fuji.conn.execute(
                "SELECT p.metadata_json,c.metadata_json FROM propositions p "
                "JOIN cases c ON c.case_id=p.case_id WHERE p.proposition_id=?",
                (prev["proposition_id"],)).fetchone()
            propmeta, casemeta = map(json.loads, definition)
            if request["purpose"] != casemeta["purpose"]:
                raise PermissionError("purpose_mismatch")
            if observed < _instant(casemeta["earliest_observable_at"]):
                raise ValueError("premature_resolution")
            if request["source_ref"] != propmeta["resolution_source"]:
                raise ValueError("resolution_source_mismatch")
            scores = fuji.resolve(prev["proposition_id"], request["outcome"],
                notes=_canonical({"source_sha256": request["source_sha256"],
                                  "source_ref": request["source_ref"],
                                  "observed_at": request["observed_at"],
                                  "verified_by": request["verified_by"]}))
            result = {"status": "RESOLVED", "case_id": prev["case_id"],
                      "proposition_id": prev["proposition_id"],
                      "outcome": request["outcome"], "scores": scores,
                      "resolution_source_hash": request["source_sha256"],
                      "request_hash": request_hash, "actions_enabled": False}
            self._write(fuji.conn, receipt_key, request_hash, result)
            return result

    def inspect(self, *, workflow, principal_id, case_key, purpose, source_refs):
        """Read forecast only after rechecking caller's current evidence scope."""
        key = self._scope({"workflow":workflow,"principal_id":principal_id,
                           "case_key":case_key,"purpose":purpose})
        self._access(principal_id, purpose, source_refs)
        with self._transaction() as fuji:
            row = fuji.conn.execute(
                "SELECT result_json FROM workflow_receipts WHERE key=?",
                ("lock:" + key,)).fetchone()
            if row is None:
                return None
            receipt = json.loads(row[0])
            case = fuji.conn.execute("SELECT metadata_json FROM cases WHERE case_id=?",
                                     (receipt["case_id"],)).fetchone()
            meta = json.loads(case[0])
            if purpose != meta["purpose"] or _hash(source_refs) != meta["source_refs_hash"]:
                raise PermissionError("scope_mismatch")
            return receipt
