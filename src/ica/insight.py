"""ICA insight layer — CP4 resonance extraction and the signature feature.

The signature move (PROJECT.md): auto-generated GTM action artifacts that
close the loop from insight to action — most portfolio pieces stop at a
dashboard. This module also folds in CP4, the Claude resonance-extraction
layer, per the dashboard-round (a)+(b) decision: Claude extracts themes
from the raw qualitative fields, and those feed the artifact generation.

Sources: PROJECT.md (Signature move; pipeline stages 4-5; LLM-credibility
section; the ruthless cut order — artifacts are cut item #1).
docs/data-world.md §4 (ground_truth_themes are seed labels, not gold).
taxonomy.py §3 + §14 (the disambiguation rule and anchor vocab were
written to be shared by copy_bank generation AND this extraction prompt).

TODO (planning header — review before any implementation). Each decision
is tagged DICTATED (cited spec or a prior locked decision) or PROPOSED
(a v1 design choice open to review).

== Core architectural call: the LLM layer is offline and run-once ==
PROPOSED. The Claude calls do NOT run on dashboard load. A CLI step
(`python -m ica.insight`) runs extraction + artifact generation once,
writes its output to committed files, and the dashboard merely reads
those files. This one decision resolves four problems together:
- Determinism: the generator stays byte-deterministic; the LLM output is
  a committed, dated snapshot rather than something regenerated per run.
- Secrets: only the offline step needs ANTHROPIC_API_KEY. The deployed
  Streamlit Cloud dashboard needs no key and makes no network call.
- Cost / latency: the API is hit once, not on every page view.
- Reviewability: a hiring manager sees the artifacts in the repo without
  running anything or holding a key.

== Decision 1 — CP4 resonance extraction ==
What: Claude reads the qualitative fields (form free-text answers and
sales-note text) and labels each with a primary theme, plus an optional
secondary, from the fixed taxonomy.
- DICTATED: themes are the taxonomy `Theme` enum, not free-form — the
  taxonomy already settled PROJECT.md's open "free-form vs fixed" item.
- DICTATED: the extraction prompt reuses MWR_VS_DATA_QUALITY_
  DISAMBIGUATION and THEME_ANCHOR_VOCAB from taxonomy.py — both exist to
  be shared by copy_bank (generation) and this prompt (extraction).
- PROPOSED scope: extract a stratified SAMPLE (~300 snippets across
  personas and themes), not all ~2,736 fields. The sample is enough to
  prove extraction works, to compute an extracted-vs-seed agreement
  score, and to roll up per-persona resonance. Full-corpus extraction
  (~140 batched calls) is the if-time upgrade, not v1.
- PROPOSED credibility output: report the agreement score — how often
  Claude's extracted primary theme matches the seed ground_truth_theme.
  The ground truth already exists; this is a cheap, high-signal README
  number and a partial stand-in for the deferred stability check.

== Decision 2 — prompt design ==
Two prompts, both as module constants.
- Extraction: input a batch of snippets, output JSON constrained to the
  Theme enum (snippet id, primary, secondary). PROPOSED model: Haiku 4.5
  — a cheap, high-volume classification task. JSON output so parsing is
  robust.
- Artifact generation: input one Finding (its numbers, the resonant
  theme, 2-3 real example snippets buyers actually wrote), output a
  drafted artifact. PROPOSED model: Sonnet 4.6 — few calls, needs
  quality GTM writing.

== Decision 3 — artifact selection ==
PROJECT.md names three artifact types: content briefs, ad-copy variants,
ICP refinements. PROPOSED v1 — one artifact per headline Finding, type
chosen to fit, so the insight->action loop closes on each:
- F1 channel quality   -> content brief (lean into the podcast channel)
- F2 message-persona   -> ad-copy variants (Maya x manual-work-reduction)
- F3 multi-touch path  -> a sequence / play brief
- F4 ICP vs volume     -> an ICP refinement (tighten the broad-funnel ICP)
F5 -> an optional 5th artifact if time allows. This ships all three
named types plus a journey play; 4-5 generation calls is trivial cost.

== Decision 4 — output format ==
PROPOSED: artifacts written as markdown into a committed `artifacts/`
directory — one file per artifact, plus a `resonance.md` extraction
report (the agreement score + per-persona resonance). Markdown because
it reads cleanly in the repo, on GitHub, and in Streamlit unchanged.

== Flag — new dependency and secrets ==
PROPOSED: the `anthropic` SDK goes in its own optional-dependency extra
(`[insight]`), NOT in `[dashboard]` — the dashboard reads committed
markdown and never imports anthropic. `.env` carries ANTHROPIC_API_KEY;
`.env.example` is committed, `.env` is git-ignored (portfolio rule:
never commit real keys).

== Flag — dashboard Actions-tab follow-on ==
This work includes a dashboard.py edit: the Actions tab stops being a
placeholder and renders the artifacts + resonance report from
`artifacts/`; the "seeded ground-truth" theme disclaimer is updated to
point at the now-existing extraction. PROPOSED as a second commit after
insight.py lands.

== Flag — theme-stability check ==
PROJECT.md's LLM-credibility section wants an N-run stability score; the
ruthless cut order (item 3) explicitly allows cutting it with a README
acknowledgement. PROPOSED: defer it — the extracted-vs-seed agreement
score already supplies a credibility number — and acknowledge stability
in the README as the planned next step.

== Time budget — Day 3, and the degrade path ==
Auto-generated artifacts are cut-order item #1. PROPOSED: build the real
LLM version (it is the single strongest portfolio differentiator), but
timeboxed — decision point: if extraction plus one end-to-end artifact
is not working within the agreed budget, degrade per the cut order to
1-2 hard-templated artifacts filled from the seeded themes + finding
numbers, framed honestly in the README. Ryan sets the timebox.

== Module structure ==
PROPOSED: a single module `src/ica/insight.py` (extraction, roll-up,
artifact generation, a `main()` CLI) — a run-once offline script does
not need a package. CLI: `python -m ica.insight`; a Makefile `insight`
target. Tests: the deterministic parts (prompt assembly, agreement-score
computation, markdown rendering) unit-tested with the anthropic client
stubbed, so the suite stays hermetic — no network, no key.

== What v1 does NOT do ==
- No live API calls from the dashboard or inside the test suite.
- No full-corpus extraction (sample only); no theme-stability score.
- No closed-loop measurement (PROJECT.md Phase 2 — a README sketch only).

Output: a committed set of GTM action artifacts plus a resonance report,
surfaced in the dashboard Actions tab.
"""

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ica.generator.seed import DEFAULT_DB_PATH
from ica.taxonomy import (
    F3_PATH_WITHIN_DAYS,
    F4_BAD_CLOSED_LOST_SUB_REASON,
    F4_TARGET_CAMPAIGN,
    MWR_VS_DATA_QUALITY_DISAMBIGUATION,
    THEME_ANCHOR_VOCAB,
    Channel,
    EventType,
    Outcome,
    Persona,
    Theme,
)

