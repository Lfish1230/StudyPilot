# StudyPilot RAG 评测集

该目录提供一套可重复运行的中文 RAG 质量评测。数据集包含 20 个问题：15 个可从固定资料回答的问题，以及 5 个应当拒答的越界问题。

## 固定来源与许可

- 标题：`xv6 中文文档`
- 中文翻译项目（应在转载和引用时署名）：https://github.com/ranxian/xv6-chinese
- 核验的翻译源码提交：`4f19812a389a74ee9a6ff980b7b34a30722b6118`
- 固定 PDF 镜像 URL：https://lihaoran.work/wp-content/uploads/2023/08/xv6-chinese.pdf
- 许可：中文翻译采用 GNU General Public License v3.0；PDF 第 4 页及项目 README 均注明该许可和署名要求
- SHA-256：`51D28581A043C438CF91F21B66DC3EBA914404CC48CDD8F763AB15C10DD36BF7`
- 核验日期：2026-08-13
- 文档页数：65

上面的 PDF URL 是第三方静态镜像，不被当作许可依据；许可依据是翻译项目 README 和 PDF 自带的第 4 页声明。镜像只作为可重复取得同一 65 页排版版本的下载位置，脚本强制校验 SHA-256。若镜像失效，应从相同源码版本重新生成并重新标注页码，而不能静默替换文件。

PDF 不提交到本仓库。运行以下命令下载并校验固定文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\evals\download_source.ps1
```

如果远端文件发生改变，脚本会删除未通过哈希验证的下载文件并报错，避免无意中更换评测基准。

## 数据集字段

每行是一个 JSON 对象：

- `id`：稳定用例编号。
- `question`：发送给问答 API 的中文问题。
- `answerable`：固定资料能否回答。
- `expected_pages`：PDF 的实际页码，不是章节内部印刷页码。
- `required_terms`：人工审阅回答完整性时应出现的关键概念；当前核心自动指标不把措辞差异直接判错。

## 指标口径

- `retrieval_hit_at_5`：可回答用例中，前五个检索来源至少命中一个标注页的比例。
- `citation_page_accuracy`：所有实际引用页中，属于对应标注页的比例。
- `refusal_accuracy`：可回答用例未拒答、不可回答用例正确拒答的总体比例。
- `mean_latency_ms`：端到端提问平均延迟。
- `mean_token_use`：每个问题平均输入与输出 Token 总和。

## 运行

先启动后端、数据库和文档处理依赖，并在 `.env` 配置真实模型及对象存储。评测会产生真实模型费用：

```powershell
.\backend\.venv\Scripts\python.exe .\evals\run_rag_eval.py --base-url http://localhost:8000
```

脚本会复用同名评测课程，并用 PDF 哈希前缀组成稳定文档名；若课程中还没有该固定版本，则上传并等待处理完成。随后为每个用例创建独立对话，记录原始结果，并在 `evals/results/` 生成带时间戳的 JSON 与 Markdown 报告。不要提交结果目录中的本地报告。默认每日问答额度可运行两次完整评测；同一天需要更多轮次时，应显式提高本地评测环境的 `DAILY_QUESTION_QUOTA`。
