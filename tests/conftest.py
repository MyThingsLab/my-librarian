from __future__ import annotations

import json

import pytest
from mythings.engine import EngineRequest, EngineResult

from mylibrarian.registries import NPM_SEARCH_ENDPOINT, PYPI_JSON_ENDPOINT


@pytest.fixture(autouse=True)
def _clean_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Consistency with the fleet's other test suites (harmless here — no git
    # subprocess is spawned by this tool, but keeps the fixture set uniform).
    for var in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.delenv(var, raising=False)


NPM_RESULTS = {
    "objects": [
        {
            "package": {
                "name": "markdown-it",
                "description": "Markdown parser done right",
                "license": "MIT",
                "date": "2024-01-01T00:00:00.000Z",
                "links": {"npm": "https://www.npmjs.com/package/markdown-it"},
            },
            "score": {"detail": {"popularity": 0.8}},
        }
    ]
}

PYPI_MARKDOWN_IT_PY = {
    "info": {
        "name": "markdown-it-py",
        "summary": "Python port of markdown-it",
        "license": "MIT",
        "project_url": "https://pypi.org/project/markdown-it-py/",
    },
    "releases": {"1.0.0": [{"upload_time_iso_8601": "2023-06-01T00:00:00Z"}]},
}


_PYPI_PREFIX = "https://pypi.org/pypi/"


def fake_fetch(url: str, *, data: bytes | None = None, headers: dict | None = None) -> bytes:
    if url.startswith(NPM_SEARCH_ENDPOINT):
        return json.dumps(NPM_RESULTS).encode()
    if url == PYPI_JSON_ENDPOINT.format(name="markdown-it-py"):
        return json.dumps(PYPI_MARKDOWN_IT_PY).encode()
    if url.startswith(_PYPI_PREFIX):
        # Any other seed name the fixture didn't stub — no metadata.
        return json.dumps({"info": {}, "releases": {}}).encode()
    raise AssertionError(f"unexpected fetch url: {url}")


def empty_fetch(url: str, *, data: bytes | None = None, headers: dict | None = None) -> bytes:
    if url.startswith(NPM_SEARCH_ENDPOINT):
        return json.dumps({"objects": []}).encode()
    return json.dumps({"info": {}, "releases": {}}).encode()


class ScriptedEngine:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        return EngineResult(text=self.reply)


class SpyEngine:
    def __init__(self) -> None:
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        return EngineResult(text="")


class FakeRunner:
    def __init__(self, comment_url: str = "https://github.com/owner/name/issues/1#comment") -> None:
        self.calls: list[list[str]] = []
        self._comment_url = comment_url

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        if argv[:2] == ["issue", "comment"]:
            return self._comment_url + "\n"
        if argv[:2] == ["search", "repos"]:
            return json.dumps([])
        raise AssertionError(f"unexpected gh call: {argv}")