# Model IDs are CLI-overridable; these are the v1 defaults (planning header
# Decision 2): Haiku for high-volume classification, Sonnet for drafting.
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
ARTIFACT_MODEL = "claude-sonnet-4-6"

DEFAULT_OUT_DIR = "artifacts"
DEFAULT_BATCH_SIZE = 25
DEFAULT_STABILITY_RUNS = 3

_VALID_THEMES = frozenset(t.value for t in Theme)
_WON = Outcome.CLOSED_WON.value


# =============================================================================
# Prompts — built once from the taxonomy so generation and extraction share
# one source of truth (planning header Decision 1, DICTATED).
# =============================================================================


def _theme_menu() -> str:
    return "\n".join(
        f"- {theme.value}: e.g. {', '.join(THEME_ANCHOR_VOCAB[theme][:6])}"
        for theme in Theme
    )


# rep_efficiency snippets often cite manual work as the *cause* of lost
# selling time; without this guidance, extraction mislabels them as
# manual_work_reduction. Applies the taxonomy's goal-vs-symptom rule to the
# (rep_efficiency, manual_work_reduction) bridge pair.
REP_EFFICIENCY_DISAMBIGUATION = """\
Theme disambiguation — rep_efficiency vs manual_work_reduction

rep_efficiency
    The pain is SELLING CAPACITY — how well, or how much, reps can sell.
    Vocabulary: "call quality", "talk track", "selling time", "rep
    productivity", "call coaching", "reps stuck on admin instead of selling".

manual_work_reduction
    The pain is THE MANUAL WORK ITSELF — copy-paste and by-hand tasks, with
    no mention of reps, selling, or call quality.
    Vocabulary: "list-building by hand", "manual data entry", "copy-paste
    between tools", "ops backlog".

Many snippets name both — a rep-productivity problem CAUSED by manual work
(e.g. "rep productivity tanks when AEs do manual data entry instead of
selling"). Tag these:
    primary   = rep_efficiency        (the goal — selling capacity is what
                                       the buyer ultimately cares about)
    secondary = manual_work_reduction (the symptom — the manual cause)
Tag a snippet primary manual_work_reduction only when the manual work is the
whole point and reps / selling / call quality are not mentioned.
"""

