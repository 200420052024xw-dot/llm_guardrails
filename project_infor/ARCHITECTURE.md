# LLM Guardrails 网关架构设计文档

## 项目概述

这是一个文本输入电子围栏网关系统，用于在用户文本发送到 LLM 之前进行安全检测和策略控制。

**核心流程:**
```
用户请求 → 网关接收 → 检测敏感信息 → 策略决策 → 调用LLM(可选) → 返回结果 → 审计日志
```

---

## 项目目录结构

```
llm-guardrails/
├── app.py                          # FastAPI 主入口，定义路由和请求处理逻辑
├── requirements.txt                # Python 依赖清单
├── .env.example                    # 环境变量示例文件
├── .env                            # 实际环境变量(不提交到 git)
├── .gitignore                      # Git 忽略文件配置
├── README.md                       # 项目说明文档
├── ARCHITECTURE.md                 # 本架构设计文档
│
├── config/                         # 配置文件目录
│   ├── __init__.py
│   ├── models.yaml                 # LLM API 配置(地址、超时、模型名)
│   ├── settings.py                 # 配置加载器(读取 yaml 和环境变量)
│   └── logging_config.py           # 日志配置(格式、级别、输出)
│
├── core/                           # 核心业务逻辑
│   ├── __init__.py
│   ├── schemas.py                  # 数据模型定义(Request/Response/Detection/Decision)
│   ├── orchestrator.py             # 核心编排器(调度检测→策略→LLM)
│   └── exceptions.py               # 自定义异常类
│
├── llm/                            # LLM 客户端模块
│   ├── __init__.py
│   ├── client.py                   # LLM API 调用封装
│   ├── base.py                     # LLM 客户端抽象基类
│   └── openai_client.py            # OpenAI 兼容客户端实现
│
├── detectors/                      # 检测器模块(由2号同学负责)
│   ├── __init__.py
│   ├── runner.py                   # 检测器运行器(统一调度所有检测器)
│   ├── base.py                     # 检测器抽象基类
│   ├── regex_detector.py           # 正则检测器(手机号、邮箱等)
│   └── model_detector.py           # 模型检测器(灰区文本分类)
│
├── policy/                         # 策略引擎模块(由3号同学负责)
│   ├── __init__.py
│   ├── decision.py                 # 策略决策器(根据检测结果决定动作)
│   ├── risk_scorer.py              # 风险评分器
│   └── rules.yaml                  # 策略规则配置
│
├── logs/                           # 日志模块
│   ├── __init__.py
│   ├── audit_logger.py             # 审计日志记录器
│   └── audit/                      # 审计日志文件存储目录
│
├── eval/                           # 评估模块(由4号同学负责)
│   ├── __init__.py
│   ├── test_cases.jsonl            # 测试用例数据集
│   └── run_eval.py                 # 评估脚本(计算准确率、召回率等)
│
└── tests/                          # 测试目录
    ├── __init__.py
    ├── conftest.py                 # pytest 配置和公共 fixtures
    ├── test_gateway.py             # 网关接口测试
    ├── test_orchestrator.py        # 编排器单元测试
    ├── test_llm_client.py          # LLM 客户端测试
    └── test_integration.py         # 集成测试
```

---

## 核心模块职责说明

### 1. **app.py** - FastAPI 主入口
**职责:**
- 定义 HTTP 路由 (`/health`, `/chat`)
- 接收用户请求并校验参数
- 调用 `Orchestrator` 处理业务逻辑
- 统一异常处理和错误响应
- 启动 uvicorn 服务器

**关键代码结构:**
```python
from fastapi import FastAPI, HTTPException
from core.schemas import ChatRequest, ChatResponse
from core.orchestrator import Orchestrator

app = FastAPI(title="LLM Guardrails Gateway")
orchestrator = Orchestrator()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        result = await orchestrator.process(request)
        return result
    except Exception as e:
        # 统一异常处理
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 2. **core/orchestrator.py** - 核心编排器
**职责:**
- **这是整个系统的大脑**,负责调度各个模块
- 按顺序调用: 检测器 → 策略引擎 → LLM 客户端
- 根据策略决策(block/allow/redact)选择不同执行路径
- 记录审计日志

**核心流程:**
```python
async def process(self, request: ChatRequest) -> ChatResponse:
    request_id = generate_uuid()
    
    # Step 1: 运行检测器
    detections = await detector_runner.detect(request.text)
    
    # Step 2: 策略决策
    decision = policy_engine.decide(request.text, detections)
    
    # Step 3: 根据决策调用 LLM
    llm_response = None
    if decision.action == "allow":
        llm_response = await llm_client.chat(request.text)
    elif decision.action == "redact":
        llm_response = await llm_client.chat(decision.redacted_text)
    # action == "block" 时不调用 LLM
    
    # Step 4: 记录审计日志
    audit_logger.log(request_id, request, decision, llm_response)
    
    # Step 5: 返回结果
    return ChatResponse(
        request_id=request_id,
        action=decision.action,
        risk_score=decision.risk_score,
        message=decision.message,
        llm_response=llm_response
    )
