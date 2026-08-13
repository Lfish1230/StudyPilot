from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.qwen import QwenEmbeddingClient  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.rag.evaluation import (  # noqa: E402
    EvalCase,
    EvalClient,
    EvalResult,
    evaluate_cases,
)
from app.rag.repository import (  # noqa: E402
    RETRIEVAL_LIMIT,
    RETRIEVAL_MAX_DISTANCE,
    retrieve_chunks,
)

DEFAULT_DATASET = Path(__file__).with_name("dataset.jsonl")
DEFAULT_SOURCE = Path(__file__).with_name("sources") / "xv6-chinese.pdf"
COURSE_NAME = "RAG 评测 - xv6 中文文档"
SOURCE_SHA256 = "51d28581a043c438cf91f21b66dc3eba914404cc48cdd8f763ab15c10dd36bf7"
DOCUMENT_NAME = f"xv6-chinese-{SOURCE_SHA256[:12]}.pdf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the reproducible StudyPilot RAG evaluation.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--email",
        default=os.getenv("STUDYPILOT_EVAL_EMAIL", "eval@studypilot.local"),
    )
    parser.add_argument(
        "--password",
        default=os.getenv(
            "STUDYPILOT_EVAL_PASSWORD", "local-eval-password-42"
        ),
    )
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).with_name("results"),
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                cases.append(EvalCase.from_dict(json.loads(line)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid dataset row {line_number}: {exc}") from exc
    if len(cases) < 20:
        raise ValueError("Evaluation dataset must contain at least 20 cases")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    return cases


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


class ApiSession:
    def __init__(self, client: httpx.AsyncClient, email: str, password: str) -> None:
        self.client = client
        self.email = email
        self.password = password

    async def authenticate(self) -> None:
        response = await self.client.post(
            "/auth/login", json={"email": self.email, "password": self.password}
        )
        if response.status_code == 401:
            registration = await self.client.post(
                "/auth/register",
                json={"email": self.email, "password": self.password},
            )
            registration.raise_for_status()
            response = await self.client.post(
                "/auth/login", json={"email": self.email, "password": self.password}
            )
        response.raise_for_status()
        self.client.headers["Authorization"] = (
            f"Bearer {response.json()['access_token']}"
        )

    async def ensure_course(self) -> str:
        response = await self.client.get("/courses")
        response.raise_for_status()
        existing = next(
            (item for item in response.json() if item["name"] == COURSE_NAME), None
        )
        if existing:
            return str(existing["id"])
        created = await self.client.post("/courses", json={"name": COURSE_NAME})
        created.raise_for_status()
        return str(created.json()["id"])

    async def ensure_document(
        self,
        course_id: str,
        source: Path,
        poll_seconds: float,
        timeout_seconds: float,
    ) -> None:
        endpoint = f"/courses/{course_id}/documents"
        response = await self.client.get(endpoint)
        response.raise_for_status()
        document = next(
            (
                item
                for item in response.json()
                if item["original_name"] == DOCUMENT_NAME
            ),
            None,
        )
        if document is None:
            with source.open("rb") as stream:
                upload = await self.client.post(
                    endpoint,
                    files={"file": (DOCUMENT_NAME, stream, "application/pdf")},
                )
            upload.raise_for_status()
            document = upload.json()
        elif document["status"] == "failed":
            retry = await self.client.post(f"/documents/{document['id']}/retry")
            retry.raise_for_status()
            document = retry.json()

        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while document["status"] != "ready":
            if document["status"] == "failed":
                raise RuntimeError(
                    f"Document processing failed: {document.get('failure_message')}"
                )
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("Timed out waiting for evaluation PDF processing")
            await asyncio.sleep(poll_seconds)
            response = await self.client.get(f"/documents/{document['id']}")
            response.raise_for_status()
            document = response.json()


class StudyPilotEvalClient(EvalClient):
    def __init__(
        self,
        api: ApiSession,
        course_id: str,
        embedding_client: QwenEmbeddingClient,
    ) -> None:
        self.api = api
        self.course_id = UUID(course_id)
        self.embedding_client = embedding_client

    async def evaluate(self, case: EvalCase) -> EvalResult:
        started = asyncio.get_running_loop().time()
        vectors = await self.embedding_client.embed([case.question])
        async with SessionLocal() as session:
            chunks = await retrieve_chunks(session, self.course_id, vectors[0])
        conversation = await self.api.client.post(
            f"/courses/{self.course_id}/conversations"
        )
        conversation.raise_for_status()
        response = await self.api.client.post(
            f"/conversations/{conversation.json()['id']}/messages",
            json={"question": case.question},
        )
        elapsed_ms = (asyncio.get_running_loop().time() - started) * 1000
        response.raise_for_status()
        payload = response.json()
        answer = str(payload["content"])
        term_hits = [term for term in case.required_terms if term in answer]
        return EvalResult(
            case_id=case.id,
            answer=answer,
            retrieved_pages=[chunk.page_number for chunk in chunks],
            citation_pages=[item["page_number"] for item in payload["citations"]],
            refused=bool(payload["refused"]),
            latency_ms=elapsed_ms,
            input_tokens=int(payload.get("input_tokens") or 0),
            output_tokens=int(payload.get("output_tokens") or 0),
            raw_result={
                "answer": payload,
                "retrieved": [asdict(chunk) for chunk in chunks],
                "required_term_hits": term_hits,
                "backend_answer_latency_ms": payload.get("latency_ms"),
            },
        )


def markdown_report(metadata: dict[str, Any], metrics: dict[str, Any]) -> str:
    percentage_metrics = {
        "retrieval_hit_at_5",
        "citation_page_accuracy",
        "refusal_accuracy",
    }
    lines = [
        "# StudyPilot RAG Evaluation",
        "",
        "## Run metadata",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    lines.extend(f"| {key} | `{value}` |" for key, value in metadata.items())
    lines.extend(["", "## Metrics", "", "| Metric | Value |", "| --- | ---: |"])
    for key, value in metrics.items():
        if key in percentage_metrics:
            rendered = f"{value:.2%}"
        else:
            rendered = str(round(value, 2) if isinstance(value, float) else value)
        lines.append(f"| {key} | {rendered} |")
    lines.append("")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> tuple[Path, Path]:
    dataset = args.dataset.resolve()
    source = args.source.resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"Source PDF not found at {source}. Run evals/download_source.ps1 first."
        )
    actual_source_hash = sha256(source)
    if actual_source_hash != SOURCE_SHA256:
        raise ValueError(
            f"Source PDF SHA-256 mismatch: expected {SOURCE_SHA256}, "
            f"got {actual_source_hash}"
        )
    cases = load_cases(dataset)
    settings = Settings()
    if not settings.dashscope_api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required for a real evaluation run")

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), timeout=60.0
    ) as http_client:
        api = ApiSession(http_client, args.email, args.password)
        await api.authenticate()
        course_id = await api.ensure_course()
        await api.ensure_document(
            course_id,
            source,
            args.poll_seconds,
            args.timeout_seconds,
        )
        evaluation_client = StudyPilotEvalClient(
            api,
            course_id,
            QwenEmbeddingClient.from_settings(settings),
        )
        report = await evaluate_cases(cases, evaluation_client)

    run_at = datetime.now(UTC)
    metadata = {
        "run_at_utc": run_at.isoformat(),
        "git_commit": git_commit(),
        "dataset_sha256": sha256(dataset),
        "source_sha256": actual_source_hash,
        "chat_model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": settings.embedding_dimension,
        "retrieval_limit": RETRIEVAL_LIMIT,
        "retrieval_max_distance": RETRIEVAL_MAX_DISTANCE,
        "evaluation_case_count": len(cases),
        "total_estimated_token_use": report.metrics.total_token_use,
    }
    raw_report = {
        "metadata": metadata,
        "metrics": report.metrics.to_dict(),
        "cases": [asdict(case) for case in cases],
        "results": [asdict(result) for result in report.results],
    }
    args.results_dir.mkdir(parents=True, exist_ok=True)
    stem = run_at.strftime("rag-eval-%Y%m%dT%H%M%SZ")
    json_path = args.results_dir / f"{stem}.json"
    markdown_path = args.results_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(raw_report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(
        markdown_report(metadata, report.metrics.to_dict()), encoding="utf-8"
    )
    return json_path, markdown_path


def main() -> None:
    args = parse_args()
    json_path, markdown_path = asyncio.run(run(args))
    print(f"Raw report: {json_path}")
    print(f"Summary: {markdown_path}")


if __name__ == "__main__":
    main()