EXTRACTION_SYSTEM = (
    "You label short GTM buyer-feedback snippets with the buyer's primary "
    "pain theme.\n\n"
    "Use EXACTLY these nine themes — return the snake_case id verbatim:\n"
    f"{_theme_menu()}\n\n"
    f"{MWR_VS_DATA_QUALITY_DISAMBIGUATION}\n"
    f"{REP_EFFICIENCY_DISAMBIGUATION}\n"
    "For each snippet return its primary theme, and a secondary theme only "
    "if a distinct second theme is clearly and substantially present "
    "(otherwise null).\n\n"
    "Output ONLY a JSON array, no prose and no code fences:\n"
    '[{"id": <int>, "primary": "<theme_id>", "secondary": "<theme_id>|null"}]'
)

ARTIFACT_SYSTEM = (
    "You are a senior GTM Engineer at a growth-stage B2B SaaS company. You "
    "turn one analysis finding into one concrete internal GTM action "
    "artifact a RevOps or marketing counterpart could act on this week. Be "
    "specific and grounded ONLY in the data you are given — invent no "
    "metrics, names, or quotes. Choose section headings appropriate to the "
    "artifact type requested.\n\n"
    "Output ONLY a JSON object, no prose and no code fences:\n"
    '{"title": "<str>", "headline_insight": "<one sentence>", '
    '"rationale": "<2-4 sentences citing the given numbers>", '
    '"sections": [{"heading": "<str>", "body": "<str>" or ["<str>", ...]}]}'
)

_ARTIFACT_TYPE_HUMAN = {
    "content_brief": "content brief",
    "ad_copy_variants": "set of 3-4 ad-copy variants",
    "sequence_play": "multi-touch sequence play",
    "icp_refinement": "ICP refinement",
}


# =============================================================================
# Data structures
# =============================================================================


@dataclass(frozen=True)
class Snippet:
    """One free-text field to classify — a form answer or a sales-note line."""

    snippet_id: str
    source: str  # "form" | "note"
    lead_id: str
    text: str
    seed_themes: tuple[str, ...]


@dataclass
class FindingContext:
    """Everything the artifact prompt needs for one finding."""

    finding_id: str
    title: str
    artifact_type: str
    stat_summary: str
    example_snippets: list[str] = field(default_factory=list)
    extra: str = ""


# =============================================================================
# Snippet loading
# =============================================================================


def load_snippets(conn: sqlite3.Connection) -> list[Snippet]:
    """Load qualitative-text snippets for extraction.

    v1.5 methodology change: rows whose text is NULL, empty, or
    whitespace-only are skipped. v1 generation always populated these
    fields; v1.5's missingness noise dimension (§2.1 of the v1.5
    planning header) blanks ~25% of qualitative fields to the empty-
    string sentinel. Sending those to the extraction LLM tests
    "classify a blank field" — not "does signal survive noise" — and
    would make the §11 agreement gate fire on a methodology artifact.

    The dropped count is recoverable via count_qualitative_field_status()
    for transparent reporting alongside the agreement number.
    """
    snippets: list[Snippet] = []
    for sid, lead_id, text, themes in conn.execute(
        "SELECT submission_id, lead_id, free_text_answer, ground_truth_themes "
        "FROM form_submissions"
    ):
        if not text or not text.strip():
            continue
        snippets.append(Snippet(sid, "form", lead_id, text, tuple(json.loads(themes))))
    for sid, lead_id, text, themes in conn.execute(
        "SELECT note_id, lead_id, text, ground_truth_themes FROM sales_notes"
    ):
        if not text or not text.strip():
            continue
        snippets.append(Snippet(sid, "note", lead_id, text, tuple(json.loads(themes))))
    return snippets


