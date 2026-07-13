from evals.run import run


def test_eval_runner_uses_fixture_mode_by_default(tmp_path):
    questions = tmp_path / "questions.yml"
    questions.write_text(
        """
mode: fixture
questions:
  - id: grounded_answer
    question: What does the project use for its vector store?
    expected_answer_contains: [Chroma]
    expected_citations: [data/docs/architecture.md]
  - id: refuse_unknown
    question: What is the launch code for the production cluster?
    must_refuse: true
""",
        encoding="utf-8",
    )

    summary = run(mode="fixture", questions_file=questions)

    assert summary["mode"] == "fixture"
    assert summary["total"] == 2
    assert summary["passed"] == 2
    assert summary["failed"] == 0
    assert [result["id"] for result in summary["results"]] == ["grounded_answer", "refuse_unknown"]


def test_eval_runner_reports_json_serializable_summary(tmp_path):
    questions = tmp_path / "questions.yml"
    questions.write_text(
        """
questions:
  - id: citation_required
    question: How is the knowledge base served locally?
    expected_answer_contains: [Docker Compose]
    min_citations: 1
""",
        encoding="utf-8",
    )

    summary = run(mode="fixture", questions_file=questions)

    result = summary["results"][0]
    assert result["passed"] is True
    assert result["citations"][0]["source"] == "README.md"
    assert result["checks"][-1]["passed"] is True
