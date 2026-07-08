# my-librarian — agent instructions

You are developing **my-librarian**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** given a task issue ("convert Markdown to HTML", "typeset a
  PDF"), discovers existing community-maintained packages/CLIs **live** (PyPI,
  npm, optionally GitHub) via LLM-free HTTP, then recommends which one(s) to
  depend on instead of reimplementing — a build-vs-buy check, not a research
  brief and not a project-history recommendation. See the design doc:
  [`my-things-core/docs/tools/my-librarian.md`](../my-things-core/docs/tools/my-librarian.md).
- **The single Engine call:** one per invocation, optional. "Given this task
  and a shortlist of discovered candidate packages, recommend which one(s) to
  use, with trade-offs and a usage snippet" → `{recommended, avoid,
  confidence}`, citing only package names present in the shortlist — never an
  invented package. Against `NoopEngine`, emits the shortlist verbatim, sorted
  by the deterministic popularity score, with no `why`/`snippet` — honest
  degrade, no synthesis.
- **Invariants / rules:** exactly one Engine call per run; all retrieval is
  deterministic, LLM-free HTTP (`urllib` + `json`, no SDK) — PyPI and npm need
  no key; GitHub search is opt-in via the existing `gh` Runner. The HTTP
  boundary is mocked in the default suite; any real-network test is
  `@pytest.mark.slow`. **Read-only** — no `Workspace`, no PR, no code edits;
  MyLibrarian recommends, it never adopts a dependency itself. The only side
  effect is an issue comment, routed through `Policy` (`Guard` default).
  Copyleft-licensed candidates are downranked, never silently dropped. Ledger
  `kind`: `library_survey`.
- **Backlog label:** `my-librarian`