def count_qualitative_field_status(conn: sqlite3.Connection) -> dict:
    """Counts of qualitative-text fields, partitioned into kept vs empty.

    Used by build_resonance_report() so the resonance.md / .json output
    can surface the missingness filter rate alongside the agreement
    number — v1.5 transparency convention is to report
    "agreement X% on N snippets after excluding Y% empty-text fields."

    Empty here means NULL or whitespace-only — the v1.5 missingness
    sentinel and any legitimate empty values v1 might have shipped.
    """
    def _split(table: str, col: str) -> tuple[int, int]:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        empty = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL OR TRIM({col}) = ''"
        ).fetchone()[0]
        return total, empty

    form_total, form_empty = _split("form_submissions", "free_text_answer")
    note_total, note_empty = _split("sales_notes", "text")
    total = form_total + note_total
    empty = form_empty + note_empty
    return {
        "total_fields": total,
        "empty_fields": empty,
        "kept_fields": total - empty,
        "empty_rate": empty / total if total else 0.0,
        "form_submissions": {"total": form_total, "empty": form_empty},
        "sales_notes": {"total": note_total, "empty": note_empty},
    }


def batch_snippets(snippets: list[Snippet], size: int) -> list[list[Snippet]]:
    return [snippets[i : i + size] for i in range(0, len(snippets), size)]


# =============================================================================
# Claude calls — the only functions that touch the network. anthropic is
# imported lazily so `import ica.insight` (and the test suite) need no SDK.
# =============================================================================


def _make_client():  # pragma: no cover - needs the SDK + a key
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit(
            'error: the anthropic SDK is not installed — run: pip install -e ".[insight]"'
        ) from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("error: ANTHROPIC_API_KEY is not set — see .env.example")
    return anthropic.Anthropic()


