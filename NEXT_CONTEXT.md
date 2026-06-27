# LLM Guardrails 项目交接

## Resume Prompt

继续维护 `F:\llm-guardrails`。先阅读根目录 `NEXT_CONTEXT.md`，检查 Git 工作树、8000/5173 端口和 `logs/pipeline.log`，保留所有现有改动。当前前后端功能已实现但尚未提交；优先清理前端构建生成的源码旁 `.js` 文件、补 UI/E2E 验证，再按用户的新要求继续开发。

## Project Paths

- 根目录：`F:\llm-guardrails`
- 后端：`F:\llm-guardrails\core`
- 检测模块：`F:\llm-guardrails\detection`
- 前端：`F:\llm-guardrails\frontend`
- 数据库迁移：`F:\llm-guardrails\alembic`
- 宝塔部署配置：`F:\llm-guardrails\deploy`
- 主流程日志：`F:\llm-guardrails\logs\pipeline.log`
- 部署说明：`F:\llm-guardrails\README.md`

## Current Objective

维护一个多用户隔离的 LLM 安全对话平台：用户输入先经过规则脱敏、向量检索和 LLM 安全分析，只有通过或脱敏后的文本才发送给回答模型；前端提供类似主流聊天产品的流式交互。

## User Decisions / Hard Constraints

- 前端使用 Vue 3 + TypeScript + Vite，整体为蓝色系。
- 布局：左侧历史记录，右侧对话，左下设置。
- 全部用户数据隔离：会话、消息、保密库、公开库、模型配置。
- 账号方式：开放用户名 + 密码注册，不做邮箱找回。
- 数据库：MySQL；本地和宝塔均只填写 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`。
- 宝塔使用面板 MySQL、Nginx 和 Python 项目管理，不使用 Docker。
- API Key 为传统密码框：默认黑点、眼睛显示明文、可直接修改；清空保存会删除模型配置。
- 未配置模型时前后端都禁止发送消息。
- 风险结果显示在助手回复上方，不显示在用户消息上方。
- 流程日志只要主体流水，不要 HTTP access/app/error 日志。
- `logs/record/` 内容永远不要上传 GitHub。
- 不输出或提交任何 `.env` 密钥。

## Architecture

- FastAPI 入口：`core/app.py`，所有业务 API 前缀为 `/api`。
- 异步数据库：SQLAlchemy 2 + `asyncmy`，本地测试兼容 `aiosqlite`。
- 数据表定义：`core/models.py`。
- 鉴权：数据库会话 + HttpOnly Cookie，密码 Argon2id。
- API Key：使用 `APP_ENCRYPTION_KEY` 派生 Fernet 密钥后加密入库。
- SSE 聊天：`POST /api/conversations/{id}/messages/stream`。
- 用户安全检测组装：`core/guardrail_service.py`。
- 对话编排与流水日志：`core/routers/chat.py`。
- 用户模型配置：`core/routers/settings.py`。
- 前端当前主要集中在 `frontend/src/App.vue`，样式拆分为 `style.css`、`model-status.css`、`blue-theme.css`。

## Implemented Backend

- 注册、登录、退出、当前用户、修改密码。
- 会话创建、列表、重命名、删除和消息历史。
- 保密库与公开库 CRUD、JSONL 导入。
- 每用户独立 OpenAI-compatible API Key、Base URL、模型名。
- 模型配置查询、明文 Key 的鉴权读取、保存、删除和测试连接。
- 测试连接错误分类：401、403、404、429、超时、连接失败、400 和其他 HTTP 错误。
- 模型地址默认只允许公网 HTTPS，`ALLOW_PRIVATE_MODEL_HOSTS=true` 才允许内网模型。
- SSE 事件：`decision`、`delta`、`complete`、`error`。
- 多轮上下文只使用历史安全文本；被拦截内容不进入模型。
- 拦截时创建一条助手消息，便于历史回显风险结果。
- 基于 IP 的单进程频率限制和 Origin 校验。

## Main Pipeline Logging

- 当前只写 `logs/pipeline.log`，JSON Lines + 轮转。
- 同一次请求使用统一 `request_id`。
- 阶段固定为：
  1. `input`
  2. `rule_match`
  3. `vector_search`
  4. `llm_analysis`
  5. `call_llm`
- `call_llm` 会记录 started/completed/error/interrupted；拦截时记录 `skipped`。
- 不记录 API Key。
- 日志会记录用户原始输入、安全上下文和模型完整回复，这是用户明确要求；部署时注意日志目录权限和数据保留。
- 旧 `app.log/access.log/error.log` 已停用并删除。

## Implemented Frontend UX

- 登录/注册页、会话侧栏、聊天区、设置弹窗。
- 右上角显示模型名：正常绿点，未配置或连接测试失败红点。
- 无模型配置时禁用输入框与发送按钮。
- 发送后立即显示动态省略号：先“正在进行安全检测”，获得 decision 后显示“正在思考”。
- 风险状态为“安全通过 / 已脱敏处理 / 已阻止发送”，位于助手回复上方。
- 脱敏结果可折叠查看实际发送给模型的内容。
- 回复下方有复制、重新生成按钮。
- Markdown 使用 `markdown-it`，输出经 DOMPurify 清洗。
- 蓝色主题、蓝色渐变发送按钮、蓝色盾牌 favicon。
- 空会话只显示“有什么可以帮助您的？”和安全检测说明。
- API Key 密码框打开设置时通过鉴权接口取回明文；生产必须使用 HTTPS。

## Database / Deployment

- `.env` 已配置五项 DB 字段并成功连接本机 MySQL；不要在交接文件记录实际账号或密码。
- MySQL 可导入文件：`deploy/llm_guardrails.sql`。
- Alembic 初始版本：`0001_initial`。
- 宝塔 Nginx 片段：`deploy/bt-nginx.conf`，已关闭 SSE 代理缓冲。
- 前端部署产物目录：`frontend/dist`（被 Git 忽略）。
- 服务端建议：FastAPI 监听 `127.0.0.1:8000`，宝塔 Nginx 同域代理 `/api`。

## Current Runtime State

- 本轮最后确认前端 `http://127.0.0.1:5173` 返回 200。
- 本轮最后确认后端 `http://127.0.0.1:8000/api/health` 返回 `ok`。
- 后端为正常网络权限启动，外部模型域名 443 可连接。
- 运行进程由当前工具会话托管；新会话不要假定仍然存活，应重新检查端口和健康接口。
- 当前用户模型配置已入库；曾经的连接失败原因是后端运行在受限沙箱，而不是配置保存失败。

