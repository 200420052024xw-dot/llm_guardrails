# LLM Guardrails

带用户隔离、保密检测、脱敏和流式回答的智能对话工作台。

## 数据库配置

不需要通过命令行连接数据库。使用 MySQL Workbench 或宝塔创建数据库，然后导入：

```text
deploy/llm_guardrails.sql
```

在 `.env` 中填写数据库面板提供的五项信息：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=llm_guardrails
DB_PASSWORD=数据库密码
DB_NAME=llm_guardrails
```

项目会自动组合连接地址。`DB_NAME` 后面不能带 `}` 等多余字符。

还需要配置应用安全参数：

```env
APP_ENCRYPTION_KEY=足够长的随机字符串
SESSION_COOKIE_SECURE=false
FRONTEND_ORIGIN=http://localhost:5173
ALLOW_PRIVATE_MODEL_HOSTS=false
```

默认只允许用户连接公开 HTTPS 模型服务。只有可信内网确实需要本地模型时，才设置 `ALLOW_PRIVATE_MODEL_HOSTS=true`。

## 本地启动

后端：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn core.app:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。

## 宝塔部署

1. 在宝塔数据库面板创建数据库和专用用户，字符集选择 `utf8mb4`。
2. 点击数据库的“导入”，选择 `deploy/llm_guardrails.sql`。
3. 上传项目，创建 Python 3.11 项目并安装 `requirements.txt`。
4. 按宝塔数据库信息填写 `.env` 中的五个 `DB_` 配置。
5. 设置 `SESSION_COOKIE_SECURE=true`，并将 `FRONTEND_ORIGIN` 改为实际 HTTPS 域名。
6. 后端启动命令：

   ```bash
   python -m uvicorn core.app:app --host 127.0.0.1 --port 8000 --workers 1
   ```

7. 在 `frontend` 目录执行 `npm ci && npm run build`，站点根目录选择 `frontend/dist`。
8. 将 `deploy/bt-nginx.conf` 中的配置加入宝塔站点配置，并申请 HTTPS 证书。

应用使用服务端 Cookie 会话，前后端应通过同一域名访问。

## 主流程日志

后端只将对话处理流水写入 `logs/pipeline.log`。同一次请求通过 `request_id` 关联，固定记录：

1. `input`：用户输入。
2. `rule_match`：规则匹配及脱敏结果。
3. `vector_search`：向量检索输入、命中项和相似度。
4. `llm_analysis`：LLM 安全分析及最终判定。
5. `call_llm`：发送给回答模型的安全上下文、完整回答或错误；拦截时记录 `skipped`。

日志为每行一条 JSON，默认达到 10MB 后轮转并保留 10 份。可通过 `LOG_DIR`、`LOG_MAX_BYTES` 和 `LOG_BACKUP_COUNT` 调整。API Key 永远不会写入日志。

## JSONL 导入格式

保密库：

```json
{"fact_text":"内部项目底价为七折","fact_type":"pricing_strategy","paraphrases":["项目最低折扣是七折"]}
```

公开库：

```json
{"type":"phone","value":"13800000000","label":"公开客服电话"}
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```
