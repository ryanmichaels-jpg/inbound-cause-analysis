"""copy_bank.py tests — including the lexical-separation discipline check
that keeps theme vocabularies machine-separable for the CP4 LLM eval."""

import numpy as np

from ica.generator.copy_bank import (
    _CHANNEL_FLAVOR,
    _FORM_ANSWERS,
    Snippet,
    form_answer,
    form_question,
    iter_bank_snippets,
    sales_note,
)
from ica.taxonomy import (
    THEME_ANCHOR_VOCAB,
    THEME_BRIDGE_PAIRS,
    Channel,
    FormType,
    Persona,
    Theme,
)


def _themes_present(text: str) -> set[Theme]:
    """Themes whose anchor vocabulary appears in `text` (case-insensitive)."""
    low = text.lower()
    return {
        theme
        for theme, anchors in THEME_ANCHOR_VOCAB.items()
        if any(anchor in low for anchor in anchors)
    }


# --- lexical-separation discipline -------------------------------------------


def test_pure_snippets_carry_exactly_their_theme():
    for snip in iter_bank_snippets():
        if snip.secondary_theme is not None:
            continue
        present = _themes_present(snip.text)
        assert present == {snip.primary_theme}, (
            f"pure snippet must carry only {snip.primary_theme.value}, "
            f"carries {sorted(t.value for t in present)}: {snip.text!r}"
        )


def test_bridge_snippets_carry_exactly_their_two_themes():
    for snip in iter_bank_snippets():
        if snip.secondary_theme is None:
            continue
        present = _themes_present(snip.text)
        assert present == {snip.primary_theme, snip.secondary_theme}, (
            f"bridge snippet must carry {snip.primary_theme.value} + "
            f"{snip.secondary_theme.value}, carries "
            f"{sorted(t.value for t in present)}: {snip.text!r}"
        )


def test_bridge_pairs_are_taxonomy_sanctioned():
    for snip in iter_bank_snippets():
        if snip.secondary_theme is None:
            continue
        pair = (snip.primary_theme, snip.secondary_theme)
        assert pair in THEME_BRIDGE_PAIRS, f"{pair} not in THEME_BRIDGE_PAIRS"


def test_bridge_fraction_near_thirty_percent():
    snips = iter_bank_snippets()
    bridges = sum(1 for s in snips if s.secondary_theme is not None)
    frac = bridges / len(snips)
    assert 0.20 <= frac <= 0.40, f"bridge fraction {frac:.2f} outside 0.20-0.40"


# --- channel flavor ----------------------------------------------------------


def test_channel_flavor_openers_are_anchor_free():
    for openers in _CHANNEL_FLAVOR.values():
        for opener in openers:
            assert _themes_present(opener) == set(), opener


# --- API ---------------------------------------------------------------------


def test_form_answer_returns_themed_snippet():
    rng = np.random.default_rng(0)
    for persona, theme in _FORM_ANSWERS:
        snip = form_answer(persona, Channel.ORGANIC_SEARCH, theme, rng)
        assert isinstance(snip, Snippet)
        assert snip.primary_theme == theme
        assert snip.ground_truth_themes[0] == theme


def test_sales_note_returns_themed_snippet():
    rng = np.random.default_rng(0)
    snip = sales_note(Theme.MANUAL_WORK_REDUCTION, "rep_note", rng)
    assert isinstance(snip, Snippet)
    assert snip.primary_theme == Theme.MANUAL_WORK_REDUCTION


def test_form_question_returns_nonblank_string():
    rng = np.random.default_rng(0)
    for form_type in FormType:
        question = form_question(form_type, rng)
        assert isinstance(question, str)
        assert question.strip()


def test_selection_is_deterministic():
    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)
    for _ in range(50):
        snip_a = form_answer(
            Persona.MAYA, Channel.LINKEDIN_PAID, Theme.MANUAL_WORK_REDUCTION, rng_a
        )
        snip_b = form_answer(
            Persona.MAYA, Channel.LINKEDIN_PAID, Theme.MANUAL_WORK_REDUCTION, rng_b
        )
        assert snip_a == snip_b


def test_ground_truth_themes_ordering():
    pure = Snippet("x", Theme.DATA_QUALITY)
    assert pure.ground_truth_themes == [Theme.DATA_QUALITY]
    bridge = Snippet("x", Theme.DATA_QUALITY, Theme.MANUAL_WORK_REDUCTION)
    assert bridge.ground_truth_themes == [
        Theme.DATA_QUALITY,
        Theme.MANUAL_WORK_REDUCTION,
    ]