```

---

### 3. **core/schemas.py** - 数据模型定义
**职责:**
- 定义所有模块间共享的数据结构
- 使用 Pydantic 提供类型校验和序列化

**核心数据模型:**
```python
from pydantic import BaseModel, Field
from typing import Optional, List

# 用户请求
class ChatRequest(BaseModel):
    user_id: str = "anonymous"
    text: str = Field(min_length=1)
    model: Optional[str] = None

# 检测结果
class Detection(BaseModel):
    type: str                    # 类型: "phone", "email", "api_key"
    text: str                    # 检测到的原文
    start: int                   # 起始位置
    end: int                     # 结束位置
    confidence: float            # 置信度 0-1
    source: str                  # 来源: "regex", "model"
    risk_weight: float           # 风险权重

# 策略决策
class Decision(BaseModel):
    action: str                  # "allow", "block", "redact"
    risk_score: float            # 总风险分数
    risk_level: str              # "low", "medium", "high"
    redacted_text: Optional[str] # 脱敏后的文本
    message: str                 # 给用户的提示信息

# 网关响应
class ChatResponse(BaseModel):
    request_id: str
    action: str
    risk_score: float
    message: str
    llm_response: Optional[str]
    guard_result: dict           # 包含检测和决策的详细信息
```

---

### 4. **llm/client.py** - LLM 客户端
**职责:**
- 封装对现有 LLM API 的调用
- 支持多种 LLM 提供商(OpenAI, Azure, 私有化部署)
- 处理超时、重试、错误

**设计模式: 策略模式**
```python
# llm/base.py
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(self, text: str, model: Optional[str] = None) -> str:
        pass

# llm/openai_client.py
import httpx
from llm.base import BaseLLMClient

class OpenAIClient(BaseLLMClient):
    def __init__(self, base_url, api_key, timeout):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
    
    async def chat(self, text: str, model: Optional[str] = None) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={"model": model, "messages": [{"role": "user", "content": text}]},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout
            )
            return response.json()["choices"][0]["message"]["content"]
```

---

### 5. **detectors/runner.py** - 检测器运行器
**职责:**
- 统一管理所有检测器
- 并行运行多个检测器提高效率
- 合并检测结果并去重

**设计模式: 组合模式**
```python
from detectors.base import BaseDetector
from detectors.regex_detector import RegexDetector
from detectors.model_detector import ModelDetector

class DetectorRunner:
    def __init__(self):
        self.detectors: List[BaseDetector] = [
            RegexDetector(),
            ModelDetector()
        ]
    
    async def detect(self, text: str) -> List[Detection]:
        # 并行运行所有检测器
        results = await asyncio.gather(
            *[detector.detect(text) for detector in self.detectors]
        )
        # 合并结果
        all_detections = [d for sublist in results for d in sublist]
        return self._deduplicate(all_detections)
```

---

### 6. **policy/decision.py** - 策略决策器
**职责:**
- 根据检测结果和风险分数决定动作
- 生成脱敏文本(将敏感信息替换为占位符)
- 配置化的策略规则

**决策逻辑:**
```python
def decide(text: str, detections: List[Detection]) -> Decision:
    # 计算总风险分数
    risk_score = sum(d.risk_weight * d.confidence for d in detections)
    
    # 根据风险阈值决定动作
    if risk_score >= 0.8:
        action = "block"
        message = "检测到高风险内容,已拦截"
    elif risk_score >= 0.3:
        action = "redact"
        redacted_text = redact(text, detections)
        message = "检测到敏感信息,已脱敏处理"
    else:
        action = "allow"
        message = "内容安全,已发送"
    
    return Decision(action=action, risk_score=risk_score, ...)
```

---

### 7. **logs/audit_logger.py** - 审计日志
**职责:**
- 记录每次请求的完整信息(请求内容、检测结果、决策、LLM响应)
- 支持日志轮转和持久化
- 便于后续分析和监管合规

**日志格式:**
```json
{
  "timestamp": "2026-06-10T14:30:00Z",
  "request_id": "uuid-123",
  "user_id": "user_456",
  "text": "原始文本",
  "detections": [...],
  "decision": {...},
  "llm_response": "LLM的回复",
  "latency_ms": 120
}
```

---

## 扩展性设计

### 1. **新增检测器**
在 `detectors/` 目录下创建新的检测器类:

```python
# detectors/custom_detector.py
from detectors.base import BaseDetector

class CustomDetector(BaseDetector):
    async def detect(self, text: str) -> List[Detection]:
        # 实现你的检测逻辑
        return [Detection(...)]

# 在 detectors/detect.py 中注册
class DetectorRunner:
    def __init__(self):
        self.detectors = [
            RegexDetector(),
            ModelDetector(),
            CustomDetector()  # 新增
        ]
```

### 2. **新增 LLM 提供商**
在 `llm/` 目录下实现新的客户端:

```python
# llm/azure_client.py
from llm.base import BaseLLMClient

class AzureClient(BaseLLMClient):
    async def chat(self, text: str, model: Optional[str] = None) -> str:
        # 实现 Azure OpenAI 调用逻辑
        pass

