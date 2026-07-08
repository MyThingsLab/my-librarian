from __future__ import annotations

import argparse
import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.ledger import Ledger

from mylibrarian.librarian import Librarian

_ENGINE_NAMES = ("noop", "claude-cli")
_REGISTRY_NAMES = ("pypi", "npm", "github")


def build_engine(name: str, *, model: str | None = None) -> Engine:
    if name == "claude-cli":
        return ClaudeCLIEngine(model=model)
    return NoopEngine()


def _parse_registries(raw: str) -> tuple[str, ...]:
    registries = tuple(r.strip() for r in raw.split(",") if r.strip())
    unknown = [r for r in registries if r not in _REGISTRY_NAMES]
    if unknown:
        raise SystemExit(f"unknown registry: {unknown[0]!r} (choose from {_REGISTRY_NAMES})")
    return registries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mylibrarian",
        description="Discover community libraries/CLIs for a task and recommend build-vs-buy.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    survey = sub.add_parser("survey", help="survey candidate packages for a task")
    survey.add_argument("--issue", type=int, required=True)
    survey.add_argument("--task", required=True, help="the task to find a package for")
    survey.add_argument("--repo", help="GitHub slug owner/name")
    survey.add_argument("--registries", default="pypi,npm")
    survey.add_argument("--top", type=int, default=10)
    survey.add_argument(
        "--comment", action="store_true", help="also post the survey to the issue"
    )
    survey.add_argument("--json", action="store_true")
    survey.add_argument("--ledger", type=Path, default=Path(".mythings/ledger.jsonl"))
    survey.add_argument("--engine", choices=sorted(_ENGINE_NAMES), default="noop")
    survey.add_argument("--engine-model", help="model for --engine claude-cli")

    args = parser.parse_args(argv)
    engine = build_engine(args.engine, model=args.engine_model)
    registries = _parse_registries(args.registries)

    librarian = Librarian(
        ledger=Ledger(args.ledger),
        repo=args.repo,
        engine=engine,
        registries=registries,
        top=args.top,
    )
    result = librarian.survey(args.issue, args.task, comment=args.comment)

    if args.json:
        print(
            json.dumps(
                {
                    "outcome": result.outcome,
                    "task": result.task,
                    "candidate_count": result.candidate_count,
                    "detail": result.detail,
                    "comment_url": result.comment_url,
                }
            )
        )
    else:
        print(result.detail)
    return 0 if result.outcome != "failure" else 1


if __name__ == "__main__":
    raise SystemExit(main())
