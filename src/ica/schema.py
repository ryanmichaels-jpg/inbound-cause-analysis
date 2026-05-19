"""Database schema (SQLite DDL) and ICP fit derivation.

Table definitions mirror `docs/data-world.md` §2. ICP fit formula is in
`docs/data-world.md` §3 and is implemented as `compute_icp_fit_score()`
here. CP2's structuring layer is expected to re-run the same formula on
the structured-data side as a sanity check (per the architectural
commitment in data-world.md §3).
"""

import json
import sqlite3
from dataclasses import asdict, astuple, dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from ica.taxonomy import (
    Channel,
    EventType,
    FormType,
    Outcome,
    Persona,
    Seniority,
    Theme,
)

# =============================================================================
# DDL
# =============================================================================

DDL_LEADS = """
CREATE TABLE IF NOT EXISTS leads (
    lead_id                     TEXT PRIMARY KEY,
    created_at                  TEXT NOT NULL,
    person_first_name           TEXT NOT NULL,
    person_last_name            TEXT NOT NULL,
    person_email                TEXT NOT NULL,
    person_title                TEXT NOT NULL,
    person_seniority            TEXT NOT NULL,
    company_name                TEXT NOT NULL,
    company_domain              TEXT NOT NULL,
    company_industry            TEXT NOT NULL,
    company_employee_count      INTEGER NOT NULL,
    company_revenue_band        TEXT NOT NULL,
    persona                     TEXT NOT NULL,
    icp_fit_score               INTEGER NOT NULL,
    created_via_channel         TEXT NOT NULL,
    seed_label_theme_primary    TEXT NOT NULL,
    seed_label_theme_secondary  TEXT
);
"""

DDL_TOUCHPOINTS = """
CREATE TABLE IF NOT EXISTS touchpoints (
    touchpoint_id        TEXT PRIMARY KEY,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id),
    ts                   TEXT NOT NULL,
    channel              TEXT NOT NULL,
    event_type           TEXT NOT NULL,
    content_asset_slug   TEXT,
    utm_source           TEXT,
    utm_medium           TEXT,
    utm_campaign         TEXT,
    utm_content          TEXT,
    referrer_url         TEXT,
    is_first_touch       INTEGER NOT NULL,
    is_last_touch        INTEGER NOT NULL
);
"""

DDL_FORM_SUBMISSIONS = """
CREATE TABLE IF NOT EXISTS form_submissions (
    submission_id        TEXT PRIMARY KEY,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id),
    touchpoint_id        TEXT NOT NULL REFERENCES touchpoints(touchpoint_id),
    ts                   TEXT NOT NULL,
    form_type            TEXT NOT NULL,
    free_text_question   TEXT NOT NULL,
    free_text_answer     TEXT NOT NULL,
    ground_truth_themes  TEXT NOT NULL  -- JSON array
);
"""

DDL_SALES_NOTES = """
CREATE TABLE IF NOT EXISTS sales_notes (
    note_id              TEXT PRIMARY KEY,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id),
    ts                   TEXT NOT NULL,
    kind                 TEXT NOT NULL,
    author               TEXT NOT NULL,
    text                 TEXT NOT NULL,
    ground_truth_themes  TEXT NOT NULL  -- JSON array
);
"""

DDL_OUTCOMES = """
CREATE TABLE IF NOT EXISTS outcomes (
    lead_id            TEXT PRIMARY KEY REFERENCES leads(lead_id),
    outcome            TEXT NOT NULL,
    sub_reason         TEXT,
    pipeline_value_usd INTEGER,
    resolved_at        TEXT NOT NULL,
    days_to_outcome    INTEGER NOT NULL
);
"""

ALL_DDL: tuple[str, ...] = (
    DDL_LEADS,
    DDL_TOUCHPOINTS,
    DDL_FORM_SUBMISSIONS,
    DDL_SALES_NOTES,
    DDL_OUTCOMES,
)


def create_tables(conn: sqlite3.Connection) -> None:
    """Run all CREATE TABLE statements. Idempotent."""
    for ddl in ALL_DDL:
        conn.execute(ddl)
    conn.commit()


# =============================================================================
# Dataclasses (one per table). Field order matches column order in the DDL
# so dataclasses.astuple() can feed parametrized INSERTs directly.
# =============================================================================


@dataclass
class Lead:
    lead_id: str
    created_at: datetime
    person_first_name: str
    person_last_name: str
    person_email: str
    person_title: str
    person_seniority: Seniority
    company_name: str
    company_domain: str
    company_industry: str
    company_employee_count: int
    company_revenue_band: str
    persona: Persona
    icp_fit_score: int
    created_via_channel: Channel
    seed_label_theme_primary: Theme
    seed_label_theme_secondary: Theme | None = None


@dataclass
class Touchpoint:
    touchpoint_id: str
    lead_id: str
    ts: datetime
    channel: Channel
    event_type: EventType
    content_asset_slug: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    referrer_url: str | None = None
    is_first_touch: bool = False
    is_last_touch: bool = False


@dataclass
class FormSubmission:
    submission_id: str
    lead_id: str
    touchpoint_id: str
    ts: datetime
    form_type: FormType
    free_text_question: str
    free_text_answer: str
    ground_truth_themes: list[Theme] = field(default_factory=list)


@dataclass
class SalesNote:
    note_id: str
    lead_id: str
    ts: datetime
    kind: str  # "rep_note" | "call_transcript_snippet"
    author: str  # "sdr" | "ae" | "sales_engineer"
    text: str
    ground_truth_themes: list[Theme] = field(default_factory=list)