## Validation Facts

- 最近后端测试：`11 passed`。
- 命令：`.\.venv\Scripts\python.exe -m pytest -q`
- 最近前端生产构建：通过。
- 命令：`cd frontend; npm run build`
- Python compileall 和 `git diff --check` 最近均通过。
- 存在一个 Starlette TestClient 关于 `httpx2` 的弃用警告，不影响测试结果。

## Git State

- 分支：`main`，远程为 `origin/main`。
- 最新已提交版本：`e251844 feat: add rule-based detection and semantic integration`。
- 本次前端、数据库、鉴权、部署、日志等大量改动均尚未 commit/push。
- `project_infor/img.png` 已暂存，是用户提供的 MySQL Workbench 截图，不要擅自删除。
- 工作树有大量新增文件；提交前必须完整检查 `git status`。
- `.env`、`logs/record/`、`logs/*.log`、`frontend/node_modules/`、`frontend/dist/` 和本地 SQLite 文件被忽略。

## Important Files

- `core/app.py`：应用装配、CORS、中间件和生命周期。
- `core/models.py`：用户、会话、消息、知识库和模型配置表。
- `core/routers/chat.py`：检测、SSE、历史上下文、拦截助手回复和流水日志。
- `core/routers/settings.py`：API Key 显示/保存/删除和连接测试。
- `core/pipeline_logger.py`：五阶段 JSONL 日志写入。
- `detection/semantic_client.py`：规则与语义检测 trace 合并。
- `frontend/src/App.vue`：当前全部主要页面与交互。
- `frontend/src/blue-theme.css`：蓝色主题、思考动画、回复操作按钮。
- `deploy/llm_guardrails.sql`：宝塔可直接选择导入的 MySQL 表结构。
- `README.md`：本地及宝塔部署说明。

## Known Pitfalls / Need Verify

- `vue-tsc -b` 当前会在 `frontend/src` 旁生成 `App.vue.js`、`main.js`、`api.js` 等编译文件；这些不应提交。下一步应在 `tsconfig.json` 设置 `noEmit: true`，删除生成文件，并重新构建验证。
- PowerShell 5 直接 `Get-Content` UTF-8 无 BOM 文件时可能显示中文乱码；Python/Vite 实际按 UTF-8 读取正常，不要据终端显示盲目重写中文。
- Windows 上通过工具终止长运行 cell 不一定杀死提权后的 Uvicorn 子进程；重启前检查 8000 端口 PID，只停止明确监听该端口的旧进程。
- FastAPI 频率限制存在进程内，多 worker 会各自计数；当前宝塔建议一个 Uvicorn worker。
- 模型测试和聊天需要外部网络；受限沙箱中会报 `APIConnectionError`。
- API Key 明文读取是用户明确要求的传统密码框体验；必须保持 HTTPS、HttpOnly 会话和用户归属检查。
- “重新生成”当前会以同一用户文本追加新一轮消息，不会覆盖旧回复。
- 尚未增加浏览器级 E2E 测试；主要依赖后端 pytest 和前端 production build。

## Exact Next Steps

1. 运行 `git status --short`，确认用户文件和未提交改动。
2. 检查 `http://127.0.0.1:8000/api/health` 与 `http://127.0.0.1:5173`；需要时重启。
3. 修正前端 TypeScript 配置为不向 `src` 发射 JS，并只删除确认由构建生成的 `.js` 文件。
4. 使用浏览器手工验证：发送动画、decision 位置、脱敏折叠、拦截助手消息、复制、重新生成、API Key 眼睛和测试连接。
5. 发送一条完整消息后检查 `logs/pipeline.log` 是否严格产生五阶段且没有 API Key。
6. 再运行 pytest、前端 build 和 `git diff --check`。
7. 只有用户明确要求时才 commit/push；推送时继续排除 `logs/record/`。

## Acceptance Checklist

- 未配置模型无法发送消息。
- 发送后立即有动态反馈，无空白等待。
- 风险判定只显示在助手回复上方。
- pass/redact 才调用回答模型；block 的流水日志为 skipped。
- 脱敏时模型上下文不含原始敏感值。
- 每用户无法读取其他用户的会话、知识库和 API Key。
- `pipeline.log` 可通过 request_id 还原完整处理链路。
- 宝塔导入 SQL、静态站点、同域 `/api` 和 SSE 均可部署。
