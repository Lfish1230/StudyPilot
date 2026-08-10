# StudyPilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a portfolio-ready AI course assistant that turns text PDFs into cited RAG answers, quizzes, grading feedback, and learning analytics.

**Architecture:** A React TypeScript single-page app calls a FastAPI API. FastAPI owns authentication, domain rules, document processing, RAG orchestration, quizzes, and analytics; PostgreSQL with pgvector stores relational and vector data, Supabase Storage holds private PDFs, and an OpenAI-compatible Qwen gateway supplies chat and embeddings.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, PostgreSQL 16 + pgvector, PyMuPDF, OpenAI Python SDK, React 19, TypeScript, Vite, React Router, TanStack Query, Vitest, Playwright, pytest, Docker Compose, GitHub Actions.

## Global Constraints

- First release includes auth, courses, text-PDF ingestion, cited RAG Q&A, multiple-choice and short-answer quizzes, grading, mistakes, and course analytics.
- Do not add OCR, voice, image understanding, knowledge graphs, multi-agent orchestration, collaboration, mobile apps, billing, or model training.
- Accept PDF only; maximum file size is 20 MB and maximum length is 300 pages.
- Split within page boundaries at approximately 700 tokens with 100-token overlap.
- Use `text-embedding-v4` with exactly 1024 dimensions and retrieve the five nearest chunks by cosine distance.
- Default chat model is `qwen-plus`; all model access stays behind provider interfaces.
- Persist structured data and vectors in PostgreSQL + pgvector and original PDFs in private Supabase Storage.
- API keys and secrets exist only in backend environment variables.
- Daily per-user demo limits are 5 PDF uploads, 50 RAG questions, and 10 quiz generations, measured in UTC.
- Background document jobs older than 15 minutes become `failed` on startup and can be retried idempotently.
- Every resource query must enforce owner scope; tests must prove cross-user isolation.
- Budget for model API and deployment remains within 50–100 CNY.
- Use test-driven development and commit after each task passes its focused verification.

---

## Planned File Structure

```text
StudyPilot/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory and lifespan
│   │   ├── core/
│   │   │   ├── config.py              # Validated environment settings
│   │   │   ├── database.py            # Async engine/session factory
│   │   │   ├── errors.py              # Stable API error envelope
│   │   │   ├── middleware.py          # Request ID and safe logging
│   │   │   └── security.py            # Password hashing and JWT
│   │   ├── auth/                       # User model, schemas, service, router, deps
│   │   ├── courses/                    # Course model, schemas, service, router
│   │   ├── documents/                  # PDF metadata, storage, parsing, chunking, jobs
│   │   ├── ai/                         # Chat/embedding provider interfaces and Qwen adapter
│   │   ├── rag/                        # Chunk model, retrieval, conversations, citations
│   │   ├── quizzes/                    # Quiz generation, questions, attempts, grading
│   │   └── analytics/                  # Aggregated course metrics and weak topics
│   └── tests/                          # Unit and API tests mirroring app domains
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── playwright.config.ts
│   └── src/
│       ├── app/                        # Router, providers, shell and global styles
│       ├── api/                        # Typed fetch client and API contracts
│       ├── features/                   # auth, courses, documents, chat, quizzes, analytics
│       ├── components/                 # Reusable loading, error and layout components
│       └── test/                       # Vitest setup and test helpers
├── evals/
│   ├── dataset.jsonl                   # At least 20 versioned RAG questions
│   ├── run_rag_eval.py                 # Repeatable retrieval/citation/refusal evaluation
│   └── README.md
├── infra/
│   ├── docker-compose.yml              # Local pgvector database
│   └── render.yaml                     # Backend deployment declaration
├── .github/workflows/ci.yml
├── .env.example
└── README.md
```

## Task 1: Runnable Monorepo Foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/middleware.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/` with the Vite React TypeScript template
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/test/setup.ts`
- Create: `infra/docker-compose.yml`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: none.
- Produces: `app.main:create_app() -> FastAPI`, `GET /health -> {"status":"ok"}`, `Settings`, and the shared error shape `{code, message, request_id}`.

- [ ] **Step 1: Add backend dependencies and a failing health test**

Create `backend/pyproject.toml` with Python `>=3.12` and these bounded runtime dependencies: `fastapi>=0.116,<1`, `uvicorn[standard]>=0.35,<1`, `pydantic-settings>=2.10,<3`, `sqlalchemy[asyncio]>=2.0,<3`, `asyncpg>=0.30,<1`, `alembic>=1.16,<2`, `pgvector>=0.4,<1`, `pyjwt>=2.10,<3`, `pwdlib[argon2]>=0.2,<1`, `python-multipart>=0.0.20,<1`, `pymupdf>=1.26,<2`, `tiktoken>=0.11,<1`, `openai>=1.99,<3`, `tenacity>=9,<10`, and `supabase>=2.18,<3`. Add development dependencies `pytest>=8.4,<9`, `pytest-asyncio>=1.1,<2`, `httpx>=0.28,<1`, `ruff>=0.12,<1`, and `mypy>=1.17,<2`. Configure Ruff for Python 3.12 with an 88-character line length, pytest asyncio mode `auto`, and mypy strict mode. Commit the generated `uv.lock`.

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Install and prove the backend test fails**

Run:

```powershell
cd backend
python -m pip install uv
uv sync
uv run pytest tests/test_health.py -v
```

Expected: FAIL because `app.main` or `create_app` does not exist.

- [ ] **Step 3: Implement the minimal application factory**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="StudyPilot API", version="0.1.0")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

Add `Settings` with `database_url`, `jwt_secret`, `cors_origins`, `dashscope_api_key`, `dashscope_base_url`, `chat_model`, `embedding_model`, `embedding_dimension`, Supabase URL/key/bucket, quotas, and size/page limits. Use an `ErrorResponse` Pydantic model and request-ID middleware that echoes `X-Request-ID` without logging secrets. Add FastAPI `CORSMiddleware` with exact origins parsed from `cors_origins`, credentials enabled, and methods/headers restricted to those used by the app.

- [ ] **Step 4: Verify backend quality gates**

Run:

```powershell
cd backend
uv run pytest tests/test_health.py -v
uv run ruff check app tests
uv run mypy app
```

Expected: all commands exit 0.

- [ ] **Step 5: Scaffold the frontend and write a failing shell test**

Run `npm create vite@latest frontend -- --template react-ts`, install dependencies, then add Vitest and Testing Library. Replace the default test with:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the StudyPilot shell", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "StudyPilot" })).toBeInTheDocument();
  });
});
```

