# 部署指南

推荐组合：Vercel 托管 `frontend`，Render 托管 `backend`，Supabase 提供 PostgreSQL、pgvector 与私有对象存储。仓库中的声明参考了 Render Blueprint 的 `rootDir` / `preDeployCommand` 和 Vercel 官方 Vite SPA rewrite 配置。

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
| `CORS_ORIGINS` | 精确的 Vercel HTTPS 域名；多个域名用逗号分隔 |
| `DASHSCOPE_API_KEY` | 百炼服务端密钥 |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | service-role key，仅后端保存 |
| `SUPABASE_STORAGE_BUCKET` | `course-pdfs` |

可调变量：`CHAT_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION`、`MAX_PDF_BYTES`、`MAX_PDF_PAGES`、三项 `DAILY_*_QUOTA`、`DOCUMENT_JOB_TIMEOUT_MINUTES`、`REQUEST_TIMEOUT_SECONDS`。

Blueprint 在构建时运行 `uv sync --frozen --no-dev`，部署前运行 `uv run alembic upgrade head`，启动命令为 Uvicorn。Render 的 pre-deploy command 需要支持该能力的付费服务；若选择不支持它的套餐，应在每次发布前手动运行迁移，再部署应用。健康检查为 `/health`。

免费或休眠实例可能冷启动。前端会保留未成功发送的问题，但首次请求仍可能等待几十秒；正式演示前应先访问 `/health` 预热。

## 3. Vercel 前端

- Root Directory：`frontend`
- Framework Preset：Vite
- Build Command：`npm run build`
- Output Directory：`dist`
- 环境变量：`VITE_API_BASE_URL=https://<render-service>.onrender.com`

`frontend/vercel.json` 把深层路由重写到 `index.html`。部署后，把最终 Vercel 域名写回 Render 的 `CORS_ORIGINS`，重新部署后端。

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