# 在 config/settings.py 中根据配置选择客户端
def get_llm_client() -> BaseLLMClient:
    provider = os.getenv("LLM_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIClient(...)
    elif provider == "azure":
        return AzureClient(...)
```

### 3. **自定义策略规则**
修改 `policy/rules.yaml`:

```yaml
risk_thresholds:
  block: 0.8    # 高风险直接拦截
  redact: 0.3   # 中风险脱敏

detection_weights:
  api_key: 1.0       # 绝对拦截
  password: 1.0
  phone: 0.6         # 中等风险
  email: 0.4
  person_name: 0.3   # 低风险

redaction_templates:
  phone: "[PHONE_{index}]"
  email: "[EMAIL_{index}]"
  person: "[PERSON_{index}]"
```

### 4. **添加中间件**
在 `app.py` 中添加 FastAPI 中间件:

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"]
)

# 响应压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 自定义中间件: 请求计时
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

### 5. **插件化架构(高级)**
创建插件目录 `plugins/`:

```python
# plugins/plugin_manager.py
from importlib import import_module

class PluginManager:
    def __init__(self, plugin_dir="plugins"):
        self.plugins = []
        self._load_plugins(plugin_dir)
    
    def _load_plugins(self, plugin_dir):
        for file in os.listdir(plugin_dir):
            if file.endswith("_plugin.py"):
                module = import_module(f"{plugin_dir}.{file[:-3]}")
                self.plugins.append(module.Plugin())
    
    async def run_plugins(self, text, detections):
        for plugin in self.plugins:
            await plugin.process(text, detections)
```

---

## 关键技术点

### 1. **异步编程**
使用 `async/await` 提高并发性能:
- 检测器并行运行: `asyncio.gather()`
- LLM 调用异步化: `httpx.AsyncClient()`

### 2. **配置管理**
- 环境变量: 密钥、API地址
- YAML文件: 策略规则、模型配置
- 分离关注点: 代码与配置解耦

### 3. **错误处理**
```python
try:
    result = await llm_client.chat(text)
except httpx.TimeoutException:
    # 超时降级: 返回默认响应
    result = "抱歉,服务暂时不可用"
except Exception as e:
    # 记录错误日志但不中断服务
    logger.error(f"LLM调用失败: {e}")
    result = None
```

### 4. **测试策略**
- 单元测试: 每个模块独立测试
- 集成测试: 端到端流程测试
- Mock外部依赖: 不依赖真实LLM API

```python
# tests/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_orchestrator_block_action(mocker):
    # Mock 检测器返回高风险结果
    mocker.patch("detectors.runner.detect", return_value=[
        Detection(type="api_key", risk_weight=1.0, confidence=1.0)
    ])
    
    orchestrator = Orchestrator()
    response = await orchestrator.process(ChatRequest(text="test"))
    
    assert response.action == "block"
    assert response.llm_response is None
```

---

## 部署建议

### 开发环境
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API key

# 启动服务
uvicorn app:app --reload --port 8000
```

### 生产环境
```bash
# 使用 gunicorn + uvicorn workers
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 或使用 Docker
docker build -t llm-guardrails .
docker run -p 8000:8000 --env-file .env llm-guardrails
```

### 监控指标
- 请求QPS和延迟
- 各动作(block/allow/redact)比例
- 检测器准确率(通过评估脚本)
- LLM调用成功率

---

## 后续优化方向

1. **性能优化**
   - Redis 缓存检测结果(相同文本不重复检测)
   - 检测器结果流式返回(不等所有检测器完成)

2. **功能增强**
   - 支持多轮对话上下文检测
   - 用户自定义敏感词库
   - 检测结果可视化面板

3. **安全加固**
   - API 鉴权(JWT Token)
   - 请求限流(防止滥用)
   - 审计日志加密存储

4. **AI能力**
   - 在线学习: 根据用户反馈调整策略
   - 对抗样本检测: 识别绕过尝试

---

## 常见问题

**Q: 如何测试而不调用真实LLM?**  
A: 在测试中 Mock `llm_client.chat()` 方法,或在配置中设置 `mock_mode=true`

**Q: 检测器太慢怎么办?**  
A: 1) 使用异步并行 2) 缓存结果 3) 只对灰区文本调用模型检测器

**Q: 如何处理误报?**  
A: 1) 收集误报案例到 eval/test_cases.jsonl 2) 调整策略阈值 3) 优化检测器规则

**Q: 如何支持多语言?**  
A: 1) 检测器添加语言参数 2) 不同语言使用不同正则规则 3) 模型检测器选择多语言模型

---

## 总结

这个架构设计的核心原则:
1. **模块化**: 每个模块职责单一,便于维护和测试
2. **可扩展**: 通过抽象基类和配置文件支持灵活扩展
3. **高性能**: 异步编程和并行处理提高吞吐量
4. **可观测**: 完善的日志和审计机制

按照这个框架实现,你的网关将具备良好的代码质量和可维护性,便于团队协作和后续迭代。