def _complete(
    client, model: str, system: str, user: str, *, max_tokens: int, temperature: float
) -> str:
    """Single message turn -> response text. Tests monkeypatch this."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _loads_lenient(text: str):
    """json.loads, tolerating code fences and surrounding prose."""
    body = text.strip()
    if body.startswith("```"):
        body = body.strip("`")
        if body.lower().startswith("json"):
            body = body[4:]
        body = body.strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        for opener, closer in (("[", "]"), ("{", "}")):
            start, end = body.find(opener), body.rfind(closer)
            if 0 <= start < end:
                return json.loads(body[start : end + 1])
        raise


# =============================================================================
# Extraction (CP4)
# =============================================================================


def parse_extraction_response(text: str, batch_len: int) -> list[tuple | None]:
    """Map a model response to a list aligned with the batch: entry i is the
    (primary, secondary) tuple for snippet i, or None if the model omitted or
    garbled it. Unknown theme strings are dropped to None."""
    by_id: dict[int, tuple] = {}
    for item in _loads_lenient(text):
        if not isinstance(item, dict):
            continue
        idx = item.get("id")
        if not isinstance(idx, int) or not 1 <= idx <= batch_len:
            continue
        primary = item.get("primary")
        secondary = item.get("secondary")
        by_id[idx] = (
            primary if primary in _VALID_THEMES else None,
            secondary if secondary in _VALID_THEMES else None,
        )
    return [by_id.get(i + 1) for i in range(batch_len)]


def extract_batch(client, batch: list[Snippet], model: str) -> dict[str, tuple | None]:
    user = "\n".join(f"{i + 1}. {s.text}" for i, s in enumerate(batch))
    text = _complete(
        client, model, EXTRACTION_SYSTEM, user, max_tokens=4096, temperature=0.0
    )
    parsed = parse_extraction_response(text, len(batch))
    return {batch[i].snippet_id: parsed[i] for i in range(len(batch))}


def run_extraction(
    client, snippets: list[Snippet], *, batch_size: int, model: str, progress=None
) -> dict[str, tuple | None]:
    results: dict[str, tuple | None] = {}
    batches = batch_snippets(snippets, batch_size)
    for n, batch in enumerate(batches, 1):
        results.update(extract_batch(client, batch, model))
        if progress is not None:
            progress(n, len(batches))
    return results


def agreement_score(
    extraction: dict[str, tuple | None], snippets: list[Snippet]
) -> dict:
    """Share of snippets whose extracted primary theme matches the seed
    ground_truth primary theme — overall and per seed theme."""
    matched = total = 0
    per_theme: dict[str, list[int]] = {}
    for snippet in snippets:
        result = extraction.get(snippet.snippet_id)
        if result is None or not snippet.seed_themes:
            continue
        seed_primary = snippet.seed_themes[0]
        total += 1
        bucket = per_theme.setdefault(seed_primary, [0, 0])
        bucket[1] += 1
        if result[0] == seed_primary:
            matched += 1
            bucket[0] += 1
    return {
        "overall": matched / total if total else 0.0,
        "matched": matched,
        "total": total,
        "per_theme": {
            theme: {
                "matched": hit,
                "total": seen,
                "rate": hit / seen if seen else 0.0,
            }
            for theme, (hit, seen) in sorted(per_theme.items())
        },
    }


def stability_score(runs: list[dict[str, tuple | None]]) -> dict:
    """Across N extraction runs, the share of snippets where every run agreed
    on the primary theme (the cross-run unanimity rate)."""
    if len(runs) < 2:
        return {"runs": len(runs), "counted": 0, "unanimous_rate": None}
    unanimous = counted = 0
    for snippet_id in runs[0]:
        primaries = []
        for run in runs:
            result = run.get(snippet_id)
            if result is None or result[0] is None:
                primaries = []
                break
            primaries.append(result[0])
        if not primaries:
            continue
        counted += 1
        if len(set(primaries)) == 1:
            unanimous += 1
    return {
        "runs": len(runs),
        "counted": counted,
        "unanimous_rate": unanimous / counted if counted else 0.0,
    }


# =============================================================================
# Finding stats + per-finding artifact context
# =============================================================================


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()):
    value = conn.execute(sql, params).fetchone()[0]
    return value if value is not None else 0


def _f3_path_lead_ids(conn: sqlite3.Connection) -> list[str]:
    days = F3_PATH_WITHIN_DAYS
    rows = conn.execute(
        f"""
        SELECT l.lead_id FROM leads l
        WHERE l.created_via_channel = ?
          AND EXISTS (SELECT 1 FROM touchpoints t WHERE t.lead_id = l.lead_id
              AND t.channel = ?
              AND julianday(t.ts) <= julianday(l.created_at) + {days})
          AND EXISTS (SELECT 1 FROM touchpoints t WHERE t.lead_id = l.lead_id
              AND t.event_type = ?
              AND julianday(t.ts) <= julianday(l.created_at) + {days})
        """,
        (Channel.PODCAST.value, Channel.ORGANIC_SEARCH.value, EventType.DEMO_REQUEST.value),
    )
    return [row[0] for row in rows]


def _segment_quotes(
    conn: sqlite3.Connection, where: str, params: tuple, limit: int = 3
) -> list[str]:
    rows = conn.execute(
        f"SELECT fs.free_text_answer FROM form_submissions fs "
        f"JOIN leads l ON l.lead_id = fs.lead_id WHERE {where} LIMIT {limit}",
        params,
    )
    return [row[0] for row in rows]


def _corroboration(
    extraction: dict[str, tuple | None],
    snippets: list[Snippet],
    lead_ids: set[str],
    theme: str,
) -> str:
    """One line: how often the independent extraction agreed with the seed
    theme on a segment's snippets — the visible insight->artifact loop."""
    hit = seen = 0
    for snippet in snippets:
        if snippet.lead_id not in lead_ids:
            continue
        result = extraction.get(snippet.snippet_id)
        if result is None:
            continue
        seen += 1
        if result[0] == theme:
            hit += 1
    if not seen:
        return ""
    return (
        f"Independent extraction: of {seen} free-text snippets from this "
        f"segment, Claude's resonance pass labelled {hit / seen:.0%} as "
        f"{theme} — corroborating the seed labels.\n\n"
    )


