"""Command-line entry point — invoked via `python -m ica.cli`.

A thin argparse wrapper over generator/seed.py:generate(). v1 supports
--seed and --db-path. data-world.md §1 also lists --total-leads,
--start-date and --end-date; the generator is built for the locked
2,500-lead / Jan-Jun-2026 world, so those three are rejected with an
explanatory message (see README "Known v1 limitations") rather than
silently ignored.

Design notes (lighter-cadence, surfaced here): the CLI is flat — one
implicit action, no subcommand (the scaffold Makefile's `generate`
subcommand was dropped; the Makefile target is updated to match). The
path flag is --db-path, matching seed.generate()'s parameter (the
scaffold's --out was a placeholder).
"""

import argparse
import sys

from ica.generator.seed import DEFAULT_DB_PATH, generate
from ica.taxonomy import (
    DEFAULT_SEED,
    TIME_WINDOW_END,
    TIME_WINDOW_START,
    TOTAL_LEADS_DEFAULT,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ica.cli",
        description="Generate the ICA synthetic dataset into a SQLite database.",
        epilog=(
            "--total-leads / --start-date / --end-date are listed in "
            "data-world.md §1 but are LOCKED in v1 — see README "
            "'Known v1 limitations'."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed for a reproducible dataset (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"Output SQLite path (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--total-leads",
        type=int,
        help="LOCKED in v1 to 2500 — see README 'Known v1 limitations'.",
    )
    parser.add_argument(
        "--start-date",
        help="LOCKED in v1 — see README 'Known v1 limitations'.",
    )
    parser.add_argument(
        "--end-date",
        help="LOCKED in v1 — see README 'Known v1 limitations'.",
    )
    return parser


def _locked_knob_error(used: list[str]) -> str:
    return (
        f"error: {', '.join(used)} not supported in v1.\n"
        f"The generator is built for the locked {TOTAL_LEADS_DEFAULT}-lead "
        "world (channels.py asserts it) over the "
        f"{TIME_WINDOW_START} .. {TIME_WINDOW_END} window (taxonomy "
        "constants). --total-leads / --start-date / --end-date cannot "
        "change that in v1 — see README 'Known v1 limitations'. Re-run with "
        "--seed and/or --db-path only."
    )


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to seed.generate(). Returns the process exit
    code: 0 on success, 2 if a locked v1 knob was passed."""
    args = _build_parser().parse_args(argv)
    used_locked = [
        flag
        for flag, value in (
            ("--total-leads", args.total_leads),
            ("--start-date", args.start_date),
            ("--end-date", args.end_date),
        )
        if value is not None
    ]
    if used_locked:
        print(_locked_knob_error(used_locked), file=sys.stderr)
        return 2

    counts = generate(seed=args.seed, db_path=args.db_path)
    print(f"Generated {args.db_path}  (seed {args.seed})")
    for table, count in counts.items():
        print(f"  {table:<18}{count:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
