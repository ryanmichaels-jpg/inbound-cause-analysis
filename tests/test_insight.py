"""insight.py — hermetic tests. The Claude call (_complete) is monkeypatched,
so these exercise the real batching / parsing / scoring / rendering logic
with no network and no API key."""

from ica import insight
from ica.insight import Snippet


def _snip(snippet_id, text, seed):
    return Snippet(snippet_id, "form", f"L-{snippet_id}", text, tuple(seed))


def test_batch_snippets_splits_evenly_and_remainder():
    snippets = [_snip(str(i), "x", ()) for i in range(7)]
    batches = insight.batch_snippets(snippets, 3)
    assert [len(b) for b in batches] == [3, 3, 1]


def test_parse_extraction_response_aligns_to_batch():
    text = (
        '[{"id": 1, "primary": "data_quality", "secondary": null}, '
        '{"id": 2, "primary": "manual_work_reduction", "secondary": "data_quality"}]'
    )
    assert insight.parse_extraction_response(text, 2) == [
        ("data_quality", None),
        ("manual_work_reduction", "data_quality"),
    ]


def test_parse_extraction_response_tolerates_code_fences():
    text = '```json\n[{"id": 1, "primary": "forecasting_accuracy", "secondary": null}]\n```'
    assert insight.parse_extraction_response(text, 1) == [("forecasting_accuracy", None)]


def test_parse_extraction_response_drops_unknown_theme_and_missing_id():
    text = '[{"id": 1, "primary": "not_a_real_theme", "secondary": null}]'
    # snippet 1 gets an invalid theme -> None; snippet 2 omitted -> None
    assert insight.parse_extraction_response(text, 2) == [(None, None), None]


def test_agreement_score_overall_and_per_theme():
    snippets = [
        _snip("a", "x", ("manual_work_reduction",)),
        _snip("b", "x", ("data_quality",)),
        _snip("c", "x", ("data_quality",)),
    ]
    extraction = {
        "a": ("manual_work_reduction", None),  # match
        "b": ("manual_work_reduction", None),  # miss
        "c": None,  # unscored — model omitted it
    }
    score = insight.agreement_score(extraction, snippets)
    assert score["matched"] == 1 and score["total"] == 2
    assert score["overall"] == 0.5
    assert score["per_theme"]["data_quality"] == {"matched": 0, "total": 1, "rate": 0.0}


def test_stability_score_counts_cross_run_unanimity():
    runs = [
        {"a": ("x", None), "b": ("y", None)},
        {"a": ("x", None), "b": ("z", None)},
        {"a": ("x", None), "b": ("y", None)},
    ]
    score = insight.stability_score(runs)
    assert score["runs"] == 3 and score["counted"] == 2
    assert score["unanimous_rate"] == 0.5  # 'a' unanimous, 'b' not


def test_stability_score_single_run_is_unmeasured():
    assert insight.stability_score([{"a": ("x", None)}])["unanimous_rate"] is None


def test_extract_batch_maps_response_to_snippet_ids(monkeypatch):
    batch = [_snip("S1", "manual toil", ()), _snip("S2", "dupes everywhere", ())]
    canned = (
        '[{"id": 1, "primary": "manual_work_reduction", "secondary": null}, '
        '{"id": 2, "primary": "data_quality", "secondary": null}]'
    )
    monkeypatch.setattr(insight, "_complete", lambda *a, **k: canned)
    assert insight.extract_batch(None, batch, "model") == {
        "S1": ("manual_work_reduction", None),
        "S2": ("data_quality", None),
    }


def test_run_extraction_covers_every_batch(monkeypatch):
    snippets = [_snip(f"S{i}", "x", ()) for i in range(5)]
    monkeypatch.setattr(
        insight,
        "_complete",
        lambda *a, **k: '[{"id": 1, "primary": "rep_efficiency", "secondary": null}]',
    )
    result = insight.run_extraction(None, snippets, batch_size=2, model="m")
    assert set(result) == {f"S{i}" for i in range(5)}


def test_render_artifact_markdown_structure():
    artifact = {
        "finding_id": "F2",
        "artifact_type": "ad_copy_variants",
        "generated_at": "2026-05-21T00:00:00+00:00",
        "model": "claude-sonnet-4-6",
        "title": "Maya ad copy",
        "headline_insight": "RevOps leaders convert on manual-toil messaging.",
        "rationale": "The segment closes 8x higher.",
        "sections": [
            {"heading": "Variant A", "body": "Stop the copy-paste."},
            {"heading": "Notes", "body": ["targets Maya", "use on LinkedIn"]},
        ],
    }
    md = insight.render_artifact_markdown(artifact)
    assert md.startswith("# Maya ad copy")
    assert "> RevOps leaders convert on manual-toil messaging." in md
    assert "## Variant A" in md
    assert "- targets Maya" in md


def test_generate_artifact_wraps_response_with_metadata(monkeypatch):
    ctx = insight.FindingContext("F1", "Channel quality", "content_brief", "stats here")
    canned = (
        '{"title": "Double down on podcasts", "headline_insight": "Podcasts win.", '
        '"rationale": "30% vs 3%.", "sections": [{"heading": "Plan", "body": "Do it."}]}'
    )
    monkeypatch.setattr(insight, "_complete", lambda *a, **k: canned)
    artifact = insight.generate_artifact(None, ctx, "claude-sonnet-4-6")
    assert artifact["finding_id"] == "F1"
    assert artifact["artifact_type"] == "content_brief"
    assert artifact["model"] == "claude-sonnet-4-6"
    assert artifact["title"] == "Double down on podcasts"
    assert artifact["generated_at"]  # stamped
