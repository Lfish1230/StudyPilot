import pytest

from app.rag.evaluation import (
    EvalCase,
    EvalResult,
    calculate_metrics,
    evaluate_cases,
)


def case(case_id: str, answerable: bool, pages: list[int]) -> EvalCase:
    return EvalCase(case_id, f"question {case_id}", answerable, pages, [])


def result(
    case_id: str,
    *,
    retrieved: list[int],
    citations: list[int],
    refused: bool,
    latency: float,
    input_tokens: int,
    output_tokens: int,
) -> EvalResult:
    return EvalResult(
        case_id=case_id,
        answer="answer",
        retrieved_pages=retrieved,
        citation_pages=citations,
        refused=refused,
        latency_ms=latency,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def test_metrics_measure_retrieval_citations_refusal_latency_and_tokens() -> None:
    cases = [
        case("a", True, [2]),
        case("b", True, [7]),
        case("c", False, []),
        case("d", False, []),
    ]
    results = [
        result(
            "a",
            retrieved=[2, 3],
            citations=[2],
            refused=False,
            latency=100,
            input_tokens=10,
            output_tokens=5,
        ),
        result(
            "b",
            retrieved=[8],
            citations=[8],
            refused=False,
            latency=300,
            input_tokens=20,
            output_tokens=5,
        ),
        result(
            "c",
            retrieved=[],
            citations=[],
            refused=True,
            latency=50,
            input_tokens=0,
            output_tokens=0,
        ),
        result(
            "d",
            retrieved=[1],
            citations=[],
            refused=False,
            latency=150,
            input_tokens=0,
            output_tokens=0,
        ),
    ]

    metrics = calculate_metrics(cases, results)

    assert metrics.retrieval_hit_at_5 == 0.5
    assert metrics.citation_page_accuracy == 0.5
    assert metrics.refusal_accuracy == 0.75
    assert metrics.mean_latency_ms == 150.0
    assert metrics.mean_token_use == 10.0
    assert metrics.total_token_use == 40


def test_zero_denominators_return_zero_not_nan() -> None:
    metrics = calculate_metrics([], [])

    assert metrics.case_count == 0
    assert metrics.retrieval_hit_at_5 == 0.0
    assert metrics.citation_page_accuracy == 0.0
    assert metrics.refusal_accuracy == 0.0
    assert metrics.mean_latency_ms == 0.0
    assert metrics.mean_token_use == 0.0


class FixedClient:
    def __init__(self) -> None:
        self.seen: list[str] = []

    async def evaluate(self, evaluation_case: EvalCase) -> EvalResult:
        self.seen.append(evaluation_case.id)
        return result(
            evaluation_case.id,
            retrieved=evaluation_case.expected_pages,
            citations=evaluation_case.expected_pages,
            refused=not evaluation_case.answerable,
            latency=10,
            input_tokens=2,
            output_tokens=3,
        )


@pytest.mark.asyncio
async def test_evaluate_cases_runs_client_in_dataset_order() -> None:
    cases = [case("one", True, [1]), case("two", False, [])]
    client = FixedClient()

    report = await evaluate_cases(cases, client)

    assert client.seen == ["one", "two"]
    assert [item.case_id for item in report.results] == ["one", "two"]
    assert report.metrics.refusal_accuracy == 1.0
    assert report.metrics.total_token_use == 10
