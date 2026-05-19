"""Synthetic data generator components.

Top-down causal generation: sample (persona, channel, theme), then play
the journey forward through touchpoints, free-text, sales notes, outcome.

Pattern injectors live in seed.py as explicit, readable skews keyed to
the aha-pattern smoke tests in tests/test_aha_patterns.py.
"""
