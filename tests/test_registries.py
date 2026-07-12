from __future__ import annotations

import json
import urllib.error

from conftest import empty_fetch, fake_fetch
from mylibrarian.registries import (
    NPM_SEARCH_ENDPOINT,
    build_query,
    is_copyleft,
    normalize_license,
    retrieve,
    search_github,
    search_npm,
    search_pypi,
)


def test_build_query_drops_stopwords_and_dedupes() -> None:
    q = build_query("Convert Markdown to HTML", "how to convert markdown files")
    terms = q.split()
    assert "markdown" in terms and "html" in terms
    assert "convert" not in terms  # stopword
    assert "how" not in terms  # stopword
    assert terms.count("markdown") == 1  # deduped across title + body


def test_build_query_caps_at_npm_text_length() -> None:
    # A verbose but realistic task description tokenizes past npm's 64-char
    # `text` param limit; build_query must never hand back more than that.
    title = "lightweight CSS-only animation library"
    body = (
        "usable by copy-pasting inline CSS into a single self-contained "
        "HTML file, no JavaScript, no build step"
    )
    q = build_query(title, body)
    assert len(q) <= 64
    assert q  # still non-empty -- some terms fit


def test_search_npm_degrades_on_http_error() -> None:
    def raising_fetch(url: str, *, data: bytes | None = None, headers: dict | None = None) -> bytes:
        assert url.startswith(NPM_SEARCH_ENDPOINT)
        raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)

    assert search_npm("some query", fetch=raising_fetch) == []


def test_normalize_license() -> None:
    assert normalize_license("MIT License") == "mit"
    assert normalize_license("GNU GPLv3") == "gpl"
    assert normalize_license(None) == "unknown"


def test_is_copyleft() -> None:
    assert is_copyleft("gpl-3.0")
    assert not is_copyleft("mit")


def test_search_npm_parses_results() -> None:
    candidates = search_npm("markdown", fetch=fake_fetch)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.name == "markdown-it"
    assert c.registry == "npm"
    assert c.license == "mit"
    assert c.popularity == 0.8


def test_search_npm_empty() -> None:
    assert search_npm("markdown", fetch=empty_fetch) == []


def test_search_pypi_uses_seed_table() -> None:
    candidates = search_pypi("convert markdown to html", fetch=fake_fetch)
    names = [c.name for c in candidates]
    assert "markdown-it-py" in names
    hit = next(c for c in candidates if c.name == "markdown-it-py")
    assert hit.registry == "pypi"
    assert hit.license == "mit"
    assert hit.last_release == "2023-06-01T00:00:00Z"


def test_search_pypi_no_seed_match_returns_empty() -> None:
    assert search_pypi("something with no seed keyword", fetch=fake_fetch) == []


def test_search_github_parses_repo_search() -> None:
    def runner(argv: list[str]) -> str:
        assert argv[:2] == ["search", "repos"]
        return json.dumps(
            [
                {
                    "fullName": "markdown-it/markdown-it",
                    "description": "Markdown parser",
                    "url": "https://github.com/markdown-it/markdown-it",
                    "stargazersCount": 15000,
                    "updatedAt": "2024-01-01T00:00:00Z",
                }
            ]
        )

    candidates = search_github("markdown", runner=runner)
    assert len(candidates) == 1
    assert candidates[0].registry == "github"
    assert candidates[0].popularity == 1.0  # capped at 10k+ stars


def test_retrieve_merges_and_dedupes_across_registries() -> None:
    candidates = retrieve("convert markdown to html", fetch=fake_fetch, top=10)
    names = {(c.registry, c.name) for c in candidates}
    assert ("pypi", "markdown-it-py") in names
    assert ("npm", "markdown-it") in names


def test_retrieve_caps_at_top() -> None:
    candidates = retrieve("convert markdown to html", fetch=fake_fetch, top=1)
    assert len(candidates) == 1


def test_retrieve_downranks_copyleft_without_dropping() -> None:
    def fetch(url: str, *, data: bytes | None = None, headers: dict | None = None) -> bytes:
        if url.startswith("https://registry.npmjs.org"):
            return json.dumps(
                {
                    "objects": [
                        {
                            "package": {
                                "name": "gpl-tool",
                                "description": "markdown converter",
                                "license": "GPL-3.0",
                                "links": {"npm": "https://www.npmjs.com/package/gpl-tool"},
                            },
                            "score": {"detail": {"popularity": 0.99}},
                        },
                        {
                            "package": {
                                "name": "mit-tool",
                                "description": "markdown converter",
                                "license": "MIT",
                                "links": {"npm": "https://www.npmjs.com/package/mit-tool"},
                            },
                            "score": {"detail": {"popularity": 0.5}},
                        },
                    ]
                }
            ).encode()
        return json.dumps({"info": {}, "releases": {}}).encode()

    candidates = retrieve(
        "markdown converter", registries=("npm",), fetch=fetch, top=10
    )
    names = [c.name for c in candidates]
    assert "gpl-tool" in names  # never silently dropped
    assert names.index("mit-tool") < names.index("gpl-tool")  # but ranked below
