from __future__ import annotations

import json

import pytest

# Shared fakes come from mythings.testing (plain imports; aliased fixture
# re-export + getfixturevalue wrapper per core docs/CONVENTIONS.md).
from mythings.testing import FakeGh, ScriptedEngine
from mythings.testing import clean_git_env as _shared_clean_git_env  # noqa: F401
from mythings.testing import fake_fetch as _fake_fetch

from mylibrarian.registries import NPM_SEARCH_ENDPOINT, PYPI_JSON_ENDPOINT

__all__ = ["ScriptedEngine"]


@pytest.fixture(autouse=True)
def _clean_git_env(request: pytest.FixtureRequest) -> None:
    # Consistency with the fleet's other test suites (harmless here — no git
    # subprocess is spawned by this tool, but keeps the fixture set uniform).
    request.getfixturevalue("_shared_clean_git_env")


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


# Insertion order matters: the stubbed package wins before the any-other-PyPI
# fallback ("no metadata").
fake_fetch = _fake_fetch(
    {
        NPM_SEARCH_ENDPOINT: NPM_RESULTS,
        PYPI_JSON_ENDPOINT.format(name="markdown-it-py"): PYPI_MARKDOWN_IT_PY,
        "https://pypi.org/pypi/": {"info": {}, "releases": {}},
    }
)

empty_fetch = _fake_fetch(
    {NPM_SEARCH_ENDPOINT: {"objects": []}},
    default=json.dumps({"info": {}, "releases": {}}).encode(),
)


def fake_gh(comment_url: str = "https://github.com/owner/name/issues/1#comment") -> FakeGh:
    return FakeGh(
        {
            ("issue", "comment"): comment_url + "\n",
            ("search", "repos"): json.dumps([]),
        }
    )
