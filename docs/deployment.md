# 部署指南

推荐组合：Render Static Site 托管 `frontend`，Render Web Service 托管 `backend`，Supabase 提供 PostgreSQL、pgvector 与私有对象存储。仓库中的 Blueprint 可一次创建前后端两个免费服务。

## 1. Supabase

1. 新建项目，在 SQL Editor 执行 `create extension if not exists vector;`。
2. Storage 新建私有 bucket：`course-pdfs`，不要设为 public。
3. 取得 PostgreSQL 连接串、Project URL 与 service-role key。`SUPABASE_SERVICE_KEY` 只能放后端。
4. 将连接串改为 SQLAlchemy 异步形式 `postgresql+asyncpg://...`。若使用连接池端口，按 Supabase 控制台给出的参数保留 SSL 设置。

## 2. Render 后端

使用仓库的 `infra/render.yaml` 创建 Blueprint（该文件不在默认根路径，导入时需指定它），或在面板等价配置 `backend` 为 Root Directory。

必填环境变量：

| 变量 | 说明 |
| --- | --- |
| `ENVIRONMENT=production` | 开启生产环境语义 |
| `AI_PROVIDER=qwen` | 线上禁止 `fake` |
| `DATABASE_URL` | Supabase 异步 PostgreSQL 连接串 |
| `JWT_SECRET` | 至少 32 字节随机值 |
| `CORS_ORIGINS` | 精确的前端 HTTPS 域名；Blueprint 已预设 Render 前端域名 |
| `DASHSCOPE_API_KEY` | 百炼服务端密钥 |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | service-role key，仅后端保存 |
| `SUPABASE_STORAGE_BUCKET` | `course-pdfs` |

可调变量：`CHAT_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION`、`MAX_PDF_BYTES`、`MAX_PDF_PAGES`、三项 `DAILY_*_QUOTA`、`DOCUMENT_JOB_TIMEOUT_MINUTES`、`REQUEST_TIMEOUT_SECONDS`。

Blueprint 默认使用 Render 免费 Web Service：构建时运行 `uv sync --frozen --no-dev`，启动时先运行 `uv run alembic upgrade head`，迁移成功后再启动 Uvicorn。单实例免费服务以这种方式保持数据库结构最新，不依赖付费的 pre-deploy command；升级到多实例方案前，应改回独立的 pre-deploy migration。健康检查为 `/health`。

免费或休眠实例可能冷启动。前端会保留未成功发送的问题，但首次请求仍可能等待几十秒；正式演示前应先访问 `/health` 预热。

## 3. Render 前端

- 服务类型：Static Site
- Root Directory：`frontend`
- Build Command：`npm ci && npm run build`
- Publish Directory：`dist`
- 环境变量：`VITE_API_BASE_URL=https://studypilot-lfish1230-api.onrender.com`

Blueprint 使用 `/* -> /index.html` rewrite 支持 React Router 深层路由，并设置基础安全响应头。若服务名称改变，必须同步更新前端的 `VITE_API_BASE_URL` 和后端的 `CORS_ORIGINS`，然后重新部署两个服务。

Vercel 仍可作为备选：使用 `frontend/vercel.json` 部署，并将 Vercel HTTPS 域名写入后端 `CORS_ORIGINS`。

## 4. 可选演示账号

先在部署环境临时设置 `DEMO_EMAIL`、`DEMO_PASSWORD`（至少 10 字符）和可选的 `DEMO_COURSE_NAME`，然后从 `backend` 执行：

```bash
uv run python scripts/seed_demo.py
```

脚本可重复执行：已有用户和同名课程不会重复创建。脚本和仓库不包含密码。创建后可移除 `DEMO_PASSWORD`；若邮箱已存在，脚本不会覆盖其密码。

## 5. 发布与回滚

1. 发布前在本地或 CI 跑完整 release gate，并备份数据库。
2. 迁移成功后再切换应用版本。当前迁移均向前兼容；破坏性 schema 变更应采用 expand/contract 两阶段。
3. 应用回滚：在 Render 选择上一个成功部署；确认旧代码能读取当前 schema。
4. 数据回滚：仅在迁移确实破坏数据时使用已验证的 Supabase 备份恢复，不要直接对生产库执行 `alembic downgrade`。
5. 密钥泄漏时立刻在供应商处撤销并轮换，再触发后端重新部署。

官方参考：[Render Blueprint 规范](https://render.com/docs/blueprint-spec)、[Render 部署流程](https://render.com/docs/deploys)、[Vercel Vite SPA](https://vercel.com/docs/frameworks/frontend/vite)。
