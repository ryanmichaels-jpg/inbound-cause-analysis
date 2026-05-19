"""Schema integrity and row-count smoke tests.

The five statistical contract assertions for the aha patterns live in
test_aha_patterns.py. This file covers structural checks: are all FK
relationships intact, do per-table row counts hit expected bounds, do
enum-valued columns only contain values from taxonomy.
"""
