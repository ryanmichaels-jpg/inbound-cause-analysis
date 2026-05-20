"""Schema module tests: DDL creates tables, dataclass round-trip works,
ICP fit formula behaves as documented in data-world.md §3.
"""

import sqlite3
from datetime import datetime

import numpy as np
import pytest

from ica.schema import (
    FormSubmission,
    Lead,
    OutcomeRow,
    SalesNote,
    Touchpoint,
    compute_icp_fit_score,
    insert_form_submission,
    insert_lead,
    insert_outcome,
    insert_sales_note,
    insert_touchpoint,
    open_db,
    revenue_band_for_employee_count,
)
from ica.taxonomy import (
    Channel,
    EventType,
    FormType,
    Outcome,
    Persona,
    Seniority,
    Theme,
)


# -----------------------------------------------------------------------------
# DDL / table creation
# -----------------------------------------------------------------------------


def test_open_db_creates_all_five_tables():
    conn = open_db()
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"leads", "touchpoints", "form_submissions", "sales_notes", "outcomes"} <= names


def test_create_tables_is_idempotent():
    conn = open_db()
    # Run it again — should not raise.
    from ica.schema import create_tables

    create_tables(conn)


# -----------------------------------------------------------------------------
# Insert round-trips
# -----------------------------------------------------------------------------


def _sample_lead() -> Lead:
    return Lead(
        lead_id="lead-001",
        created_at=datetime(2026, 3, 1, 10, 0, 0),
        person_first_name="Maya",
        person_last_name="Chen",
        person_email="maya.chen@example.com",
        person_title="Director of RevOps",
        person_seniority=Seniority.DIRECTOR,
        company_name="Acme SaaS",
        company_domain="acme-saas.com",
        company_industry="SaaS",
        company_employee_count=275,
        company_revenue_band="$20-100M",
        persona=Persona.MAYA,
        icp_fit_score=78,
        created_via_channel=Channel.PODCAST,
        seed_label_theme_primary=Theme.MANUAL_WORK_REDUCTION,
        seed_label_theme_secondary=None,
    )


def test_insert_lead_roundtrip():
    conn = open_db()
    insert_lead(conn, _sample_lead())
    row = conn.execute("SELECT lead_id, persona, icp_fit_score FROM leads").fetchone()
    assert row == ("lead-001", "Mid-market RevOps Leader", 78)


def test_insert_touchpoint_roundtrip():
    conn = open_db()
    insert_lead(conn, _sample_lead())
    tp = Touchpoint(
        touchpoint_id="tp-001",
        lead_id="lead-001",
        ts=datetime(2026, 3, 1, 9, 30, 0),
        channel=Channel.PODCAST,
        event_type=EventType.PODCAST_LISTEN,
        utm_source="ops-podcast-ep-42",
        utm_medium="audio",
        is_first_touch=True,
    )
    insert_touchpoint(conn, tp)
    row = conn.execute(
        "SELECT channel, event_type, is_first_touch FROM touchpoints"
    ).fetchone()
    assert row == ("podcast", "podcast_listen", 1)


def test_insert_form_submission_roundtrip_with_ground_truth_themes():
    conn = open_db()
    insert_lead(conn, _sample_lead())
    tp = Touchpoint(
        touchpoint_id="tp-002",
        lead_id="lead-001",
        ts=datetime(2026, 3, 1, 10, 0, 0),
        channel=Channel.PODCAST,
        event_type=EventType.FORM_SUBMIT,
    )
    insert_touchpoint(conn, tp)
    fs = FormSubmission(
        submission_id="fs-001",
        lead_id="lead-001",
        touchpoint_id="tp-002",
        ts=datetime(2026, 3, 1, 10, 0, 0),
        form_type=FormType.DEMO_REQUEST,
        free_text_question="What's the biggest pain in your day?",
        free_text_answer="We burn 12 hours/week on manual list-building.",
        ground_truth_themes=[Theme.MANUAL_WORK_REDUCTION],
    )
    insert_form_submission(conn, fs)
    raw = conn.execute("SELECT ground_truth_themes FROM form_submissions").fetchone()[0]
    import json
    assert json.loads(raw) == ["manual_work_reduction"]


def test_insert_sales_note_roundtrip():
    conn = open_db()
    insert_lead(conn, _sample_lead())
    sn = SalesNote(
        note_id="note-001",
        lead_id="lead-001",
        ts=datetime(2026, 3, 5, 14, 0, 0),
        kind="rep_note",
        author="sdr",
        text="Discovery call — pain is manual work, not data.",
        ground_truth_themes=[Theme.MANUAL_WORK_REDUCTION, Theme.REP_EFFICIENCY],
    )
    insert_sales_note(conn, sn)
    row = conn.execute("SELECT kind, author FROM sales_notes").fetchone()
    assert row == ("rep_note", "sdr")


