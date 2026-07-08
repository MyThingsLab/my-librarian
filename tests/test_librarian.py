from __future__ import annotations

import json
from pathlib import Path

from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, PolicyResult

from conftest import FakeRunner, ScriptedEngine, SpyEngine, empty_fetch, fake_fetch
from mylibrarian.librarian import Librarian


class _AllowPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


def test_survey_skips_when_no_candidates(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = SpyEngine()
    librarian = Librarian(
        ledger=ledger, repo="owner/name", runner=FakeRunner(), engine=engine,
        policy=_AllowPolicy(), fetch=empty_fetch,
    )
    result = librarian.survey(1, "some task with no seed match")
    assert result.outcome == "skipped"
    assert engine.calls == []  # Engine never called with nothing to judge

    entries = ledger.read(tool="mylibrarian", kind="library_survey")
    assert len(entries) == 1
    assert entries[0].outcome == "skipped"


def test_survey_success_records_ledger_and_recommendation(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    reply = json.dumps(
        {
            "recommended": [
                {"name": "markdown-it-py", "why": "solid", "install": "", "snippet": ""}
            ],
            "avoid": [],
            "confidence": "high",
        }
    )
    librarian = Librarian(
        ledger=ledger, repo="owner/name", runner=FakeRunner(),
        engine=ScriptedEngine(reply), policy=_AllowPolicy(), fetch=fake_fetch,
    )
    result = librarian.survey(1, "convert markdown to html")
    assert result.outcome == "success"
    assert result.candidate_count > 0

    entries = ledger.read(tool="mylibrarian", kind="library_survey")
    assert entries[0].outcome == "success"
    assert "markdown-it-py" in entries[0].data["recommended"]


def test_survey_comment_posts_via_runner(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    runner = FakeRunner()
    librarian = Librarian(
        ledger=ledger, repo="owner/name", runner=runner, engine=ScriptedEngine("{}"),
        policy=_AllowPolicy(), fetch=fake_fetch,
    )
    result = librarian.survey(1, "convert markdown to html", comment=True)
    assert result.comment_url is not None
    assert any(call[:2] == ["issue", "comment"] for call in runner.calls)


def test_survey_no_comment_without_repo(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    librarian = Librarian(
        ledger=ledger, repo=None, runner=FakeRunner(), engine=ScriptedEngine("{}"),
        policy=_AllowPolicy(), fetch=fake_fetch,
    )
    result = librarian.survey(1, "convert markdown to html", comment=True)
    assert result.comment_url is None


def test_survey_github_registry_uses_runner(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    runner = FakeRunner()
    librarian = Librarian(
        ledger=ledger, repo="owner/name", runner=runner, engine=ScriptedEngine("{}"),
        policy=_AllowPolicy(), fetch=fake_fetch, registries=("pypi", "npm", "github"),
    )
    librarian.survey(1, "convert markdown to html")
    assert any(call[:2] == ["search", "repos"] for call in runner.calls)
