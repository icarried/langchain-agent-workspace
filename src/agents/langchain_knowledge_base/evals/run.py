from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml


AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUESTIONS_FILE = AGENT_ROOT / "evals/questions.yml"


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    expected_answer_contains: tuple[str, ...] = ()
    expected_citations: tuple[str, ...] = ()
    must_refuse: bool = False
    min_citations: int = 0


@dataclass(frozen=True)
class EvalResult:
    id: str
    passed: bool
    answer: str
    refused: bool
    citations: list[dict[str, Any]]
    checks: list[dict[str, Any]]


def load_questions(path: Path) -> list[EvalQuestion]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions: list[EvalQuestion] = []
    for item in payload.get("questions", []):
        questions.append(
            EvalQuestion(
                id=item["id"],
                question=item["question"],
                expected_answer_contains=tuple(item.get("expected_answer_contains", []) or ()),
                expected_citations=tuple(item.get("expected_citations", []) or ()),
                must_refuse=bool(item.get("must_refuse", False)),
                min_citations=int(item.get("min_citations", 0) or 0),
            )
        )
    return questions


def fixture_answer(question: EvalQuestion) -> dict[str, Any]:
    if question.must_refuse:
        return {"answer": "I do not know based on the available knowledge base.", "citations": [], "refused": True}
    if "vector store" in question.question.lower():
        return {
            "answer": "The project uses Chroma as the vector store.",
            "citations": [
                {
                    "source": "data/docs/architecture.md",
                    "chunk_id": "architecture-1",
                    "chunk_index": 1,
                    "text": "The project uses Chroma as the local vector store.",
                    "score": 0.94,
                    "metadata": {"source": "data/docs/architecture.md"},
                }
            ],
            "refused": False,
        }
    if "serve" in question.question.lower() or "docker compose" in question.question.lower():
        return {
            "answer": "The API and Langflow demo are served locally with Docker Compose, while Chroma persists locally.",
            "citations": [
                {
                    "source": "README.md",
                    "chunk_id": "readme-1",
                    "chunk_index": 0,
                    "text": "Use Docker Compose to run the API and Langflow; Chroma persists locally through PersistentClient.",
                    "score": 0.9,
                    "metadata": {"source": "README.md"},
                }
            ],
            "refused": False,
        }
    return {"answer": "I do not know based on the available knowledge base.", "citations": [], "refused": True}


def live_answer(question: EvalQuestion, base_url: str) -> dict[str, Any]:
    chat_response = httpx.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": "langchain-knowledge-base-agent",
            "messages": [{"role": "user", "content": question.question}],
            "stream": False,
        },
        timeout=30.0,
    )
    chat_response.raise_for_status()
    retrieval_response = httpx.post(
        f"{base_url.rstrip('/')}/v1/retrieval",
        json={"question": question.question},
        timeout=30.0,
    )
    retrieval_response.raise_for_status()

    chat_payload = chat_response.json()
    retrieval_payload = retrieval_response.json()
    content = chat_payload["choices"][0]["message"]["content"]
    return {
        "answer": content,
        "citations": retrieval_payload.get("citations", []),
        "refused": bool(retrieval_payload.get("refused", False)),
    }


def evaluate_question(question: EvalQuestion, payload: dict[str, Any]) -> EvalResult:
    answer = str(payload.get("answer", ""))
    citations = list(payload.get("citations", []) or [])
    refused = bool(payload.get("refused", False))
    checks: list[dict[str, Any]] = []
    passed = True

    if question.must_refuse:
        ok = refused or "do not know" in answer.lower() or "cannot" in answer.lower()
        checks.append({"check": "must_refuse", "passed": ok})
        passed = passed and ok

    for needle in question.expected_answer_contains:
        ok = needle.lower() in answer.lower()
        checks.append({"check": "answer_contains", "needle": needle, "passed": ok})
        passed = passed and ok

    if question.min_citations:
        ok = len(citations) >= question.min_citations
        checks.append({"check": "min_citations", "minimum": question.min_citations, "passed": ok})
        passed = passed and ok

    for source in question.expected_citations:
        ok = any(source in str(citation.get("source", "")) for citation in citations)
        checks.append({"check": "expected_citation", "source": source, "passed": ok})
        passed = passed and ok

    return EvalResult(
        id=question.id,
        passed=passed,
        answer=answer,
        refused=refused,
        citations=citations,
        checks=checks,
    )


def run(mode: str, questions_file: Path, base_url: str | None = None) -> dict[str, Any]:
    questions = load_questions(questions_file)
    results: list[EvalResult] = []

    for question in questions:
        if mode == "live":
            if not base_url:
                raise ValueError("base_url is required in live mode")
            payload = live_answer(question, base_url)
        else:
            payload = fixture_answer(question)
        results.append(evaluate_question(question, payload))

    summary = {
        "mode": mode,
        "questions_file": str(questions_file),
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "results": [
            {
                "id": result.id,
                "passed": result.passed,
                "answer": result.answer,
                "refused": result.refused,
                "citations": result.citations,
                "checks": result.checks,
            }
            for result in results
        ],
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run evals against the knowledge base.")
    parser.add_argument("--mode", choices=["fixture", "live"], default=os.getenv("EVALS_MODE", "fixture"))
    parser.add_argument("--questions", type=Path, default=Path(os.getenv("EVALS_QUESTIONS", DEFAULT_QUESTIONS_FILE)))
    parser.add_argument("--base-url", default=os.getenv("KB_API_BASE_URL"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run(mode=args.mode, questions_file=args.questions, base_url=args.base_url)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
