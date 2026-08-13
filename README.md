# StudyPilot

面向大学生课程资料的 AI 学习助手：上传文字版 PDF，获得可追溯到页码的问答，生成基于原文的测验，并从错题中定位薄弱知识点。

> 作品集状态：核心产品、自动化测试、20 题 RAG 评测基准和部署声明已完成。公开体验地址与演示账号将在首次部署后补充；仓库不会提交演示密码。

## 要解决的问题

长篇课程资料难以检索，而通用聊天机器人经常给出无法核查的答案。StudyPilot 把回答限制在学生上传的课程 PDF 内，为关键结论提供文件名和实际页码引用；测验也必须引用已选资料中的真实来源页。

## 功能展示

| 课程问答工作区 | 测验结果 |
| --- | --- |
| ![带引用的课程问答](docs/screenshots/course-workspace.png) | ![逐题反馈的测验结果](docs/screenshots/quiz-result.png) |

- 邮箱注册、登录与课程级数据隔离
- 私有 PDF 上传、解析、Token 分块、向量化、失败恢复
- Top-5 语义检索、资料不足拒答、可点击页码引用
- JSON Schema 约束的选择题/简答题生成与评分
- 错题本、薄弱知识点、得分趋势和最近测验
- 确定性无外部调用 E2E、GitHub Actions 与部署清单

## 架构与数据流

```text
React/Vite → FastAPI → PostgreSQL + pgvector
                      ↘ Supabase 私有 PDF 存储
                      ↘ Qwen Chat / Embedding
```

文档进入 `uploaded → processing → ready/failed` 状态机。就绪分块存入 pgvector；提问先在当前课程范围内检索，再把编号来源交给模型。服务端只接受检索结果中存在的 `[S1]` 引用，并将引用页随回答持久化。测验生成同样经过来源页和 Pydantic 二次校验。详见 [架构说明](docs/architecture.md)。

## 技术栈

- React 19、TypeScript、Vite、TanStack Query、Playwright、Vitest
- FastAPI、Pydantic、SQLAlchemy 2、Alembic、PyMuPDF
- PostgreSQL 16、pgvector、Supabase Storage
- 阿里云百炼 `qwen-plus`、`text-embedding-v4`
- GitHub Actions、Render、Vercel

## 本地运行

要求：Python 3.12+、Node.js 24+、Docker Desktop。复制配置模板，至少设置本地 `JWT_SECRET`；真实问答还需百炼和 Supabase 凭据。

```powershell
Copy-Item .env.example .env
docker compose -f infra/docker-compose.yml up -d db

cd backend
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

另开终端：

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

访问 `http://localhost:5173`；后端交互文档为 [http://localhost:8000/docs](http://localhost:8000/docs)，健康检查为 [http://localhost:8000/health](http://localhost:8000/health)。

### 不花模型费用的端到端测试

仅测试环境允许使用确定性假提供商：

```powershell
$env:ENVIRONMENT="test"
$env:AI_PROVIDER="fake"
$env:DATABASE_URL="postgresql+asyncpg://studypilot:studypilot@localhost:5432/studypilot"
$env:JWT_SECRET="local-e2e-secret-that-is-long-enough"
$env:CORS_ORIGINS="http://127.0.0.1:5173"
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8000

# 另开终端
cd frontend
npm run test:e2e
```

`AI_PROVIDER=fake` 在 development、staging 或 production 会使应用启动失败，避免测试替身误上线。

## 安全与可靠性决策

- Argon2 密码哈希、短期 JWT、稳定的 401/404 错误，不回传密码或供应商异常。
- 所有课程资源按当前用户校验；另一个用户访问时返回 404。
- PDF 同时校验扩展名、MIME、魔数、体积、页数与文本可提取性；对象存储保持私有。
- 文档内容作为不可信数据包裹，提示词明确禁止执行资料中的指令。
- 模型 JSON 经 Schema 与业务规则双重校验，失败可修复一次，仍无效则拒绝落库。
- 每日上传、问答、测验额度，供应商超时与可重试错误统一处理；日志不打印密钥和原文全文。

## RAG 质量评测

固定评测基于 GPL v3《xv6 中文文档》，包含 15 个可回答问题和 5 个应拒答问题。PDF 通过固定 URL 下载并校验 SHA-256，不把来源文件直接提交仓库。

| 指标 | 固定口径 | 当前公开结果 |
| --- | --- | --- |
| Retrieval Hit@5 | 可回答问题的 Top-5 命中标注页比例 | 待使用部署模型运行 |
| 引用页准确率 | 实际引用页属于标注页的比例 | 待使用部署模型运行 |
| 拒答准确率 | 可回答不拒答、越界问题正确拒答 | 待使用部署模型运行 |
| 平均延迟 / Token | 20 题端到端均值 | 待使用部署模型运行 |

没有填写虚构分数。运行真实评测会调用模型并产生费用：

```powershell
powershell -ExecutionPolicy Bypass -File .\evals\download_source.ps1
.\backend\.venv\Scripts\python.exe .\evals\run_rag_eval.py --base-url http://localhost:8000
```

数据许可、问题标注、指标定义和报告字段见 [评测说明](evals/README.md)。

## 验证

```powershell
cd backend
uv run ruff check app tests
uv run mypy app
uv run pytest -q
uv run alembic upgrade head

cd ../frontend
npm test -- --run
npm run build
npm run test:e2e
```

CI 使用 `pgvector/pgvector:pg16`，不需要任何真实模型或存储密钥。

## 部署与演示账号

按 [部署指南](docs/deployment.md) 配置 Vercel、Render 和 Supabase。`backend/scripts/seed_demo.py` 只从环境读取 `DEMO_EMAIL` 与 `DEMO_PASSWORD`，可幂等创建一个空示例课程。请勿把真实密码写入 README、提交记录或 CI。

## 已知限制

- 当前只支持可提取文字的 PDF，不做 OCR、表格或图片语义理解。
- 文档处理使用进程内后台任务；实例意外退出后依赖启动恢复，不等同于持久任务队列。
- 检索是固定阈值与 Top-5，没有 reranker 或查询改写。
- 简答题评分仍是模型判断，适合作为学习反馈，不适合正式考试定分。
- 尚未发布公开在线地址，也尚未运行会产生费用的完整真实模型基准。

## Roadmap

1. OCR 与版面感知解析，支持公式、表格和扫描讲义。
2. 持久任务队列、独立 worker、取消与实时进度。
3. 混合检索、reranker 与按课程类型自适应阈值。
4. 评测结果趋势、成本监控、供应商回退与可观测性。
5. 课程共享、导出复习计划和移动端适配。

## 更多文档

- [产品设计](docs/superpowers/specs/2026-08-10-studypilot-design.md)
- [实施计划](docs/superpowers/plans/2026-08-10-studypilot-implementation.md)
- [架构说明](docs/architecture.md)
- [部署指南](docs/deployment.md)
- [面试讲解提纲](docs/interview-notes.md)
- [RAG 评测说明](evals/README.md)
