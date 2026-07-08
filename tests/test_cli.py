from __future__ import annotations

from pathlib import Path

import pytest

from mylibrarian import cli


def test_cli_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_cli_rejects_unknown_registry(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(
            [
                "survey",
                "--issue", "1",
                "--task", "convert markdown to html",
                "--registries", "bogus",
                "--ledger", str(tmp_path / "ledger.jsonl"),
            ]
        )


def test_cli_survey_skips_and_prints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from conftest import empty_fetch

    real_librarian_cls = cli.Librarian

    def _patched(*args, **kwargs):  # noqa: ANN002, ANN003
        kwargs["fetch"] = empty_fetch
        return real_librarian_cls(*args, **kwargs)

    monkeypatch.setattr(cli, "Librarian", _patched)

    code = cli.main(
        [
            "survey",
            "--issue", "1",
            "--task", "convert markdown to html",
            "--ledger", str(tmp_path / "ledger.jsonl"),
            "--json",
        ]
    )
    assert code == 0
