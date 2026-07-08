from __future__ import annotations

from dataclasses import dataclass

from myguard import Guard
from mythings.engine import Engine, NoopEngine
from mythings.github import Runner, _gh
from mythings.isolation import in_github_actions
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, Policy

from mylibrarian.recommend import Survey, render, synthesize
from mylibrarian.registries import Candidate, Fetcher, _http, retrieve


@dataclass(frozen=True)
class Result:
    outcome: str  # success | skipped | failure
    task: str
    candidate_count: int
    detail: str
    comment_url: str | None = None


class Librarian:
    def __init__(
        self,
        *,
        ledger: Ledger,
        repo: str | None = None,
        runner: Runner = _gh,
        engine: Engine | None = None,
        policy: Policy | None = None,
        fetch: Fetcher = _http,
        registries: tuple[str, ...] = ("pypi", "npm"),
        top: int = 10,
    ) -> None:
        self.ledger = ledger
        self.repo = repo
        self.runner = runner
        self.engine: Engine = engine or NoopEngine()
        self.policy: Policy = policy or Guard()
        self.fetch = fetch
        self.registries = registries
        self.top = top

    def survey(self, issue: int, task: str, *, comment: bool = False) -> Result:
        gh_runner = self.runner if "github" in self.registries else None
        candidates = retrieve(
            task,
            registries=self.registries,
            top=self.top,
            fetch=self.fetch,
            gh_runner=gh_runner,
        )
        if not candidates:
            detail = f"no candidates found for {task!r}"
            url = self._comment(issue, f"_{detail}_") if comment else None
            self._record("skipped", task, [], None, detail, comment_url=url)
            return Result("skipped", task, 0, detail, url)

        survey = synthesize(self.engine, task, candidates)
        markdown = render(survey)
        url = self._comment(issue, markdown) if comment else None
        detail = f"{len(candidates)} candidates for {task!r}"
        self._record("success", task, candidates, survey, detail, comment_url=url)
        return Result("success", task, len(candidates), detail, url)

    def _comment(self, issue: int, body: str) -> str | None:
        if self.repo is None:
            return None
        argv = ["issue", "comment", str(issue), "--repo", self.repo, "--body", body]
        action = Action(kind="bash", payload={"command": f"gh issue comment {issue}"})
        if self.policy.evaluate(action).under(unattended=in_github_actions()) is not Decision.ALLOW:
            return None
        return self.runner(argv).strip() or None

    def _record(
        self,
        outcome: str,
        task: str,
        candidates: list[Candidate],
        survey: Survey | None,
        detail: str,
        *,
        comment_url: str | None,
    ) -> None:
        self.ledger.record(
            tool="mylibrarian",
            kind="library_survey",
            outcome=outcome,
            detail=detail,
            task=task,
            candidates=[c.name for c in candidates],
            recommended=[r.name for r in survey.recommended] if survey else [],
            avoid=[a.name for a in survey.avoid] if survey else [],
            comment_url=comment_url,
        )
