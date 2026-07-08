from __future__ import annotations

import json
from dataclasses import dataclass

from mythings.engine import Engine, EngineRequest

from mylibrarian.registries import Candidate

_SYSTEM = (
    "You are a build-vs-buy advisor. Given a task and a shortlist of "
    "discovered candidate packages, recommend which one(s) to use, with "
    "trade-offs and a short usage snippet. Only recommend or flag package "
    "names that appear in the given shortlist -- never invent a package. "
    "Reply with a single JSON object and nothing else."
)


@dataclass(frozen=True)
class Recommendation:
    name: str
    why: str
    install: str
    snippet: str


@dataclass(frozen=True)
class Avoid:
    name: str
    why: str


@dataclass(frozen=True)
class Survey:
    task: str
    candidates: list[Candidate]
    recommended: list[Recommendation]
    avoid: list[Avoid]
    confidence: str  # "low" | "medium" | "high"
    degraded: bool


def _parse_json_object(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(lines).strip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _prompt(task: str, candidates: list[Candidate]) -> str:
    lines = [f"Task: {task}", "\nCandidates:"]
    for c in candidates:
        release = f", last release {c.last_release}" if c.last_release else ""
        lines.append(
            f"- {c.name} ({c.registry}, license={c.license}{release}): {c.description}"
        )
    lines.append(
        "\nReturn JSON with keys: "
        '"recommended" (array of {"name","why","install","snippet"}), '
        '"avoid" (array of {"name","why"}), '
        '"confidence" ("low"|"medium"|"high"). '
        "Only use package names from the candidates above."
    )
    return "\n".join(lines)


def _raw_survey(task: str, candidates: list[Candidate]) -> Survey:
    # Honest degrade: no synthesis, just the shortlist as-is (already sorted by
    # the deterministic popularity score) with no fabricated why/snippet.
    return Survey(
        task=task,
        candidates=candidates,
        recommended=[],
        avoid=[],
        confidence="low",
        degraded=True,
    )


def synthesize(engine: Engine, task: str, candidates: list[Candidate]) -> Survey:
    reply = engine.run(
        EngineRequest(
            system=_SYSTEM,
            prompt=_prompt(task, candidates),
            context={"task": task, "candidate_count": len(candidates)},
        )
    )
    obj = _parse_json_object(reply.text)
    if obj is None:
        return _raw_survey(task, candidates)

    valid_names = {c.name for c in candidates}
    recommended: list[Recommendation] = []
    for item in obj.get("recommended") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name not in valid_names:  # drop anything the model invented
            continue
        recommended.append(
            Recommendation(
                name=name,
                why=str(item.get("why", "")).strip(),
                install=str(item.get("install", "")).strip(),
                snippet=str(item.get("snippet", "")).strip(),
            )
        )

    avoid: list[Avoid] = []
    for item in obj.get("avoid") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name not in valid_names:
            continue
        avoid.append(Avoid(name=name, why=str(item.get("why", "")).strip()))

    confidence = str(obj.get("confidence", "low")).strip().lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "low"

    return Survey(
        task=task,
        candidates=candidates,
        recommended=recommended,
        avoid=avoid,
        confidence=confidence,
        degraded=False,
    )


def render(survey: Survey) -> str:
    out = [f"# Library survey: {survey.task}", ""]
    if survey.degraded:
        out += ["> No recommendation engine configured — raw discovered candidates below.", ""]
    else:
        out += [f"Confidence: **{survey.confidence}**", ""]
    if survey.recommended:
        out.append("## Recommended")
        for r in survey.recommended:
            out.append(f"- **{r.name}** — {r.why}")
            if r.install:
                out.append(f"  - install: `{r.install}`")
            if r.snippet:
                out.append(f"  - usage: `{r.snippet}`")
    if survey.avoid:
        out += ["", "## Avoid"]
        for a in survey.avoid:
            out.append(f"- **{a.name}** — {a.why}")
    out += ["", "## Candidates considered"]
    for c in survey.candidates:
        release = f" (last release {c.last_release})" if c.last_release else ""
        out.append(f"- `{c.name}` [{c.registry}, {c.license}]({c.url}){release}: {c.description}")
    return "\n".join(out).rstrip() + "\n"
