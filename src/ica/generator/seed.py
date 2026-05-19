"""Aha-pattern skew injectors.

Each function applies one of the five engineered skews from
`docs/aha-patterns.md`. Application order matters and is documented in
that doc's "Skew application order" section:

    Finding 4 -> Finding 1 -> Finding 2 -> Finding 3 -> Secondary Finding 5

Each skew function's docstring declares which test_aha_N_* assertion it
satisfies and which invariants from prior skews it must preserve.
"""