def build_finding_contexts(
    conn: sqlite3.Connection, extraction: dict[str, tuple | None], snippets: list[Snippet]
) -> list[FindingContext]:
    won = _WON
    pod, lin = Channel.PODCAST.value, Channel.LINKEDIN_PAID.value
    mwr, comp = Theme.MANUAL_WORK_REDUCTION.value, Theme.COMPLIANCE_SECURITY.value
    maya, patricia = Persona.MAYA.value, Persona.PATRICIA.value

    def cw(where: str, params: tuple) -> float:
        return _scalar(
            conn,
            f"SELECT AVG(o.outcome = ?) FROM leads l "
            f"JOIN outcomes o ON o.lead_id = l.lead_id WHERE {where}",
            (won, *params),
        )

    def lead_ids(where: str, params: tuple) -> set[str]:
        return {
            row[0]
            for row in conn.execute(f"SELECT lead_id FROM leads WHERE {where}", params)
        }

    # F1 — channel quality surprise
    f1 = FindingContext(
        "F1",
        "Channel quality surprise",
        "content_brief",
        f"Podcast leads close at {cw('l.created_via_channel = ?', (pod,)):.0%} "
        f"({len(lead_ids('created_via_channel = ?', (pod,)))} leads); "
        f"LinkedIn-paid leads close at {cw('l.created_via_channel = ?', (lin,)):.1%} "
        f"({len(lead_ids('created_via_channel = ?', (lin,)))} leads). "
        "The low-volume channel carries the high-value pipeline.",
        _segment_quotes(conn, "l.created_via_channel = ?", (pod,)),
    )

    # F2 — message-persona resonance
    maya_mwr_ids = lead_ids("persona = ? AND seed_label_theme_primary = ?", (maya, mwr))
    f2 = FindingContext(
        "F2",
        "Message-persona resonance",
        "ad_copy_variants",
        f"Maya (mid-market RevOps) leads on a manual-work-reduction message "
        f"close at {cw('l.persona = ? AND l.seed_label_theme_primary = ?', (maya, mwr)):.0%}; "
        f"the same message for every other persona closes at "
        f"{cw('l.persona != ? AND l.seed_label_theme_primary = ?', (maya, mwr)):.1%}.",
        _segment_quotes(
            conn, "l.persona = ? AND l.seed_label_theme_primary = ?", (maya, mwr)
        ),
        _corroboration(extraction, snippets, maya_mwr_ids, mwr),
    )

    # F3 — multi-touch journey
    path_ids = _f3_path_lead_ids(conn)
    placeholders = ",".join("?" * len(path_ids)) or "''"
    path_cw = _scalar(
        conn,
        f"SELECT AVG(outcome = ?) FROM outcomes WHERE lead_id IN ({placeholders})",
        (won, *path_ids),
    )
    overall_cw = _scalar(conn, "SELECT AVG(outcome = ?) FROM outcomes", (won,))
    f3 = FindingContext(
        "F3",
        "Multi-touch journey",
        "sequence_play",
        f"A podcast -> blog -> demo-request path within {F3_PATH_WITHIN_DAYS} days "
        f"({len(path_ids)} leads) closes at {path_cw:.0%}, against a "
        f"{overall_cw:.1%} dataset-wide rate.",
        _segment_quotes(
            conn,
            f"l.lead_id IN ({placeholders}) AND l.lead_id = fs.lead_id",
            tuple(path_ids),
        )
        if path_ids
        else [],
    )

    # F4 — ICP fit vs volume
    bf_where = "first_touch_utm_campaign = ?"
    bad_share = _scalar(
        conn,
        "SELECT AVG((o.outcome IN (?, ?)) OR (o.outcome = ? AND o.sub_reason = ?)) "
        "FROM leads l JOIN outcomes o ON o.lead_id = l.lead_id "
        "WHERE l.first_touch_utm_campaign = ?",
        (
            Outcome.DISQUALIFIED.value,
            Outcome.GHOSTED.value,
            Outcome.CLOSED_LOST.value,
            F4_BAD_CLOSED_LOST_SUB_REASON,
            F4_TARGET_CAMPAIGN,
        ),
    )
    bf_count = len(lead_ids(bf_where, (F4_TARGET_CAMPAIGN,)))
    bf_icp = _scalar(
        conn,
        "SELECT AVG(icp_fit_score) FROM leads WHERE first_touch_utm_campaign = ?",
        (F4_TARGET_CAMPAIGN,),
    )
    all_icp = _scalar(conn, "SELECT AVG(icp_fit_score) FROM leads", ())
    f4 = FindingContext(
        "F4",
        "ICP fit vs volume",
        "icp_refinement",
        f"The {F4_TARGET_CAMPAIGN} campaign ({bf_count} leads, the largest by "
        f"volume) shows a {bad_share:.0%} bad-outcome share (disqualified, "
        f"ghosted, or lost as wrong-fit). Mean ICP fit {bf_icp:.0f} vs "
        f"{all_icp:.0f} dataset-wide.",
        _segment_quotes(conn, "l.first_touch_utm_campaign = ?", (F4_TARGET_CAMPAIGN,)),
    )

    # F5 — compliance resonance (secondary)
    pat_comp_ids = lead_ids(
        "persona = ? AND seed_label_theme_primary = ?", (patricia, comp)
    )
    f5 = FindingContext(
        "F5",
        "Compliance resonance",
        "ad_copy_variants",
        f"Patricia (enterprise IT) leads on a compliance/security message close "
        f"at {cw('l.persona = ? AND l.seed_label_theme_primary = ?', (patricia, comp)):.0%}; "
        f"the same message for other personas closes at "
        f"{cw('l.persona != ? AND l.seed_label_theme_primary = ?', (patricia, comp)):.1%}.",
        _segment_quotes(
            conn, "l.persona = ? AND l.seed_label_theme_primary = ?", (patricia, comp)
        ),
        _corroboration(extraction, snippets, pat_comp_ids, comp),
    )
    return [f1, f2, f3, f4, f5]


