from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('SHADOW','ADVISORY','ACTIVE')),
    hypothesis TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
    case_key TEXT NOT NULL,
    evidence_cutoff_at TEXT NOT NULL,
    forecast_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (forecast_status IN ('PENDING','LOCKED')),
    resolution_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (resolution_status IN ('PENDING','RESOLVED')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(experiment_id, case_key)
);
CREATE TABLE IF NOT EXISTS propositions (
    proposition_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    proposition_key TEXT NOT NULL,
    statement TEXT NOT NULL,
    target_horizon TEXT NOT NULL,
    resolution_rule TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(case_id, proposition_key)
);
CREATE TABLE IF NOT EXISTS forecasts (
    forecast_id TEXT PRIMARY KEY,
    proposition_id TEXT NOT NULL REFERENCES propositions(proposition_id) ON DELETE CASCADE,
    member TEXT NOT NULL,
    probability REAL NOT NULL CHECK (probability >= 0 AND probability <= 1),
    evidence_basis TEXT,
    model_name TEXT,
    locked_at TEXT NOT NULL,
    UNIQUE(proposition_id, member)
);
CREATE TABLE IF NOT EXISTS baselines (
    baseline_id TEXT PRIMARY KEY,
    proposition_id TEXT NOT NULL REFERENCES propositions(proposition_id) ON DELETE CASCADE,
    baseline_type TEXT NOT NULL,
    probability REAL NOT NULL CHECK (probability >= 0 AND probability <= 1),
    derivation TEXT,
    locked_at TEXT NOT NULL,
    UNIQUE(proposition_id, baseline_type)
);
CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id TEXT PRIMARY KEY,
    proposition_id TEXT NOT NULL UNIQUE REFERENCES propositions(proposition_id) ON DELETE CASCADE,
    outcome INTEGER NOT NULL CHECK (outcome IN (0,1)),
    ground_truth_value REAL,
    notes TEXT,
    resolved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scores (
    score_id TEXT PRIMARY KEY,
    proposition_id TEXT NOT NULL REFERENCES propositions(proposition_id) ON DELETE CASCADE,
    method_type TEXT NOT NULL CHECK (method_type IN ('FORECAST','AGGREGATE','BASELINE')),
    method_name TEXT NOT NULL,
    probability REAL NOT NULL,
    outcome INTEGER NOT NULL,
    brier REAL NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(proposition_id, method_type, method_name)
);
CREATE TRIGGER IF NOT EXISTS forecasts_immutable_update BEFORE UPDATE ON forecasts BEGIN
    SELECT RAISE(ABORT, 'locked forecasts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS forecasts_immutable_delete BEFORE DELETE ON forecasts BEGIN
    SELECT RAISE(ABORT, 'locked forecasts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS baselines_immutable_update BEFORE UPDATE ON baselines BEGIN
    SELECT RAISE(ABORT, 'locked baselines are immutable');
END;
CREATE TRIGGER IF NOT EXISTS baselines_immutable_delete BEFORE DELETE ON baselines BEGIN
    SELECT RAISE(ABORT, 'locked baselines are immutable');
END;
CREATE TRIGGER IF NOT EXISTS resolutions_immutable_update BEFORE UPDATE ON resolutions BEGIN
    SELECT RAISE(ABORT, 'resolutions are immutable');
END;
CREATE TRIGGER IF NOT EXISTS resolutions_immutable_delete BEFORE DELETE ON resolutions BEGIN
    SELECT RAISE(ABORT, 'resolutions are immutable');
END;
-- Once a case is locked, its question and record are fixed. These triggers
-- hold the invariant in the database itself, not only in the Python API.
CREATE TRIGGER IF NOT EXISTS cases_locked_immutable BEFORE UPDATE ON cases
WHEN OLD.forecast_status <> 'PENDING' AND (
    NEW.case_id IS NOT OLD.case_id OR NEW.experiment_id IS NOT OLD.experiment_id
    OR NEW.case_key IS NOT OLD.case_key OR NEW.evidence_cutoff_at IS NOT OLD.evidence_cutoff_at
    OR NEW.metadata_json IS NOT OLD.metadata_json OR NEW.created_at IS NOT OLD.created_at
    OR NEW.forecast_status <> 'LOCKED')
BEGIN
    SELECT RAISE(ABORT, 'locked cases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS cases_resolution_forward_only BEFORE UPDATE OF resolution_status ON cases
WHEN (OLD.resolution_status = 'RESOLVED' AND NEW.resolution_status <> 'RESOLVED')
    OR (NEW.resolution_status = 'RESOLVED' AND NEW.forecast_status <> 'LOCKED')
BEGIN
    SELECT RAISE(ABORT, 'a case resolves only once, and only after it is locked');
END;
CREATE TRIGGER IF NOT EXISTS cases_locked_delete BEFORE DELETE ON cases
WHEN OLD.forecast_status <> 'PENDING'
BEGIN
    SELECT RAISE(ABORT, 'locked cases are immutable');
END;
CREATE TRIGGER IF NOT EXISTS propositions_insert_requires_pending BEFORE INSERT ON propositions
WHEN (SELECT forecast_status FROM cases WHERE case_id = NEW.case_id) <> 'PENDING'
BEGIN
    SELECT RAISE(ABORT, 'case is locked; propositions are fixed');
END;
CREATE TRIGGER IF NOT EXISTS propositions_locked_update BEFORE UPDATE ON propositions
WHEN (SELECT forecast_status FROM cases WHERE case_id = OLD.case_id) <> 'PENDING'
    OR (SELECT forecast_status FROM cases WHERE case_id = NEW.case_id) <> 'PENDING'
BEGIN
    SELECT RAISE(ABORT, 'propositions are immutable once their case is locked');
END;
CREATE TRIGGER IF NOT EXISTS propositions_locked_delete BEFORE DELETE ON propositions
WHEN (SELECT forecast_status FROM cases WHERE case_id = OLD.case_id) <> 'PENDING'
BEGIN
    SELECT RAISE(ABORT, 'propositions are immutable once their case is locked');
END;
CREATE TRIGGER IF NOT EXISTS forecasts_insert_requires_pending BEFORE INSERT ON forecasts
WHEN (SELECT c.forecast_status FROM cases c JOIN propositions p ON p.case_id = c.case_id
      WHERE p.proposition_id = NEW.proposition_id) <> 'PENDING'
BEGIN
    SELECT RAISE(ABORT, 'case is locked; late forecasts are not allowed');
END;
CREATE TRIGGER IF NOT EXISTS baselines_insert_requires_pending BEFORE INSERT ON baselines
WHEN (SELECT c.forecast_status FROM cases c JOIN propositions p ON p.case_id = c.case_id
      WHERE p.proposition_id = NEW.proposition_id) <> 'PENDING'
BEGIN
    SELECT RAISE(ABORT, 'case is locked; late baselines are not allowed');
END;
CREATE TRIGGER IF NOT EXISTS resolutions_insert_requires_locked BEFORE INSERT ON resolutions
WHEN (SELECT c.forecast_status FROM cases c JOIN propositions p ON p.case_id = c.case_id
      WHERE p.proposition_id = NEW.proposition_id) <> 'LOCKED'
BEGIN
    SELECT RAISE(ABORT, 'case must be locked before resolution');
END;
CREATE TRIGGER IF NOT EXISTS scores_require_resolution BEFORE INSERT ON scores
WHEN NOT EXISTS (SELECT 1 FROM resolutions r
                 WHERE r.proposition_id = NEW.proposition_id AND r.outcome = NEW.outcome)
BEGIN
    SELECT RAISE(ABORT, 'scores must match a recorded resolution');
END;
CREATE TRIGGER IF NOT EXISTS scores_immutable_update BEFORE UPDATE ON scores BEGIN
    SELECT RAISE(ABORT, 'scores are immutable');
END;
CREATE TRIGGER IF NOT EXISTS scores_immutable_delete BEFORE DELETE ON scores BEGIN
    SELECT RAISE(ABORT, 'scores are immutable');
END;
-- INSERT OR REPLACE deletes the old row without firing DELETE triggers
-- (unless recursive_triggers is on), so refuse any insert that would
-- collide with an existing row. A plain INSERT would fail on these anyway.
CREATE TRIGGER IF NOT EXISTS cases_no_replace BEFORE INSERT ON cases
WHEN EXISTS (SELECT 1 FROM cases WHERE case_id = NEW.case_id
             OR (experiment_id = NEW.experiment_id AND case_key = NEW.case_key))
BEGIN
    SELECT RAISE(ABORT, 'cases cannot be replaced');
END;
CREATE TRIGGER IF NOT EXISTS propositions_no_replace BEFORE INSERT ON propositions
WHEN EXISTS (SELECT 1 FROM propositions WHERE proposition_id = NEW.proposition_id
             OR (case_id = NEW.case_id AND proposition_key = NEW.proposition_key))
BEGIN
    SELECT RAISE(ABORT, 'propositions cannot be replaced');
END;
CREATE TRIGGER IF NOT EXISTS forecasts_no_replace BEFORE INSERT ON forecasts
WHEN EXISTS (SELECT 1 FROM forecasts WHERE forecast_id = NEW.forecast_id
             OR (proposition_id = NEW.proposition_id AND member = NEW.member))
BEGIN
    SELECT RAISE(ABORT, 'locked forecasts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS baselines_no_replace BEFORE INSERT ON baselines
WHEN EXISTS (SELECT 1 FROM baselines WHERE baseline_id = NEW.baseline_id
             OR (proposition_id = NEW.proposition_id AND baseline_type = NEW.baseline_type))
BEGIN
    SELECT RAISE(ABORT, 'locked baselines are immutable');
END;
CREATE TRIGGER IF NOT EXISTS resolutions_no_replace BEFORE INSERT ON resolutions
WHEN EXISTS (SELECT 1 FROM resolutions WHERE resolution_id = NEW.resolution_id
             OR proposition_id = NEW.proposition_id)
BEGIN
    SELECT RAISE(ABORT, 'resolutions are immutable');
END;
CREATE TRIGGER IF NOT EXISTS scores_no_replace BEFORE INSERT ON scores
WHEN EXISTS (SELECT 1 FROM scores WHERE score_id = NEW.score_id
             OR (proposition_id = NEW.proposition_id AND method_type = NEW.method_type
                 AND method_name = NEW.method_name))
BEGIN
    SELECT RAISE(ABORT, 'scores are immutable');
END;
"""


@dataclass(frozen=True)
class Aggregate:
    proposition_key: str
    probability: float
    member_count: int


class Fuji:
    """Small, auditable forecasting ledger for pre-action predictions."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        # Fire DELETE triggers for rows that INSERT OR REPLACE removes, too.
        self.conn.execute("PRAGMA recursive_triggers = ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def create_experiment(self, name: str, *, mode: str = "SHADOW", hypothesis: str | None = None,
                          experiment_id: str | None = None) -> str:
        experiment_id = experiment_id or str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO experiments(experiment_id,name,mode,hypothesis,created_at) VALUES(?,?,?,?,?)",
            (experiment_id, name, mode, hypothesis, _now()),
        )
        self.conn.commit()
        return experiment_id

    def create_case(self, experiment_id: str, case_key: str, evidence_cutoff_at: str, *,
                    metadata: dict[str, Any] | None = None, case_id: str | None = None) -> str:
        case_id = case_id or str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO cases(case_id,experiment_id,case_key,evidence_cutoff_at,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
            (case_id, experiment_id, case_key, evidence_cutoff_at, _json(metadata), _now()),
        )
        self.conn.commit()
        return case_id

    def add_proposition(self, case_id: str, proposition_key: str, statement: str, target_horizon: str,
                        resolution_rule: str, *, metadata: dict[str, Any] | None = None,
                        proposition_id: str | None = None) -> str:
        self._assert_case_pending(case_id)
        proposition_id = proposition_id or str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO propositions(proposition_id,case_id,proposition_key,statement,target_horizon,resolution_rule,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (proposition_id, case_id, proposition_key, statement, target_horizon, resolution_rule, _json(metadata), _now()),
        )
        self.conn.commit()
        return proposition_id

    def add_forecast(self, proposition_id: str, member: str, probability: float, *,
                     evidence_basis: str | None = None, model_name: str | None = None) -> str:
        if not 0 <= probability <= 1:
            raise ValueError("probability must be between 0 and 1")
        case_id = self._case_for_proposition(proposition_id)
        self._assert_case_pending(case_id)
        forecast_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO forecasts(forecast_id,proposition_id,member,probability,evidence_basis,model_name,locked_at) VALUES(?,?,?,?,?,?,?)",
            (forecast_id, proposition_id, member, probability, evidence_basis, model_name, _now()),
        )
        self.conn.commit()
        return forecast_id

    def add_baseline(self, proposition_id: str, baseline_type: str, probability: float, *,
                     derivation: str | None = None) -> str:
        if not 0 <= probability <= 1:
            raise ValueError("probability must be between 0 and 1")
        case_id = self._case_for_proposition(proposition_id)
        self._assert_case_pending(case_id)
        baseline_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO baselines(baseline_id,proposition_id,baseline_type,probability,derivation,locked_at) VALUES(?,?,?,?,?,?)",
            (baseline_id, proposition_id, baseline_type, probability, derivation, _now()),
        )
        self.conn.commit()
        return baseline_id

    def lock_case(self, case_id: str, *, min_members: int = 1) -> list[Aggregate]:
        """Lock every proposition of a case.

        One forecaster is enough for an individual forecast (see the
        universal workflow contract). Pass min_members to require a panel.
        """
        if min_members < 1:
            raise ValueError("min_members must be at least 1")
        self._assert_case_pending(case_id)
        props = self.conn.execute(
            "SELECT proposition_id, proposition_key FROM propositions WHERE case_id=? ORDER BY proposition_key", (case_id,)
        ).fetchall()
        if not props:
            raise ValueError("case has no propositions")
        aggregates: list[Aggregate] = []
        for prop in props:
            row = self.conn.execute(
                "SELECT AVG(probability) AS p, COUNT(DISTINCT member) AS n FROM forecasts WHERE proposition_id=?",
                (prop["proposition_id"],),
            ).fetchone()
            if int(row["n"] or 0) < min_members:
                raise ValueError(f"{prop['proposition_key']} has fewer than {min_members} independent members")
            aggregates.append(Aggregate(prop["proposition_key"], float(row["p"]), int(row["n"])))
        self.conn.execute("UPDATE cases SET forecast_status='LOCKED' WHERE case_id=?", (case_id,))
        self.conn.commit()
        return aggregates

    def aggregate(self, case_id: str) -> list[Aggregate]:
        rows = self.conn.execute(
            """SELECT p.proposition_key, AVG(f.probability) AS p, COUNT(DISTINCT f.member) AS n
               FROM propositions p JOIN forecasts f ON f.proposition_id=p.proposition_id
               WHERE p.case_id=? GROUP BY p.proposition_id,p.proposition_key ORDER BY p.proposition_key""",
            (case_id,),
        ).fetchall()
        return [Aggregate(r["proposition_key"], float(r["p"]), int(r["n"])) for r in rows]

    def resolve(self, proposition_id: str, outcome: bool, *, ground_truth_value: float | None = None,
                notes: str | None = None) -> dict[str, float]:
        case_id = self._case_for_proposition(proposition_id)
        row = self.conn.execute("SELECT forecast_status FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row["forecast_status"] != "LOCKED":
            raise ValueError("case must be locked before resolution")
        out = 1 if outcome else 0
        self.conn.execute(
            "INSERT INTO resolutions(resolution_id,proposition_id,outcome,ground_truth_value,notes,resolved_at) VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), proposition_id, out, ground_truth_value, notes, _now()),
        )

        result: dict[str, float] = {}
        forecasts = self.conn.execute(
            "SELECT member,probability FROM forecasts WHERE proposition_id=?", (proposition_id,)
        ).fetchall()
        for f in forecasts:
            b = (float(f["probability"]) - out) ** 2
            result[f"forecast:{f['member']}"] = b
            self._insert_score(proposition_id, "FORECAST", f["member"], float(f["probability"]), out, b)

        if forecasts:
            p = sum(float(f["probability"]) for f in forecasts) / len(forecasts)
            b = (p - out) ** 2
            result["aggregate:mean"] = b
            self._insert_score(proposition_id, "AGGREGATE", "mean", p, out, b)

        baselines = self.conn.execute(
            "SELECT baseline_type,probability FROM baselines WHERE proposition_id=?", (proposition_id,)
        ).fetchall()
        for f in baselines:
            b = (float(f["probability"]) - out) ** 2
            result[f"baseline:{f['baseline_type']}"] = b
            self._insert_score(proposition_id, "BASELINE", f["baseline_type"], float(f["probability"]), out, b)

        unresolved = self.conn.execute(
            """SELECT COUNT(*) AS n FROM propositions p
               WHERE p.case_id=? AND NOT EXISTS (SELECT 1 FROM resolutions r WHERE r.proposition_id=p.proposition_id)""",
            (case_id,),
        ).fetchone()["n"]
        if unresolved == 0:
            self.conn.execute("UPDATE cases SET resolution_status='RESOLVED' WHERE case_id=?", (case_id,))
        self.conn.commit()
        return result

    def leaderboard(self, experiment_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT s.method_type,s.method_name,COUNT(*) AS n,AVG(s.brier) AS mean_brier
               FROM scores s JOIN propositions p ON p.proposition_id=s.proposition_id
               JOIN cases c ON c.case_id=p.case_id
               WHERE c.experiment_id=? GROUP BY s.method_type,s.method_name
               ORDER BY mean_brier ASC,n DESC""",
            (experiment_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _insert_score(self, proposition_id: str, method_type: str, method_name: str,
                      probability: float, outcome: int, brier: float) -> None:
        self.conn.execute(
            "INSERT INTO scores(score_id,proposition_id,method_type,method_name,probability,outcome,brier,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), proposition_id, method_type, method_name, probability, outcome, brier, _now()),
        )

    def _case_for_proposition(self, proposition_id: str) -> str:
        row = self.conn.execute("SELECT case_id FROM propositions WHERE proposition_id=?", (proposition_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown proposition {proposition_id}")
        return str(row["case_id"])

    def _assert_case_pending(self, case_id: str) -> None:
        row = self.conn.execute("SELECT forecast_status,resolution_status FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown case {case_id}")
        if row["forecast_status"] != "PENDING" or row["resolution_status"] != "PENDING":
            raise ValueError("case is already locked or resolved")
