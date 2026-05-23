"""cli.py — argument handling and dispatch tests. generate() is stubbed so
these stay fast (the real pipeline is exercised by the generator tests)."""

import pytest

from ica import cli
from ica.generator.seed import DEFAULT_DB_PATH
from ica.taxonomy import CLEAN, DEFAULT_SEED, REALISTIC

_FAKE_COUNTS = {
    "leads": 2500,
    "touchpoints": 8736,
    "form_submissions": 2500,
    "sales_notes": 236,
    "outcomes": 2500,
}


@pytest.fixture
def captured_generate(monkeypatch):
    """Replace cli.generate with a stub that records its kwargs."""
    calls: dict[str, object] = {}

    def _stub(*, seed, db_path, noise_profile):
        calls["seed"] = seed
        calls["db_path"] = db_path
        calls["noise_profile"] = noise_profile
        return _FAKE_COUNTS

    monkeypatch.setattr(cli, "generate", _stub)
    return calls


def test_defaults_dispatch_to_generate(captured_generate):
    assert cli.main([]) == 0
    assert captured_generate["seed"] == DEFAULT_SEED
    assert captured_generate["db_path"] == DEFAULT_DB_PATH
    # v1.5: default noise is REALISTIC.
    assert captured_generate["noise_profile"] == REALISTIC


def test_seed_and_db_path_flags(captured_generate):
    assert cli.main(["--seed", "7", "--db-path", "/tmp/ica_x.db"]) == 0
    assert captured_generate["seed"] == 7
    assert captured_generate["db_path"] == "/tmp/ica_x.db"


# v1.5 noise-control tests --------------------------------------------------


def test_clean_flag_uses_clean_profile(captured_generate):
    assert cli.main(["--clean"]) == 0
    assert captured_generate["noise_profile"] == CLEAN


def test_noise_zero_uses_clean_profile(captured_generate):
    assert cli.main(["--noise", "0"]) == 0
    assert captured_generate["noise_profile"] == CLEAN


def test_noise_multiplier_scales_realistic(captured_generate):
    assert cli.main(["--noise", "2"]) == 0
    assert captured_generate["noise_profile"] == REALISTIC.scaled(2.0)


def test_clean_and_noise_are_mutually_exclusive(capsys):
    # argparse exits with SystemExit(2) when mutually exclusive args clash.
    with pytest.raises(SystemExit):
        cli.main(["--clean", "--noise", "2"])


@pytest.mark.parametrize(
    "argv",
    [
        ["--total-leads", "5000"],
        ["--start-date", "2026-02-01"],
        ["--end-date", "2026-05-01"],
    ],
)
def test_locked_knobs_rejected(argv, capsys):
    assert cli.main(argv) == 2
    err = capsys.readouterr().err
    assert "not supported in v1" in err
    assert "Known v1 limitations" in err


def test_locked_knob_does_not_run_generate(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("generate must not run when a locked knob is passed")

    monkeypatch.setattr(cli, "generate", _boom)
    assert cli.main(["--total-leads", "9999"]) == 2
