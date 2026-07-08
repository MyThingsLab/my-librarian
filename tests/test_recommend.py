from __future__ import annotations

import json

from mythings.engine import NoopEngine

from conftest import ScriptedEngine
from mylibrarian.recommend import render, synthesize
from mylibrarian.registries import Candidate

_CANDIDATES = [
    Candidate("markdown-it-py", "pypi", "Python port of markdown-it", "mit", 0.9, "https://x"),
    Candidate("markdown-it", "npm", "Markdown parser done right", "mit", 0.8, "https://y"),
]


def test_synthesize_parses_engine_json() -> None:
    reply = json.dumps(
        {
            "recommended": [
                {
                    "name": "markdown-it-py",
                    "why": "actively maintained, MIT",
                    "install": "pip install markdown-it-py",
                    "snippet": "from markdown_it import MarkdownIt",
                }
            ],
            "avoid": [],
            "confidence": "high",
        }
    )
    survey = synthesize(ScriptedEngine(reply), "convert markdown to html", _CANDIDATES)
    assert not survey.degraded
    assert survey.confidence == "high"
    assert [r.name for r in survey.recommended] == ["markdown-it-py"]


def test_synthesize_drops_invented_package() -> None:
    reply = json.dumps(
        {
            "recommended": [
                {"name": "markdown-it-py", "why": "real"},
                {"name": "totally-made-up", "why": "hallucinated"},
            ],
            "avoid": [],
            "confidence": "medium",
        }
    )
    survey = synthesize(ScriptedEngine(reply), "task", _CANDIDATES)
    assert [r.name for r in survey.recommended] == ["markdown-it-py"]


def test_synthesize_invalid_confidence_falls_back_to_low() -> None:
    reply = json.dumps({"recommended": [], "avoid": [], "confidence": "very high"})
    survey = synthesize(ScriptedEngine(reply), "task", _CANDIDATES)
    assert survey.confidence == "low"


def test_synthesize_noop_engine_degrades() -> None:
    survey = synthesize(NoopEngine(), "convert markdown to html", _CANDIDATES)
    assert survey.degraded
    assert survey.recommended == []
    assert survey.confidence == "low"


def test_synthesize_unparsable_reply_degrades() -> None:
    survey = synthesize(ScriptedEngine("not json"), "task", _CANDIDATES)
    assert survey.degraded


def test_render_includes_candidates_and_recommendation() -> None:
    reply = json.dumps(
        {
            "recommended": [
                {
                    "name": "markdown-it-py",
                    "why": "solid",
                    "install": "pip install x",
                    "snippet": "",
                }
            ],
            "avoid": [{"name": "markdown-it", "why": "js, not python"}],
            "confidence": "high",
        }
    )
    survey = synthesize(ScriptedEngine(reply), "convert markdown to html", _CANDIDATES)
    text = render(survey)
    assert "## Recommended" in text
    assert "markdown-it-py" in text
    assert "## Avoid" in text
    assert "## Candidates considered" in text


def test_render_degraded_notes_no_engine() -> None:
    survey = synthesize(NoopEngine(), "task", _CANDIDATES)
    text = render(survey)
    assert "No recommendation engine configured" in text
