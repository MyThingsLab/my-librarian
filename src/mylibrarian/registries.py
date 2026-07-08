from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from mythings.github import Runner

# The one network boundary. Default shells out to urllib; tests inject a fake so
# the HTTP call is the only thing mocked (same discipline as engine/github Runners).
Fetcher = Callable[..., bytes]

NPM_SEARCH_ENDPOINT = "https://registry.npmjs.org/-/v1/search"
PYPI_JSON_ENDPOINT = "https://pypi.org/pypi/{name}/json"

# PyPI retired its free-text search endpoint; a small curated seed table maps
# common task keywords to well-known package names, enriched via the JSON API
# (per-package, keyless) rather than guessed at query time.
PYPI_SEED: dict[str, tuple[str, ...]] = {
    "markdown": ("markdown-it-py", "mistune", "Markdown"),
    "html": ("markdown-it-py", "beautifulsoup4", "lxml"),
    "pdf": ("pypandoc", "reportlab", "weasyprint"),
    "typeset": ("pypandoc",),
    "yaml": ("PyYAML", "ruamel.yaml"),
    "json": ("orjson",),
    "csv": ("pandas",),
    "excel": ("openpyxl", "xlsxwriter"),
    "http": ("httpx", "requests"),
    "cli": ("click", "typer"),
    "test": ("pytest",),
    "template": ("jinja2",),
    "config": ("pydantic",),
    "date": ("python-dateutil", "pendulum"),
}

_PERMISSIVE_LICENSES = frozenset(
    {"mit", "bsd", "bsd-2-clause", "bsd-3-clause", "apache-2.0", "isc"}
)
_COPYLEFT_LICENSES = frozenset({"gpl", "gpl-2.0", "gpl-3.0", "lgpl", "agpl-3.0", "agpl"})

# A short, deterministic stopword set — same discipline as MyResearcher's
# tokenizer (no NLP dependency, harness: dependency-free runtime).
_STOPWORDS = frozenset(
    "a an and are as at be by convert for from how in into is it of on or the "
    "to via with what why tool library".split()
)


@dataclass(frozen=True)
class Candidate:
    name: str
    registry: str  # "pypi" | "npm" | "github"
    description: str
    license: str  # normalized lowercase id, or "unknown"
    popularity: float  # 0.0-1.0, registry-specific normalization
    url: str
    last_release: str | None = None  # ISO date, if known


def _http(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https endpoints
        return resp.read()


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    word: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            word.append(ch)
        elif word:
            out.append("".join(word))
            word = []
    if word:
        out.append("".join(word))
    return out


def build_query(title: str, body: str = "") -> str:
    seen: set[str] = set()
    terms: list[str] = []
    for tok in tokenize(title) + tokenize(body):
        if tok in _STOPWORDS or len(tok) < 2 or tok in seen:
            continue
        seen.add(tok)
        terms.append(tok)
    return " ".join(terms[:12])


def normalize_license(raw: str | None) -> str:
    if not raw:
        return "unknown"
    text = raw.strip().lower()
    for known in _PERMISSIVE_LICENSES | _COPYLEFT_LICENSES:
        if known in text:
            return known
    return text or "unknown"


def is_copyleft(license_id: str) -> bool:
    return license_id in _COPYLEFT_LICENSES


def search_npm(query: str, *, fetch: Fetcher = _http, limit: int = 10) -> list[Candidate]:
    if not query:
        return []
    params = urllib.parse.urlencode({"text": query, "size": limit})
    raw = fetch(f"{NPM_SEARCH_ENDPOINT}?{params}")
    payload = json.loads(raw)
    candidates: list[Candidate] = []
    for obj in payload.get("objects", []):
        pkg = obj.get("package", {})
        name = pkg.get("name")
        if not name:
            continue
        score = obj.get("score", {}).get("detail", {}).get("popularity", 0.0)
        candidates.append(
            Candidate(
                name=name,
                registry="npm",
                description=(pkg.get("description") or "").strip(),
                license=normalize_license(pkg.get("license")),
                popularity=float(score or 0.0),
                url=pkg.get("links", {}).get("npm", f"https://www.npmjs.com/package/{name}"),
                last_release=pkg.get("date"),
            )
        )
    return candidates


def _seed_names(query: str) -> list[str]:
    tokens = set(tokenize(query))
    names: list[str] = []
    seen: set[str] = set()
    for keyword, packages in PYPI_SEED.items():
        if keyword not in tokens:
            continue
        for name in packages:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def search_pypi(query: str, *, fetch: Fetcher = _http, limit: int = 10) -> list[Candidate]:
    names = _seed_names(query)[:limit]
    candidates: list[Candidate] = []
    for name in names:
        raw = fetch(PYPI_JSON_ENDPOINT.format(name=name))
        payload = json.loads(raw)
        info = payload.get("info", {})
        releases = payload.get("releases", {})
        last_release = None
        for files in releases.values():
            for f in files:
                upload_time = f.get("upload_time_iso_8601") or f.get("upload_time")
                if upload_time and (last_release is None or upload_time > last_release):
                    last_release = upload_time
        candidates.append(
            Candidate(
                name=info.get("name", name),
                registry="pypi",
                description=(info.get("summary") or "").strip(),
                license=normalize_license(info.get("license")),
                # Curated seed matches are already known-good; fixed high
                # popularity so they compete fairly against npm's live score.
                popularity=0.9,
                url=info.get("project_url") or f"https://pypi.org/project/{name}/",
                last_release=last_release,
            )
        )
    return candidates


def search_github(query: str, *, runner: Runner, limit: int = 10) -> list[Candidate]:
    if not query:
        return []
    argv = [
        "search",
        "repos",
        query,
        "--limit",
        str(limit),
        "--json",
        "fullName,description,url,stargazersCount,updatedAt",
    ]
    rows = json.loads(runner(argv))
    candidates: list[Candidate] = []
    for row in rows:
        stars = row.get("stargazersCount") or 0
        candidates.append(
            Candidate(
                name=row.get("fullName", ""),
                registry="github",
                description=(row.get("description") or "").strip(),
                license="unknown",  # not requested from the search API; keep it honest
                popularity=min(stars / 10_000, 1.0),
                url=row.get("url", ""),
                last_release=row.get("updatedAt"),
            )
        )
    return candidates


def _score(candidate: Candidate, query_tokens: set[str]) -> tuple[float, float, str]:
    haystack = set(tokenize(candidate.name)) | set(tokenize(candidate.description))
    overlap = len(query_tokens & haystack)
    downrank = -0.5 if is_copyleft(candidate.license) else 0.0
    return (overlap + candidate.popularity + downrank, candidate.popularity, candidate.name)


def retrieve(
    title: str,
    body: str = "",
    *,
    registries: tuple[str, ...] = ("pypi", "npm"),
    top: int = 10,
    fetch: Fetcher = _http,
    gh_runner: Runner | None = None,
) -> list[Candidate]:
    query = build_query(title, body)
    found: list[Candidate] = []
    if "pypi" in registries:
        found += search_pypi(query, fetch=fetch, limit=top)
    if "npm" in registries:
        found += search_npm(query, fetch=fetch, limit=top)
    if "github" in registries and gh_runner is not None:
        found += search_github(query, runner=gh_runner, limit=top)

    deduped: dict[str, Candidate] = {}
    for cand in found:
        key = f"{cand.registry}:{cand.name}".lower()
        deduped.setdefault(key, cand)

    query_tokens = set(tokenize(query))
    ranked = sorted(deduped.values(), key=lambda c: _score(c, query_tokens), reverse=True)
    return ranked[:top]
