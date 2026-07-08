# my-librarian

[![CI](https://github.com/MyThingsLab/my-librarian/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-librarian/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-librarian/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-librarian) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Given a task ("convert Markdown to HTML", "typeset a PDF"), discovers
existing community-maintained libraries/CLIs live (PyPI, npm, optionally
GitHub) and recommends which one(s) to reach for instead of reimplementing
— e.g. `markdown-it-py`/`pandoc` for document conversion. A build-vs-buy
check for [MyThingsLab](../my-things-core) tools (and humans) to run before
writing new code.

## How it works

Deterministic pre-work:

1. Read the task issue (label `my-librarian`) and build query terms (the
   same naive tokenizer MySearcher/MyResearcher use).
2. Retrieve candidates over LLM-free HTTP from the selected registries
   (`--registries`, default `pypi,npm`):
   - **npm** — `registry.npmjs.org/-/v1/search`, keyless.
   - **PyPI** — no free-text search API exists anymore, so a small curated
     seed table maps common task keywords to well-known package names,
     enriched via `pypi.org/pypi/<name>/json` (keyless).
   - **GitHub** — repo search via the existing `gh` CLI Runner, opt-in.
3. Normalize + dedupe, score by query-term overlap + popularity + recency,
   with license permissiveness downranking (never dropping) copyleft
   candidates, and cap to the top N (default 10).

If at least one candidate is found, **one Engine call** recommends which to
use, with trade-offs, a usage snippet, and any to avoid — citing only
package names from the shortlist. Against `NoopEngine`, the reply is empty
and the shortlist is posted verbatim, sorted by the deterministic score.

Read-only: no `Workspace`, no PR, no code edits — MyLibrarian recommends, it
never adopts a dependency itself. The only side effect is an optional
`--comment` posting the survey to the issue, routed through `Policy`
(`Guard` default). Writes exactly one `kind=library_survey` ledger entry per
run.

## Usage

```bash
mylibrarian survey --issue 12 --task "convert markdown to html" --source .
mylibrarian survey --issue 12 --task "..." --repo owner/name --comment
mylibrarian survey --issue 12 --task "..." --registries pypi,npm,github --engine claude-cli
```

## In the fleet loop

Standalone today — a build-vs-buy check any tool-build issue can consult
before writing new code, per the
[design doc](../my-things-core/docs/tools/my-librarian.md). See the
[org README](../README.md) for how the shipped tools chain together.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
