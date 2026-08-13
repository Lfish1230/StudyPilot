# StudyPilot

StudyPilot 是一个面向大学生的 AI 课程学习助手。用户可以上传文字版 PDF，进行带页码引用的资料问答，生成测验，并根据错题查看薄弱知识点。

当前阶段：核心功能与可重复 RAG 评测已实现。

## 技术栈

- React 19 + TypeScript + Vite
- FastAPI + Pydantic + SQLAlchemy
- PostgreSQL 16 + pgvector
- 阿里云百炼 `qwen-plus` 与 `text-embedding-v4`

## 文档

- [产品设计](docs/superpowers/specs/2026-08-10-studypilot-design.md)
- [实施计划](docs/superpowers/plans/2026-08-10-studypilot-implementation.md)
- [RAG 质量评测](evals/README.md)

## RAG 质量评测

项目包含基于 GPL v3《xv6 中文文档》的固定中文评测集：15 个可回答问题和 5 个应拒答问题。评测记录 Top-5 检索命中率、引用页准确率、拒答准确率、延迟与 Token 用量，并输出带模型版本、配置、Git 提交和数据哈希的 JSON/Markdown 报告。

```powershell
powershell -ExecutionPolicy Bypass -File .\evals\download_source.ps1
.\backend\.venv\Scripts\python.exe .\evals\run_rag_eval.py --help
```

完整运行方式、资料许可与指标定义见 [evals/README.md](evals/README.md)。执行真实评测会调用已配置的模型服务并产生费用；仅运行 `--help`、指标单元测试和下载校验不会调用模型。

## 本地要求

- Python 3.12+
- Node.js 24+
- Docker Desktop（数据库启动前安装）