Run `cd frontend; npm test -- --run`. Expected: FAIL because the heading is absent.

- [ ] **Step 6: Implement and verify the frontend shell**

Make `App.tsx` render a semantic `main` and `h1` named `StudyPilot`. Configure Vitest with `jsdom` and `src/test/setup.ts` importing `@testing-library/jest-dom/vitest`.

Run:

```powershell
cd frontend
npm test -- --run
npm run build
```

Expected: test and build pass.

- [ ] **Step 7: Add local PostgreSQL and environment examples**

Create `infra/docker-compose.yml` using `pgvector/pgvector:pg16`, database `studypilot`, user `studypilot`, a named volume, and a health check. `.env.example` must list every setting with non-secret local values and `JWT_SECRET=change-me-before-deploying`. Create a minimal root `README.md` containing the project name, approved one-paragraph scope, prerequisites, and links to the design and implementation-plan documents.

Run `docker compose -f infra/docker-compose.yml config`. Expected: valid configuration.

- [ ] **Step 8: Commit the foundation**

```powershell
git add backend frontend infra .env.example README.md
git commit -m "chore: scaffold StudyPilot applications"
```

## Task 2: Database Foundation and Authentication

**Files:**
- Create: `backend/app/core/database.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/auth/model.py`
- Create: `backend/app/auth/schemas.py`
- Create: `backend/app/auth/service.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/auth/router.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_users.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/auth/test_auth_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Settings` and `create_app()` from Task 1.
- Produces: `User`, `get_current_user() -> User`, `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, and async database sessions.

- [ ] **Step 1: Start the test database and write failing auth tests**

Use Docker Compose, run Alembic against a dedicated `studypilot_test` database, and provide fixtures `client`, `db_session`, `user_factory`, and `auth_headers` in `tests/conftest.py`.

Add tests that assert:

```python
def test_register_login_and_me(client):
    registered = client.post("/auth/register", json={
        "email": "student@example.com", "password": "correct-horse-42"
    })
    assert registered.status_code == 201
    assert "password" not in registered.text

    login = client.post("/auth/login", json={
        "email": "student@example.com", "password": "correct-horse-42"
    })
    token = login.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "student@example.com"


def test_duplicate_email_uses_stable_error_shape(client):
    payload = {"email": "same@example.com", "password": "correct-horse-42"}
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"
    assert response.json()["request_id"]
```

- [ ] **Step 2: Run tests and confirm the missing routes fail**

Run `cd backend; uv run pytest tests/auth/test_auth_api.py -v`.

Expected: FAIL with 404 responses.

- [ ] **Step 3: Implement persistence, migration, hashing, and JWT**

Use SQLAlchemy 2 declarative models with UUID primary keys and timezone-aware timestamps. `User` has unique lowercase `email`, `password_hash`, and `created_at`. Implement:

```python
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def create_access_token(user_id: UUID, expires_minutes: int = 60) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=["HS256"]
        )
        return UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("invalid_token", "登录状态无效，请重新登录。") from exc
```

Reject passwords shorter than 10 characters. Normalize email with `strip().lower()`. Return `401 invalid_credentials` for both unknown email and incorrect password. Never expose `password_hash`.

- [ ] **Step 4: Register routes and global API errors**

Include `/auth` router in `create_app()`. Convert domain exceptions to the shared `{code, message, request_id}` response. Ensure validation errors also include a request ID and a stable `validation_error` code.

- [ ] **Step 5: Run migration and auth verification**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/auth/test_auth_api.py -v
uv run ruff check app tests
```

Expected: all pass.

- [ ] **Step 6: Commit authentication**

```powershell
git add backend/app backend/alembic* backend/tests
git commit -m "feat: add secure user authentication"
```

## Task 3: Owner-Scoped Courses

**Files:**
- Create: `backend/app/courses/model.py`
- Create: `backend/app/courses/schemas.py`
- Create: `backend/app/courses/service.py`
- Create: `backend/app/courses/router.py`
- Create: `backend/alembic/versions/0002_courses.py`
- Create: `backend/tests/courses/test_courses_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `User`, `get_current_user`, and `AsyncSession` from Task 2.
- Produces: `Course`, `get_owned_course(session, user_id, course_id) -> Course`, and CRUD routes under `/courses`.

- [ ] **Step 1: Write failing CRUD and isolation tests**

```python
def test_course_crud_is_owner_scoped(client, user_factory, token_for):
    alice, bob = user_factory(), user_factory()
    created = client.post("/courses", json={"name": "计算机网络"}, headers=token_for(alice))
    course_id = created.json()["id"]
    assert created.status_code == 201
    assert client.get(f"/courses/{course_id}", headers=token_for(bob)).status_code == 404
    assert client.delete(f"/courses/{course_id}", headers=token_for(alice)).status_code == 204