def test_insert_outcome_roundtrip():
    conn = open_db()
    insert_lead(conn, _sample_lead())
    oc = OutcomeRow(
        lead_id="lead-001",
        outcome=Outcome.CLOSED_WON,
        resolved_at=datetime(2026, 4, 15, 12, 0, 0),
        days_to_outcome=45,
        sub_reason=None,
        pipeline_value_usd=80_000,
    )
    insert_outcome(conn, oc)
    row = conn.execute(
        "SELECT outcome, pipeline_value_usd, days_to_outcome FROM outcomes"
    ).fetchone()
    assert row == ("closed_won", 80_000, 45)


# -----------------------------------------------------------------------------
# Foreign keys actually enforced
# -----------------------------------------------------------------------------


def test_foreign_keys_enforced_on_orphan_touchpoint():
    conn = open_db()
    tp = Touchpoint(
        touchpoint_id="tp-orphan",
        lead_id="nonexistent",
        ts=datetime.now(),
        channel=Channel.PODCAST,
        event_type=EventType.PAGE_VIEW,
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_touchpoint(conn, tp)


# -----------------------------------------------------------------------------
# ICP fit formula — data-world.md §3
# -----------------------------------------------------------------------------


def _rng_zero_noise() -> np.random.Generator:
    """A test RNG where rng.normal(0, 3) always rounds to 0.

    np.random.default_rng with a seed has predictable but non-zero noise.
    For formula tests we want to isolate the deterministic component.
    """
    class _ZeroRNG:
        def normal(self, loc, scale):
            return 0.0
    return _ZeroRNG()  # type: ignore[return-value]


def test_icp_fit_strong_fit_maya():
    """Maya (Director) at a 300-person SaaS = 50 +8 +7 +7 +5 = 77."""
    score = compute_icp_fit_score(
        Persona.MAYA, "SaaS", 300, Seniority.DIRECTOR, _rng_zero_noise()
    )
    assert score == 77


def test_icp_fit_weak_fit_carlos():
    """Carlos (C-level founder) at a 12-person SaaS startup.

    base 50 - 15 (size) + 7 (industry SaaS) - 5 (C-level) - 8 (persona) = 29
    """
    score = compute_icp_fit_score(
        Persona.CARLOS, "SaaS", 12, Seniority.C_LEVEL, _rng_zero_noise()
    )
    assert score == 29


def test_icp_fit_enterprise_patricia_director():
    """Patricia at a 5000-person Manufacturing co.

    base 50 - 10 (oversized) - 10 (off-industry) + 7 (Director) - 2 (persona) = 35
    """
    score = compute_icp_fit_score(
        Persona.PATRICIA, "Manufacturing", 5000, Seniority.DIRECTOR, _rng_zero_noise()
    )
    assert score == 35


def test_icp_fit_worst_deterministic_lead_above_floor():
    """Deterministic worst-case attributes still score above 0.

    Lowest score reachable without noise: Carlos (weak persona),
    off-industry, sub-50 headcount, IC seniority.
    base 50 - 15 (size) - 10 (industry) - 10 (IC) - 8 (persona) = 7
    """
    score = compute_icp_fit_score(
        Persona.CARLOS, "Consumer", 5, Seniority.IC, _rng_zero_noise()
    )
    assert score == 7
    score2 = compute_icp_fit_score(
        Persona.CARLOS, "Manufacturing", 3, Seniority.IC, _rng_zero_noise()
    )
    assert score2 == 7


def test_icp_fit_clamped_at_zero():
    """An extreme negative noise draw floors the score at 0, not below."""

    class _ExtremeNegativeRNG:
        def normal(self, loc, scale):
            return -999.0

    score = compute_icp_fit_score(
        Persona.CARLOS, "Consumer", 5, Seniority.IC, _ExtremeNegativeRNG()  # type: ignore[arg-type]
    )
    assert score == 0


def test_icp_fit_deterministic_with_same_seed():
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    s1 = compute_icp_fit_score(Persona.MAYA, "SaaS", 300, Seniority.DIRECTOR, rng1)
    s2 = compute_icp_fit_score(Persona.MAYA, "SaaS", 300, Seniority.DIRECTOR, rng2)
    assert s1 == s2


# -----------------------------------------------------------------------------
# revenue_band_for_employee_count
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "employee_count,expected",
    [
        (5, "<$5M"),
        (29, "<$5M"),
        (30, "$5-20M"),
        (149, "$5-20M"),
        (150, "$20-100M"),
        (499, "$20-100M"),
        (500, "$100-500M"),
        (1499, "$100-500M"),
        (1500, "$500M+"),
        (50_000, "$500M+"),
    ],
)
def test_revenue_band_boundaries(employee_count: int, expected: str):
    assert revenue_band_for_employee_count(employee_count) == expected