# =============================================================================
# Artifact generation
# =============================================================================


def _artifact_user_msg(ctx: FindingContext) -> str:
    quotes = "\n".join(f'- "{q}"' for q in ctx.example_snippets) or "(none available)"
    return (
        f"FINDING {ctx.finding_id} — {ctx.title}\n"
        f"{ctx.stat_summary}\n\n"
        f"Real buyer quotes from this segment:\n{quotes}\n\n"
        f"{ctx.extra}"
        f"Draft a {_ARTIFACT_TYPE_HUMAN[ctx.artifact_type]}."
    )


def generate_artifact(client, ctx: FindingContext, model: str) -> dict:
    text = _complete(
        client,
        model,
        ARTIFACT_SYSTEM,
        _artifact_user_msg(ctx),
        max_tokens=4096,
        temperature=0.3,
    )
    body = _loads_lenient(text)
    return {
        "finding_id": ctx.finding_id,
        "artifact_type": ctx.artifact_type,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": model,
        "title": body.get("title", ctx.title),
        "headline_insight": body.get("headline_insight", ""),
        "rationale": body.get("rationale", ""),
        "sections": body.get("sections", []),
    }


# =============================================================================
# Rendering + output
# =============================================================================


def render_artifact_markdown(artifact: dict) -> str:
    lines = [
        f"# {artifact['title']}",
        "",
        f"> {artifact['headline_insight']}",
        "",
        f"*{artifact['artifact_type'].replace('_', ' ').title()} — generated "
        f"from Finding {artifact['finding_id']} by `{artifact['model']}` on "
        f"{artifact['generated_at']}.*",
        "",
        artifact["rationale"],
        "",
    ]
    for section in artifact["sections"]:
        lines.append(f"## {section['heading']}")
        lines.append("")
        body = section["body"]
        if isinstance(body, list):
            lines.extend(f"- {item}" for item in body)
        else:
            lines.append(str(body))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_resonance_markdown(report: dict) -> str:
    agreement = report["agreement"]
    stability = report["stability"]
    field_status = report.get("qualitative_fields")
    header_lines = [
        f"*CP4 resonance layer — `{report['model']}` over "
        f"{report['snippets']} free-text snippets, "
        f"generated {report['generated_at']}.*",
    ]
    # v1.5 transparency: when noise blanks qualitative fields, surface the
    # filter rate alongside the agreement number. v1 reports (pre-v1.5)
    # omit `qualitative_fields`; render falls back gracefully there.
    if field_status:
        header_lines += [
            "",
            f"*v1.5 methodology: empty-text fields excluded from extraction. "
            f"{field_status['empty_fields']} of {field_status['total_fields']} "
            f"qualitative fields ({field_status['empty_rate']:.1%}) were blank "
            f"(noise-layer missingness) and skipped.*",
        ]
    lines = [
        "# Resonance extraction report",
        "",
        *header_lines,
        "",
        "## Extraction vs seed labels",
        "",
        f"Claude's extracted primary theme matched the seed `ground_truth_themes` "
        f"on **{agreement['overall']:.1%}** of snippets "
        f"({agreement['matched']}/{agreement['total']}).",
        "",
        "| Seed theme | Agreement | n |",
        "| --- | --- | --- |",
    ]
    for theme, stat in agreement["per_theme"].items():
        lines.append(f"| {theme} | {stat['rate']:.0%} | {stat['total']} |")
    lines += ["", "## Cross-run stability", ""]
    if stability["unanimous_rate"] is None:
        lines.append("Single run — stability not measured.")
    else:
        lines.append(
            f"Across {stability['runs']} temperature-0 runs, "
            f"**{stability['unanimous_rate']:.1%}** of snippets received the "
            f"same primary theme in every run ({stability['counted']} scored)."
        )
    lines += ["", "## Extracted theme mix by persona", ""]
    for persona, mix in report["per_persona"].items():
        top = ", ".join(f"{theme} ({n})" for theme, n in mix[:3])
        lines.append(f"- **{persona}**: {top}")
    return "\n".join(lines).rstrip() + "\n"


