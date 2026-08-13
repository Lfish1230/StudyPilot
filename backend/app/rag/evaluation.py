from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    question: str
    answerable: bool
    expected_pages: list[int]
    required_terms: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvalCase:
        return cls(
            id=str(payload["id"]),
            question=str(payload["question"]),
            answerable=bool(payload["answerable"]),
            expected_pages=[int(page) for page in payload["expected_pages"]],
            required_terms=[str(term) for term in payload["required_terms"]],
        )


@dataclass(frozen=True, slots=True)
class EvalResult:
    case_id: str
    answer: str
    retrieved_pages: list[int]
    citation_pages: list[int]
    refused: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    raw_result: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class EvalClient(Protocol):
    async def evaluate(self, case: EvalCase) -> EvalResult: ...


@dataclass(frozen=True, slots=True)
class EvalMetrics:
    case_count: int
    answerable_count: int
    unanswerable_count: int
    retrieval_hit_at_5: float
    citation_page_accuracy: float
    refusal_accuracy: float
    mean_latency_ms: float
    mean_token_use: float
    total_token_use: int

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    metrics: EvalMetrics
    results: list[EvalResult]


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def calculate_metrics(
    cases: list[EvalCase], results: list[EvalResult]
) -> EvalMetrics:
    result_by_case = {result.case_id: result for result in results}
    evaluated = [
        (case, result_by_case[case.id])
        for case in cases
        if case.id in result_by_case
    ]
    answerable = [(case, result) for case, result in evaluated if case.answerable]
    unanswerable_count = sum(not case.answerable for case, _ in evaluated)

    retrieval_hits = sum(
        bool(set(case.expected_pages) & set(result.retrieved_pages[:5]))
        for case, result in answerable
    )
    cited_page_count = 0
    correct_cited_page_count = 0
    for case, result in answerable:
        expected = set(case.expected_pages)
        cited_page_count += len(result.citation_pages)
        correct_cited_page_count += sum(
            page in expected for page in result.citation_pages
        )

    refusal_correct = sum(
        result.refused == (not case.answerable) for case, result in evaluated
    )
    total_tokens = sum(result.total_tokens for _, result in evaluated)
    total_latency = sum(result.latency_ms for _, result in evaluated)
    evaluated_count = len(evaluated)

    return EvalMetrics(
        case_count=evaluated_count,
        answerable_count=len(answerable),
        unanswerable_count=unanswerable_count,
        retrieval_hit_at_5=_safe_ratio(retrieval_hits, len(answerable)),
        citation_page_accuracy=_safe_ratio(
            correct_cited_page_count, cited_page_count
        ),
        refusal_accuracy=_safe_ratio(refusal_correct, evaluated_count),
        mean_latency_ms=_safe_ratio(total_latency, evaluated_count),
        mean_token_use=_safe_ratio(total_tokens, evaluated_count),
        total_token_use=total_tokens,
    )


async def evaluate_cases(
    cases: list[EvalCase], client: EvalClient
) -> EvaluationReport:
    results = [await client.evaluate(case) for case in cases]
    return EvaluationReport(metrics=calculate_metrics(cases, results), results=results)