@dataclass
class OutcomeRow:
    lead_id: str
    outcome: Outcome
    resolved_at: datetime
    days_to_outcome: int
    sub_reason: str | None = None
    pipeline_value_usd: int | None = None


# =============================================================================
# Insertion helpers — translate dataclass -> column tuple suitable for
# parametrized INSERT. Handles enum->str, datetime->ISO, list->JSON.
# =============================================================================


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, list):
        # ground_truth_themes
        return json.dumps([t.value if hasattr(t, "value") else t for t in value])
    if hasattr(value, "value"):  # StrEnum / Enum
        return value.value
    return value


def _row_tuple(obj: Any) -> tuple:
    return tuple(_serialize_value(v) for v in astuple(obj))


def insert_lead(conn: sqlite3.Connection, lead: Lead) -> None:
    conn.execute(
        "INSERT INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _row_tuple(lead),
    )


def insert_touchpoint(conn: sqlite3.Connection, tp: Touchpoint) -> None:
    conn.execute(
        "INSERT INTO touchpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _row_tuple(tp),
    )


def insert_form_submission(conn: sqlite3.Connection, fs: FormSubmission) -> None:
    conn.execute(
        "INSERT INTO form_submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        _row_tuple(fs),
    )


def insert_sales_note(conn: sqlite3.Connection, sn: SalesNote) -> None:
    conn.execute(
        "INSERT INTO sales_notes VALUES (?, ?, ?, ?, ?, ?, ?)",
        _row_tuple(sn),
    )


def insert_outcome(conn: sqlite3.Connection, oc: OutcomeRow) -> None:
    # Field order in the dataclass matches insertion column order:
    # (lead_id, outcome, resolved_at, days_to_outcome, sub_reason, pipeline_value_usd)
    # But the DDL column order is:
    # (lead_id, outcome, sub_reason, pipeline_value_usd, resolved_at, days_to_outcome)
    # So we name the columns explicitly here.
    conn.execute(
        """INSERT INTO outcomes
           (lead_id, outcome, sub_reason, pipeline_value_usd, resolved_at, days_to_outcome)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            oc.lead_id,
            oc.outcome.value,
            oc.sub_reason,
            oc.pipeline_value_usd,
            oc.resolved_at.isoformat(),
            oc.days_to_outcome,
        ),
    )


# =============================================================================
# ICP fit derivation (data-world.md §3)
#
# CP2's structuring step will re-run this same formula on the structured
# data side as a consistency check.
# =============================================================================

_ICP_INDUSTRY_HIGH_FIT = frozenset({"SaaS", "Fintech", "Martech"})
_ICP_INDUSTRY_NEUTRAL = frozenset({"E-commerce", "Healthcare"})

_ICP_PERSONA_BONUS: dict[Persona, int] = {
    Persona.MAYA: 10,
    Persona.DAVID: 8,
    Persona.PATRICIA: -5,
    Persona.CARLOS: -10,
}


def compute_icp_fit_score(
    persona: Persona,
    industry: str,
    employee_count: int,
    seniority: Seniority,
    rng: np.random.Generator,
) -> int:
    """Deterministic-with-noise ICP fit score in [0, 100].

    Same formula is re-implemented in CP2's structuring step for cross-checking.
    """
    score = 50

    # Company size
    if 150 <= employee_count <= 500:
        score += 20
    elif 50 <= employee_count < 150:
        score += 5
    elif 500 < employee_count <= 1500:
        score += 0
    elif employee_count < 50:
        score -= 15
    else:  # > 1500
        score -= 10

    # Industry
    if industry in _ICP_INDUSTRY_HIGH_FIT:
        score += 10
    elif industry in _ICP_INDUSTRY_NEUTRAL:
        score += 0
    else:
        score -= 10

    # Seniority
    if seniority in (Seniority.DIRECTOR, Seniority.VP):
        score += 10
    elif seniority == Seniority.SR_MANAGER:
        score += 5
    elif seniority == Seniority.C_LEVEL:
        score -= 5
    elif seniority == Seniority.IC:
        score -= 10
    # Manager: 0

    # Persona archetype
    score += _ICP_PERSONA_BONUS[persona]

    # Small Gaussian noise
    score += int(round(rng.normal(0, 3)))

    return max(0, min(100, score))


def revenue_band_for_employee_count(employee_count: int) -> str:
    """Derive a coarse revenue band from headcount."""
    if employee_count < 30:
        return "<$5M"
    if employee_count < 150:
        return "$5-20M"
    if employee_count < 500:
        return "$20-100M"
    if employee_count < 1500:
        return "$100-500M"
    return "$500M+"


# =============================================================================
# Convenience: in-memory or on-disk DB constructor
# =============================================================================


def open_db(path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection and ensure tables exist.

    Pass `path=None` for in-memory (useful in tests).
    """
    conn = sqlite3.connect(path or ":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    create_tables(conn)
    return conn


__all__ = [
    "ALL_DDL",
    "DDL_LEADS",
    "DDL_TOUCHPOINTS",
    "DDL_FORM_SUBMISSIONS",
    "DDL_SALES_NOTES",
    "DDL_OUTCOMES",
    "FormSubmission",
    "Lead",
    "OutcomeRow",
    "SalesNote",
    "Touchpoint",
    "asdict",  # re-export convenience
    "compute_icp_fit_score",
    "create_tables",
    "insert_form_submission",
    "insert_lead",
    "insert_outcome",
    "insert_sales_note",
    "insert_touchpoint",
    "open_db",
    "revenue_band_for_employee_count",
]