def build_resonance_report(
    conn: sqlite3.Connection,
    extraction: dict[str, tuple | None],
    snippets: list[Snippet],
    agreement: dict,
    stability: dict,
    model: str,
) -> dict:
    persona_by_lead = dict(conn.execute("SELECT lead_id, persona FROM leads"))
    per_persona: dict[str, dict[str, int]] = {}
    for snippet in snippets:
        result = extraction.get(snippet.snippet_id)
        if result is None or result[0] is None:
            continue
        persona = persona_by_lead.get(snippet.lead_id, "unknown")
        per_persona.setdefault(persona, {})
        per_persona[persona][result[0]] = per_persona[persona].get(result[0], 0) + 1
    ranked = {
        persona: sorted(mix.items(), key=lambda kv: kv[1], reverse=True)
        for persona, mix in per_persona.items()
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": model,
        "snippets": len(snippets),
        # v1.5 reporting: pair the agreement number with the filter rate
        # so reviewers see what fraction of qualitative fields were
        # excluded by the empty-text filter (load_snippets).
        "qualitative_fields": count_qualitative_field_status(conn),
        "agreement": agreement,
        "stability": stability,
        "per_persona": ranked,
    }


def write_outputs(out_dir: str, artifacts: list[dict], resonance: dict) -> list[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for artifact in artifacts:
        stem = f"{artifact['finding_id']}_{artifact['artifact_type']}"
        (out / f"{stem}.json").write_text(json.dumps(artifact, indent=2) + "\n")
        (out / f"{stem}.md").write_text(render_artifact_markdown(artifact))
        written += [f"{stem}.json", f"{stem}.md"]
    (out / "resonance.json").write_text(json.dumps(resonance, indent=2) + "\n")
    (out / "resonance.md").write_text(render_resonance_markdown(resonance))
    written += ["resonance.json", "resonance.md"]
    return written


# =============================================================================
# CLI
# =============================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ica.insight",
        description="Run CP4 resonance extraction and generate GTM action artifacts.",
    )
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Input SQLite path.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Artifact output dir.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--stability-runs",
        type=int,
        default=DEFAULT_STABILITY_RUNS,
        help="Extraction passes; >1 enables the cross-run stability score.",
    )
    parser.add_argument("--extraction-model", default=EXTRACTION_MODEL)
    parser.add_argument("--artifact-model", default=ARTIFACT_MODEL)
    return parser


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _progress(done: int, total: int) -> None:
    if done % 10 == 0 or done == total:
        print(f"    batch {done}/{total}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _load_env()

    conn = sqlite3.connect(args.db_path)
    snippets = load_snippets(conn)
    print(f"Loaded {len(snippets)} free-text snippets from {args.db_path}")

    client = _make_client()

    runs: list[dict[str, tuple | None]] = []
    for run_index in range(max(1, args.stability_runs)):
        print(f"Extraction run {run_index + 1}/{max(1, args.stability_runs)}")
        runs.append(
            run_extraction(
                client,
                snippets,
                batch_size=args.batch_size,
                model=args.extraction_model,
                progress=_progress,
            )
        )

    agreement = agreement_score(runs[0], snippets)
    stability = stability_score(runs)
    print(f"  extraction agreement vs seed labels: {agreement['overall']:.1%}")
    if stability["unanimous_rate"] is not None:
        print(f"  cross-run stability: {stability['unanimous_rate']:.1%}")

    artifacts = []
    for ctx in build_finding_contexts(conn, runs[0], snippets):
        print(f"Generating artifact {ctx.finding_id} ({ctx.artifact_type})")
        artifacts.append(generate_artifact(client, ctx, args.artifact_model))

    resonance = build_resonance_report(
        conn, runs[0], snippets, agreement, stability, args.extraction_model
    )
    written = write_outputs(args.out_dir, artifacts, resonance)
    print(f"Wrote {len(written)} files to {args.out_dir}/")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