```

Also test blank names, names longer than 80 characters, ordering by newest first, and unauthenticated requests.

- [ ] **Step 2: Verify tests fail with 404**

Run `uv run pytest tests/courses/test_courses_api.py -v`. Expected: FAIL because routes are absent.

- [ ] **Step 3: Implement the course model and service**

`Course` contains `id`, `owner_id`, `name`, `created_at`, and `updated_at`. Trim names and enforce `1..80` characters in Pydantic and the database. Use `ON DELETE CASCADE` from courses to every later course-owned table so course deletion clears metadata, vectors, conversations, quizzes, and attempts. `get_owned_course` must filter both `Course.id` and `Course.owner_id`; return 404 for missing and foreign resources to avoid leaking IDs.

- [ ] **Step 4: Add routes and migration**

Implement `POST /courses`, `GET /courses`, `GET /courses/{id}`, and `DELETE /courses/{id}`. Register the router and apply migration `0002_courses.py` with an owner/name index.

- [ ] **Step 5: Verify and commit**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/courses/test_courses_api.py -v
uv run pytest tests/auth -v
git add app/courses app/main.py alembic/versions tests/courses
git commit -m "feat: add owner-scoped courses"
```

## Task 4: PDF Metadata, Private Storage, and Upload Validation

**Files:**
- Create: `backend/app/documents/model.py`
- Create: `backend/app/documents/schemas.py`
- Create: `backend/app/documents/storage.py`
- Create: `backend/app/documents/service.py`
- Create: `backend/app/documents/router.py`
- Create: `backend/alembic/versions/0003_documents.py`
- Create: `backend/tests/documents/test_upload_api.py`
- Create: `backend/tests/documents/test_storage.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `get_owned_course` and `get_current_user`.
- Produces: `Document`, `DocumentStatus`, `ObjectStorage` protocol, upload/list/get/delete/retry routes, and `schedule_document_processing(document_id: UUID)` hook.

- [ ] **Step 1: Define the storage protocol and failing tests**

```python
class ObjectStorage(Protocol):
    async def upload(self, object_key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    async def download(self, object_key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, object_key: str) -> None:
        raise NotImplementedError
```

Write API tests for a valid `%PDF-` file, a 20 MB + 1 byte rejection, MIME mismatch, bad magic bytes, foreign course, private generated object key, list, get, delete, and `429 upload_quota_exceeded` after five UTC-day uploads. Use `FakeObjectStorage` in tests.

- [ ] **Step 2: Confirm upload tests fail**

Run `uv run pytest tests/documents/test_upload_api.py tests/documents/test_storage.py -v`.

Expected: FAIL because document routes and storage do not exist.

- [ ] **Step 3: Implement metadata and validation**

`Document` fields: `id`, `course_id`, `original_name`, `object_key`, `size_bytes`, `page_count`, `status`, `failure_code`, `failure_message`, `processing_started_at`, timestamps. Status values are `uploaded`, `processing`, `ready`, `failed`.

Read uploads with a hard byte limit, validate `application/pdf`, validate `%PDF-` magic bytes, generate object keys as `{owner_id}/{course_id}/{document_id}.pdf`, and never use the client filename in a path. Before storing, count the owner's UTC-day documents and return `429 upload_quota_exceeded` at the configured limit of 5.

- [ ] **Step 4: Implement Supabase and fake adapters**

`SupabaseObjectStorage` uses the configured private bucket. Because the Supabase storage client is synchronous, call it through `asyncio.to_thread` behind the async protocol. Convert provider errors to `storage_unavailable` without returning credentials or raw provider payloads. Deleting a document removes the object first; if storage deletion fails, keep database metadata and return a retryable error.

- [ ] **Step 5: Add owner-scoped routes**

Implement `POST /courses/{course_id}/documents`, `GET /courses/{course_id}/documents`, `GET /documents/{id}`, `DELETE /documents/{id}`, and `POST /documents/{id}/retry`. The exact deliverable for this task stores a successful upload with status `uploaded` and exposes an injected scheduler callable that defaults to a no-op in this task's application wiring. Task 6 replaces that injected callable with the production background processor after its required adapters exist.

- [ ] **Step 6: Migrate, verify, and commit**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/documents/test_upload_api.py tests/documents/test_storage.py -v
git add app/documents app/main.py alembic/versions tests/documents
git commit -m "feat: validate and store private PDF uploads"
```

## Task 5: Deterministic PDF Parsing, Chunking, and Recoverable Jobs

**Files:**
- Create: `backend/app/documents/parser.py`
- Create: `backend/app/documents/chunker.py`
- Create: `backend/app/documents/processor.py`
- Create: `backend/app/documents/jobs.py`
- Create: `backend/app/ai/types.py`
- Create: `backend/app/ai/interfaces.py`
- Create: `backend/tests/documents/test_parser.py`
- Create: `backend/tests/documents/test_chunker.py`
- Create: `backend/tests/documents/test_processor.py`

**Interfaces:**
- Consumes: `ObjectStorage`, `Document`, and document status routes from Task 4.
- Produces: `PdfPage(page_number: int, text: str)`, `TextChunk(page_number: int, content: str, token_count: int)`, `EmbeddingClient`, `ChunkSink`, `parse_pdf(data)`, `chunk_pages(pages)`, and a provider-independent `process_document(document_id)`.

- [ ] **Step 1: Write failing pure parser and chunker tests**

Tests must prove that page numbers start at 1, whitespace is normalized, blank pages are ignored, a document with no useful text raises `ScannedPdfError`, pages never mix in a chunk, chunks stay at or below 700 tokens except a single indivisible token sequence, and overlap is approximately 100 tokens.

```python
def test_chunks_never_cross_page_boundaries(tokenizer):
    pages = [PdfPage(1, "alpha " * 800), PdfPage(2, "beta " * 800)]
    chunks = chunk_pages(pages, tokenizer, max_tokens=700, overlap_tokens=100)
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert all(not ("alpha" in c.content and "beta" in c.content) for c in chunks)
```

- [ ] **Step 2: Run tests and verify missing functions fail**

Run `uv run pytest tests/documents/test_parser.py tests/documents/test_chunker.py -v`.

- [ ] **Step 3: Implement parser and chunker without AI calls**

Use PyMuPDF opened from bytes. Reject more than 300 pages before extraction. Normalize repeated spaces while preserving paragraph breaks. Use `tiktoken` for repeatable token counts. Return typed dataclasses; do not access the database in these pure modules.

- [ ] **Step 4: Write failing processor state tests**

Test the transitions `uploaded -> processing -> ready`, parser failure to `failed/scanned_pdf`, provider failure to `failed/embedding_unavailable`, retry deleting previous chunks before inserting replacements, and startup recovery marking jobs older than 15 minutes failed.

- [ ] **Step 5: Implement the recoverable processor boundary**

Define the processor with explicit dependencies:

```python
async def process_document(
    document_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    embedding_client: EmbeddingClient,
    chunk_sink: ChunkSink,
) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id, with_for_update=True)
        if document is None:
            return
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = datetime.now(UTC)
        document.failure_code = None
        document.failure_message = None
        object_key = document.object_key
        course_id = document.course_id
        await session.commit()

    try:
        pdf_bytes = await storage.download(object_key)
        pages = parse_pdf(pdf_bytes, max_pages=300)
        chunks = chunk_pages(pages, max_tokens=700, overlap_tokens=100)
        embeddings = await embedding_client.embed([chunk.content for chunk in chunks])
        await chunk_sink.replace(document_id, course_id, chunks, embeddings)
    except ScannedPdfError:
        await mark_document_failed(
            session_factory, document_id, "scanned_pdf", "暂不支持扫描版 PDF。"
        )
        return
    except EmbeddingUnavailableError:
        await mark_document_failed(
            session_factory,
            document_id,
            "embedding_unavailable",
            "文档向量化暂时失败，请稍后重试。",
        )
        return

    await mark_document_ready(
        session_factory, document_id, page_count=len(pages)
    )
```

`EmbeddingClient.embed(texts)` and `ChunkSink.replace(document_id, course_id, chunks, embeddings)` are Protocol methods created in this task. Implement `mark_document_failed` and `mark_document_ready` in the same module as short fresh-session transactions that clear `processing_started_at`. The processor creates its own database session rather than reusing a request session, delegates atomic replacement to `ChunkSink`, and stores only sanitized failure codes/messages. Tests use deterministic fake implementations of both protocols.

- [ ] **Step 6: Implement and test stale-job recovery**

Implement `recover_stale_document_jobs(session, cutoff_minutes=15)` as a database update from stale `processing` rows to `failed` with code `processing_interrupted`. Verify exact cutoff behavior with a frozen clock. Production scheduling is wired after the pgvector and Qwen adapters exist in Task 6.

- [ ] **Step 7: Verify and commit**

```powershell
cd backend
uv run pytest tests/documents/test_parser.py tests/documents/test_chunker.py tests/documents/test_processor.py -v
git add app/documents app/ai tests/documents
git commit -m "feat: process PDF documents into recoverable chunks"
```

## Task 6: AI Provider Gateways and Vector Retrieval

**Files:**
- Modify: `backend/app/ai/types.py`
- Modify: `backend/app/ai/interfaces.py`
- Create: `backend/app/ai/qwen.py`
- Create: `backend/app/ai/retry.py`
- Create: `backend/app/rag/model.py`
- Create: `backend/app/rag/repository.py`
- Create: `backend/alembic/versions/0004_document_chunks.py`
- Create: `backend/tests/ai/test_qwen_gateway.py`
- Create: `backend/tests/rag/test_retrieval.py`
- Modify: `backend/app/documents/processor.py`
- Modify: `backend/app/documents/router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `TextChunk`, `EmbeddingClient`, `ChunkSink`, and `process_document()` from Task 5.
- Produces: Qwen implementations of `EmbeddingClient.embed(texts: list[str]) -> list[list[float]]`, `ChatClient.complete(messages, response_format=None) -> ChatResult`, `PgVectorChunkSink`, `DocumentChunk`, `retrieve_chunks(course_id, query_vector, limit=5, max_distance=0.40)`, and `get_document_context(document_ids, token_budget)`.

- [ ] **Step 1: Write failing provider contract tests**

Use `httpx.MockTransport` or an injected OpenAI client. Assert that embedding requests use `text-embedding-v4`, dimensions `1024`, and batch inputs; chat requests use `qwen-plus`; timeouts and 429/5xx responses retry at most twice; auth and validation errors do not retry; returned usage is normalized to `TokenUsage(input_tokens, output_tokens)`.

- [ ] **Step 2: Implement provider interfaces and Qwen adapter**

```python
class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

class ChatClient(Protocol):
    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        raise NotImplementedError
```

Use the Async OpenAI client with the configured DashScope base URL. Validate every embedding has exactly 1024 floats. Use Tenacity with two retries after the original request and bounded exponential backoff. Emit one safe structured log per provider call containing request ID, provider, model, latency, input tokens, output tokens, and error category; never log prompts, PDF text, credentials, or full model responses.

- [ ] **Step 3: Write a failing pgvector retrieval test**

Seed chunks for two courses and assert only the requested course is returned, results are distance ordered, at most five are returned, and results above `0.40` distance are excluded.

- [ ] **Step 4: Implement chunk persistence and retrieval**

`DocumentChunk` has `document_id`, `course_id`, `page_number`, `content`, `token_count`, and `embedding Vector(1024)`. Add an HNSW cosine index after the table is created. Store embeddings in batches of at most 20 chunks.

Use SQLAlchemy pgvector cosine distance and always filter by `course_id`; owner validation happens before repository calls. `get_document_context` filters selected document IDs, orders chunks by document then page, and stops before its explicit token budget.

- [ ] **Step 5: Wire document processing to production adapters**

Upload and retry routes schedule `process_document` through FastAPI `BackgroundTasks`, using a fresh session factory, `SupabaseObjectStorage`, `QwenEmbeddingClient`, and `PgVectorChunkSink`. The application lifespan calls `recover_stale_document_jobs(cutoff_minutes=15)` before accepting requests. Add an integration test proving upload reaches `ready` with fake storage/embedding adapters and persisted chunks.

- [ ] **Step 6: Verify and commit**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/ai/test_qwen_gateway.py tests/rag/test_retrieval.py tests/documents/test_processor.py -v
git add app/ai app/rag app/documents/processor.py alembic/versions tests/ai tests/rag
git commit -m "feat: add model gateways and vector retrieval"
```

## Task 7: Cited RAG Conversations

**Files:**
- Create: `backend/app/rag/schemas.py`
- Create: `backend/app/rag/conversation_models.py`
- Create: `backend/app/rag/prompts.py`
- Create: `backend/app/rag/service.py`
- Create: `backend/app/rag/router.py`
- Create: `backend/alembic/versions/0005_conversations.py`
- Create: `backend/tests/rag/test_rag_service.py`
- Create: `backend/tests/rag/test_conversation_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `ChatClient`, `EmbeddingClient`, `retrieve_chunks`, `get_owned_course`.
- Produces: conversations, messages, citations, `compose_answer(question, retrieved) -> AssistantAnswer`, `answer_question(user_id, course_id, conversation_id, question) -> AssistantAnswer`, and conversation routes.

- [ ] **Step 1: Write failing grounded-answer service tests**

Test these exact cases:

```python
async def test_low_relevance_refuses_without_chat_call(fake_chat, rag_service):
    answer = await rag_service.compose_answer(question="资料外问题", retrieved=[])
    assert answer.refused is True
    assert answer.text == "上传的资料中没有足够信息。"
    assert fake_chat.calls == []


async def test_answer_contains_only_valid_citation_ids(rag_service):
    chunks = [
        RetrievedChunk(
            source_id="S1",
            document_name="计算机网络第7版.pdf",
            page_number=214,
            content="TCP 使用三次握手确认双方收发能力并同步初始序列号。",
            distance=0.12,
        )
    ]
    answer = await rag_service.compose_answer(
        question="TCP 为什么三次握手？", retrieved=chunks
    )
    assert [c.page_number for c in answer.citations] == [214]
    assert all(c.document_name for c in answer.citations)
```

Also test prompt-injection text inside retrieved chunks is treated as quoted source data, a hallucinated citation ID is removed, and empty questions are rejected.

- [ ] **Step 2: Implement RAG prompts and citation validation**

Number retrieved chunks `S1..S5`. The system prompt requires Chinese answers, citations in `[S1]` form, and refusal when unsupported. Parse cited IDs from the answer; persist only IDs present in retrieved context. If the model cites none for a non-refusal answer, return `answer_missing_citation` rather than silently accepting it.

- [ ] **Step 3: Write failing conversation API tests**

Cover `POST /courses/{course_id}/conversations`, `GET /courses/{course_id}/conversations`, `GET /conversations/{id}/messages`, and `POST /conversations/{id}/messages`. Assert saved user and assistant messages, citation page/name/snippet, foreign-user 404, document-not-ready response, and daily quota response `429 question_quota_exceeded`.

- [ ] **Step 4: Implement models, routes, and quotas**

Store user messages, assistant text, refusal flag, model, input/output tokens, latency, and citations. Count each user's UTC-day user messages before a model call; default limit is 50. Return citation snippets capped at 300 characters.

- [ ] **Step 5: Migrate, verify, and commit**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/rag/test_rag_service.py tests/rag/test_conversation_api.py -v
git add app/rag app/main.py alembic/versions tests/rag
git commit -m "feat: add grounded conversations with citations"
```

## Task 8: Structured Quiz Generation

**Files:**
- Create: `backend/app/quizzes/models.py`
- Create: `backend/app/quizzes/schemas.py`
- Create: `backend/app/quizzes/prompts.py`
- Create: `backend/app/quizzes/generator.py`
- Create: `backend/app/quizzes/router.py`
- Create: `backend/alembic/versions/0006_quizzes.py`
- Create: `backend/tests/quizzes/test_generator.py`
- Create: `backend/tests/quizzes/test_quiz_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `ChatClient`, ready documents, chunk retrieval, and course ownership.
- Produces: `Quiz`, `Question`, `GeneratedQuiz`, `generate_quiz(course_id, document_ids, counts)`, create/list/get routes.

- [ ] **Step 1: Write failing structured-output tests**

Define Pydantic discriminated unions `MultipleChoiceQuestion` and `ShortAnswerQuestion`. Assert exactly four unique options for multiple choice, answer is one of the options, non-empty `knowledge_point`, difficulty in `easy|medium|hard`, source page exists in selected documents, and short answer contains `rubric_points`.

Test one invalid model response followed by a valid retry, then two invalid responses raising `quiz_generation_invalid`.

- [ ] **Step 2: Implement generator with one repair attempt**

The request schema accepts `document_ids`, `multiple_choice_count` from 1 to 10, and `short_answer_count` from 0 to 5, with a combined maximum of 10. Build context only from selected ready documents. Call the model with JSON Schema response format; on Pydantic failure, retry once with the validation errors.

- [ ] **Step 3: Write failing API and quota tests**

Cover generation, list, detail without answers before submission, selected-document ownership, non-ready documents, and `429 quiz_quota_exceeded` after 10 UTC-day generations.

- [ ] **Step 4: Persist quizzes and questions safely**

Store standard answers and rubrics in the database but omit them from student-facing quiz detail. Store source document and page on every question. Use a transaction so a partial quiz is never visible.

- [ ] **Step 5: Migrate, verify, and commit**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/quizzes/test_generator.py tests/quizzes/test_quiz_api.py -v
git add app/quizzes app/main.py alembic/versions tests/quizzes
git commit -m "feat: generate validated course quizzes"
```

## Task 9: Quiz Submission, Grading, Mistakes, and Analytics

**Files:**
- Create: `backend/app/quizzes/grading.py`
- Create: `backend/app/quizzes/attempt_models.py`
- Modify: `backend/app/quizzes/schemas.py`
- Modify: `backend/app/quizzes/router.py`
- Create: `backend/app/analytics/schemas.py`
- Create: `backend/app/analytics/service.py`
- Create: `backend/app/analytics/router.py`
- Create: `backend/alembic/versions/0007_attempts.py`
- Create: `backend/tests/quizzes/test_grading.py`
- Create: `backend/tests/quizzes/test_submission_api.py`
- Create: `backend/tests/analytics/test_analytics_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: quiz/question models and `ChatClient`.
- Produces: `grade_multiple_choice`, `grade_short_answer`, attempts/answers, `POST /quizzes/{id}/submit`, `GET /courses/{id}/mistakes`, and `GET /courses/{id}/analytics`.

- [ ] **Step 1: Write failing deterministic grading tests**

```python
def test_multiple_choice_is_graded_without_model():
    result = grade_multiple_choice(selected="B", correct="B")
    assert result.score == 10
    assert result.is_correct is True


def test_wrong_answer_is_a_mistake():
    result = grade_multiple_choice(selected="A", correct="B")
    assert result.score == 0
    assert result.is_correct is False
```

Test missing answers, duplicate question IDs, foreign quiz, and resubmission policy. Choose exactly one attempt per user per quiz; a second submit returns `409 quiz_already_submitted`.

- [ ] **Step 2: Implement objective and short-answer grading**

Multiple choice is programmatic. For short answers, request strict JSON `{score: 0..10, feedback: str, missing_points: list[str]}` using the stored standard answer and rubric. Invalid grading output retries once; if still invalid, roll back the entire attempt and return `grading_unavailable`.

- [ ] **Step 3: Write failing analytics tests**

Seed multiple attempts and assert total questions, attempts, average percent score, recent attempts, and weak topics. Define weak score as `wrong_count / answered_count`; order by weak score descending then answered count descending. A question is wrong when `score < 6`.

- [ ] **Step 4: Implement submission transaction and aggregation queries**

Persist the attempt and all answers only after every answer is graded. Return standard answer, explanation, feedback, score, and citation after submission. Mistakes are answer rows with score below 6. Analytics are SQL aggregations, not model output.

- [ ] **Step 5: Migrate, verify, and commit**

```powershell
cd backend
uv run alembic upgrade head
uv run pytest tests/quizzes tests/analytics -v
git add app/quizzes app/analytics app/main.py alembic/versions tests
git commit -m "feat: grade quizzes and report learning analytics"
```

## Task 10: Typed Frontend API, Authentication, and Course List

**Files:**
- Create: `frontend/src/api/contracts.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/app/providers.tsx`
- Create: `frontend/src/features/auth/AuthProvider.tsx`
- Create: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/RegisterPage.tsx`
- Create: `frontend/src/features/courses/CoursesPage.tsx`
- Create: `frontend/src/features/courses/CourseCard.tsx`
- Create: `frontend/src/features/auth/AuthProvider.test.tsx`
- Create: `frontend/src/features/courses/CoursesPage.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: auth and course HTTP contracts from Tasks 2–3.
- Produces: `api.request<T>()`, authenticated route guard, `/login`, `/register`, `/courses`, and navigation to `/courses/:courseId/chat`.

- [ ] **Step 1: Write failing auth and course UI tests**

Use Mock Service Worker. Assert successful login stores the token in `sessionStorage`, `/courses` redirects unauthenticated users to `/login`, API 401 clears auth, courses render newest first, create rejects blank names, and delete requires confirmation.

- [ ] **Step 2: Implement a typed fetch client**

`api.request<T>` attaches `Authorization: Bearer`, parses the shared backend error shape, accepts `AbortSignal`, and throws `ApiError` with `status`, `code`, `message`, and `requestId`. Do not log tokens.

- [ ] **Step 3: Implement routes and auth provider**

Use React Router and TanStack Query. The provider restores only the token, verifies it through `/auth/me`, and renders a loading state during verification. Logout clears session storage and query cache.

- [ ] **Step 4: Implement the course list**

Render create form, responsive cards, empty state, error state, and delete flow. Use accessible labels and keyboard-operable buttons.

- [ ] **Step 5: Verify and commit**

```powershell
cd frontend
npm test -- --run src/features/auth src/features/courses
npm run build
git add src package.json package-lock.json
git commit -m "feat: add frontend authentication and courses"
```

## Task 11: Course Workspace and Document Management UI

**Files:**
- Create: `frontend/src/features/courses/CourseWorkspace.tsx`
- Create: `frontend/src/features/documents/DocumentsPage.tsx`
- Create: `frontend/src/features/documents/UploadPanel.tsx`
- Create: `frontend/src/features/documents/DocumentStatus.tsx`
- Create: `frontend/src/features/documents/DocumentsPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/api/contracts.ts`

**Interfaces:**
- Consumes: document routes and statuses from Tasks 4–5.
- Produces: shared course sidebar, upload progress, status polling, retry/delete controls, and nested course routes.

- [ ] **Step 1: Write failing document workflow tests**

Test valid PDF upload, client-side 20 MB rejection, non-PDF rejection, progress display, polling while `uploaded|processing`, stopping polling at `ready|failed`, scanned-PDF message, retry, delete, and foreign/missing course navigation.

- [ ] **Step 2: Implement the workspace shell**

Create the approved layout with top bar and side links for Q&A, documents, quizzes, mistakes, and analytics. Use `<Outlet />` for nested pages and collapse the sidebar below 900 px.

- [ ] **Step 3: Implement document management**

Upload with `XMLHttpRequest` only where progress events are required; use the typed fetch client elsewhere. Poll processing documents every 2 seconds and stop when none are pending. Display backend `failure_message` and a retry button for `failed`.

- [ ] **Step 4: Verify and commit**

```powershell
cd frontend
npm test -- --run src/features/documents
npm run build
git add src
git commit -m "feat: add course workspace and PDF management"
```

## Task 12: Cited Chat UI

**Files:**
- Create: `frontend/src/features/chat/ChatPage.tsx`
- Create: `frontend/src/features/chat/MessageList.tsx`
- Create: `frontend/src/features/chat/ChatComposer.tsx`
- Create: `frontend/src/features/chat/CitationDrawer.tsx`
- Create: `frontend/src/features/chat/ChatPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/api/contracts.ts`

**Interfaces:**
- Consumes: conversation routes and `AssistantAnswer` from Task 7.
- Produces: conversation selection, cited messages, refusal state, citation drawer, and quota/error feedback.

- [ ] **Step 1: Write failing chat interaction tests**

Test empty composer disabled, one active send at a time, optimistic user message, loading indicator, successful cited answer, refusal text, clicking `[1]` opens document/page/snippet, network retry preserving draft, and 429 quota message.

- [ ] **Step 2: Implement chat state with TanStack Query**

Create a conversation lazily on first send. Invalidate message history after success. Cancel in-flight requests when leaving the course. Render assistant text as plain text with recognized citation tokens converted into buttons; do not render arbitrary model HTML.

- [ ] **Step 3: Implement the approved three-column layout**

The center column contains messages and composer. The right column shows ready documents, “generate quiz” navigation, and the analytics summary. On narrow screens, the right column moves below chat and citations open as a modal drawer.

- [ ] **Step 4: Verify and commit**

```powershell
cd frontend
npm test -- --run src/features/chat
npm run build
git add src
git commit -m "feat: add cited course chat experience"
```

## Task 13: Quiz, Mistakes, and Analytics UI

**Files:**
- Create: `frontend/src/features/quizzes/QuizListPage.tsx`
- Create: `frontend/src/features/quizzes/QuizBuilder.tsx`
- Create: `frontend/src/features/quizzes/QuizAttemptPage.tsx`
- Create: `frontend/src/features/quizzes/QuizResultPage.tsx`
- Create: `frontend/src/features/quizzes/MistakesPage.tsx`
- Create: `frontend/src/features/analytics/AnalyticsPage.tsx`
- Create: `frontend/src/features/quizzes/QuizFlow.test.tsx`
- Create: `frontend/src/features/analytics/AnalyticsPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/api/contracts.ts`

**Interfaces:**
- Consumes: quiz, submission, mistake, and analytics APIs from Tasks 8–9.
- Produces: quiz creation, answer forms, result details, mistake filtering, and course dashboard.

- [ ] **Step 1: Write failing end-user quiz tests**

Test selecting only ready documents, question-count limits, hidden answers before submit, required answers, duplicate-submit prevention, objective and short-answer result rendering, citation links, empty mistakes, and quota errors.

- [ ] **Step 2: Implement quiz builder and attempt forms**

Use discriminated question types from `contracts.ts`. Keep draft answers in component state keyed by question ID. After submission, replace the form with immutable per-question results; never request or infer standard answers before submission.

- [ ] **Step 3: Write failing analytics presentation tests**

Assert total attempts, question count, average percentage, weak-topic order, recent attempts, and accessible empty state. Verify scores render without division-by-zero or `NaN`.

- [ ] **Step 4: Implement mistakes and analytics**

Render weak topics as an accessible table plus horizontal bars, not a chart-only view. Mistakes show the user's answer, standard answer, explanation, score, feedback, and source citation.

- [ ] **Step 5: Verify and commit**

```powershell
cd frontend
npm test -- --run src/features/quizzes src/features/analytics
npm run build
git add src
git commit -m "feat: add quiz and learning analytics interfaces"
```

## Task 14: Repeatable RAG Evaluation

**Files:**
- Create: `evals/dataset.jsonl`
- Create: `evals/run_rag_eval.py`
- Create: `evals/README.md`
- Create: `backend/tests/evals/test_metrics.py`
- Create: `backend/app/rag/evaluation.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: document ingestion, retrieval, and answer APIs.
- Produces: `EvalCase`, `EvalMetrics`, `evaluate_cases(cases, client)`, and JSON/Markdown evaluation reports.

- [ ] **Step 1: Select a redistributable source document and record its license**

Use a public-domain or explicitly permissive Chinese computer-science course PDF. Store its canonical source URL, license, SHA-256, and retrieval date in `evals/README.md`. Do not commit a PDF unless its license explicitly allows redistribution; otherwise provide `download_source.ps1` with the fixed official URL and SHA-256 verification.

- [ ] **Step 2: Create at least 20 fully labeled cases**

Each JSONL row must follow:

```json
{"id":"cn-001","question":"进程与程序的核心区别是什么？","answerable":true,"expected_pages":[12],"required_terms":["动态", "执行"]}
{"id":"cn-016","question":"这份资料如何评价量子纠错？","answerable":false,"expected_pages":[],"required_terms":[]}
```

Include at least 15 answerable and 5 unanswerable questions, distributed across the document rather than one chapter.

- [ ] **Step 3: Write failing metric tests**

Test `retrieval_hit_at_5`, citation-page accuracy, refusal accuracy, mean latency, and mean token use with fixed synthetic cases, including zero denominators.

- [ ] **Step 4: Implement the evaluation runner**

The runner creates or reuses an evaluation course, ingests the fixed document, waits for `ready`, sends every question, records raw result JSON, and writes a dated Markdown summary. Include model IDs, embedding dimension, retrieval threshold, git commit, dataset hash, date, and total estimated token use.

- [ ] **Step 5: Verify and commit**

```powershell
cd backend
uv run pytest tests/evals/test_metrics.py -v
cd ..
cd backend
uv run python ../evals/run_rag_eval.py --help
git add evals backend/app/rag/evaluation.py backend/tests/evals README.md
git commit -m "feat: add reproducible RAG quality evaluation"
```

## Task 15: End-to-End Verification, CI, Deployment, and Portfolio Documentation

**Files:**
- Create: `frontend/e2e/core-flow.spec.ts`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/vercel.json`
- Create: `backend/app/ai/fake.py`
- Create: `backend/tests/ai/test_fake_provider_guard.py`
- Create: `.github/workflows/ci.yml`
- Create: `infra/render.yaml`
- Modify: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/deployment.md`
- Create: `docs/interview-notes.md`
- Create: `docs/screenshots/course-workspace.png`
- Create: `docs/screenshots/quiz-result.png`
- Create: `backend/scripts/seed_demo.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: the complete application from Tasks 1–14.
- Produces: CI, deployment manifests, public documentation, a repeatable demo, and an interview-ready project narrative.

- [ ] **Step 1: Write the failing Playwright core-flow test**

Automate: register, create course, upload the licensed fixture PDF, wait for `ready`, ask a grounded question, open its citation, generate a two-question quiz, submit it, and view analytics. Use a deterministic fake-AI mode in CI configured only by `AI_PROVIDER=fake`; production must reject fake mode.

- [ ] **Step 2: Implement CI-safe fake providers**

Create deterministic embedding/chat adapters in `backend/app/ai/fake.py`. Activate them only when `ENVIRONMENT=test` and `AI_PROVIDER=fake`; application startup must fail if fake provider is selected in any other environment. `test_fake_provider_guard.py` proves both the allowed test configuration and rejected production configuration.

- [ ] **Step 3: Run the E2E test locally**

```powershell
docker compose -f infra/docker-compose.yml up -d db
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8000
# In a second terminal:
cd frontend
npm run dev -- --port 5173
npx playwright test e2e/core-flow.spec.ts
```

Expected: the complete flow passes without external model calls.

- [ ] **Step 4: Add GitHub Actions**

Use a `pgvector/pgvector:pg16` service. Jobs must run backend Ruff, mypy, migrations, pytest; frontend Vitest and production build; then Playwright using the fake provider. Cache uv and npm dependencies. Do not put real API keys in CI.

- [ ] **Step 5: Add deployment declarations**

`infra/render.yaml` runs `uv sync --frozen`, `uv run alembic upgrade head`, then Uvicorn. `frontend/vercel.json` configures SPA route rewrites. Vercel builds the `frontend` directory. Supabase provides PostgreSQL, pgvector extension, and a private `course-pdfs` bucket. `backend/scripts/seed_demo.py` idempotently creates the documented demo user and one empty sample course using environment-provided demo credentials; it never contains a committed password. `docs/deployment.md` lists exact environment variables, CORS domain, migration and seed commands, cold-start behavior, quota settings, and rollback steps.

- [ ] **Step 6: Write portfolio-grade README and interview notes**

README must contain: problem, live demo and demo account, feature screenshots, architecture, data flow, local setup, API docs link, security decisions, RAG evaluation table, known limitations, and roadmap. Extend the Playwright flow to capture deterministic `course-workspace.png` and `quiz-result.png` at 1440×900, then verify both images visually before committing them. `docs/interview-notes.md` must answer: why pgvector, how citations work, how hallucinations are reduced, why no LangChain, how cross-user access is prevented, how invalid JSON is handled, and what would change at production scale.

- [ ] **Step 7: Run the full release gate**

```powershell
cd backend
uv run ruff check app tests
uv run mypy app
uv run pytest -q
uv run alembic upgrade head
cd ../frontend
npm test -- --run
npm run build
npx playwright test
cd ..
git diff --check
git status --short
```

Expected: every command exits 0; only intentional documentation/evaluation result changes remain unstaged.

- [ ] **Step 8: Commit the release assets**

```powershell
git add .github .env.example README.md docs infra backend/app/ai/fake.py backend/tests/ai/test_fake_provider_guard.py backend/scripts/seed_demo.py frontend/e2e frontend/playwright.config.ts frontend/vercel.json
git commit -m "docs: prepare StudyPilot portfolio release"
```

## Completion Definition

The implementation is complete only when all 15 task commits exist, the full release gate passes, the licensed 20-case evaluation is reproducible, the deployed frontend can reach the deployed API, a demo user can finish the approved flow, and README links and screenshots match the deployed version.
