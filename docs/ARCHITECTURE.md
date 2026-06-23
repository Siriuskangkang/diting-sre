# 架构详解

本文档讲清「为什么这么设计」，是面试时讲架构的弹药库。

## 设计原则

1. **洋葱式分层**：RAG / Tools / Agents 各自独立成包，能单独跑、单独讲。L1 能跑就别等 L4。
2. **配置集中**：所有可变值（key、模型、检索参数）在 `config.py`，代码零硬编码。
3. **职责单一 + 接口清晰**：每个模块能独立解释「做什么、怎么用、依赖什么」。
4. **可观测优先**：LangGraph 每个节点是显式 step，可逐节点回放调试。

---

## 组件职责

### RAG 层 `rag/`
| 文件 | 职责 | 关键决策 |
|---|---|---|
| `loader.py` | 加载文档，写入 source metadata | 来源必须在加载时就记，下游溯源依赖它 |
| `chunker.py` | 两种切分策略 | runbook 有标题结构 → markdown 切分 > 递归切分 |
| `embeddings.py` | 本地 / OpenAI 双后端 | 中文用 BGE，免 key 本地起步 |
| `vectorstore.py` | Chroma 封装 | 零运维起步，生产可换 Qdrant/Milvus |
| `retriever.py` | **混合检索 + RRF + rerank** | 本项目深度核心，三路可开关做消融 |
| `chain.py` | 问答链 + 引用溯源 | 答案带 `[来源n]`，可信可核查 |

### 工具层 `tools/`
| 文件 | 职责 |
|---|---|
| `builtin_tools.py` | 4 个运维 `@tool` + `kb_search`（Agentic RAG）|
| `github_client.py` | GitHub API 封装（有 token 真调，无 token mock）|
| `mcp_server.py` | **自研 MCP Server**：2 个 tool + 1 个 resource |
| `mcp_adapter.py` | 把 MCP 工具接进 LangGraph（`langchain-mcp-adapters`）|

### Agent 层 `agents/`
| 文件 | 职责 |
|---|---|
| `state.py` | `OpsState` TypedDict + `add_messages` reducer |
| `nodes.py` | Triage / Supervisor / Investigator(ReAct) / Reporter + 路由 |
| `graph.py` | StateGraph 组装与编译，`run()` 端到端入口 |

---

## 关键数据流

### 流 A：RAG 单轮问答
```
question
  → HybridRetriever.retrieve
      ├─ 向量召回 (top10)
      ├─ BM25 召回 (top10)
      └─ RRF 融合 → rerank(top4)
  → context 拼接（带来源编号）
  → LLM
  → answer + sources
```

### 流 B：Multi-Agent 排障
```
query
  → triage (LLM 输出故障类型/假设/待查项)
  → supervisor (iteration+1)
  → [route] evidence 不足？
       是 → investigate (ReAct 自主调 metrics/logs/pod/github/kb)
            → supervisor (循环)
       否 → report (LLM 综合证据生成结构化报告)
  → END
```

---

## 关键设计决策与权衡（面试高频）

### Q1: 为什么用 LangGraph 而不是裸 LangChain Chain？
裸 Chain 是**线性**的（A→B→C）。排障需要**循环**（证据不够就回去再查）和**条件分支**（够了就报告）。
LangGraph 用图建模：节点是 step，边是控制流，状态显式传递。好处是**可观测、可回放、可设硬约束**（如 `MAX_ITER` 防失控）。

### Q2: 为什么 Supervisor 模式而不是平铺多 Agent？
- 平铺（所有 Agent 互相说话）→ 通信爆炸、难调试、易死循环。
- Supervisor（一个调度 + 多个专职 Worker）→ 职责清晰、可控、可观测。工业界主流。
- 本项目 supervisor 很轻（只累加轮次 + 条件边路由），重逻辑在 `route()`，简单可靠。

### Q3: 为什么混合检索（向量 + BM25）？
两者短板互补：
- 向量检索：擅长语义（"延迟突增" 能匹配到 "P99 飙高"），但怕**生僻关键词 / 专有名词**（如 `CrashLoopBackOff`、`OOMKilled`）。
- BM25：精确关键词命中强，但不懂同义改写。
用 **RRF 融合**两路结果，比单路召回率高。这是"召回阶段多召回"。

### Q4: 为什么 rerank 能提升效果？为什么不直接用 reranker 检索？
- 双塔 embedding（query 和 doc **分别**编码再算相似度）：快、可预计算，但**没有 query-doc 交互**，精度有限。
- Cross-encoder（query 和 doc **拼一起**过一遍）：能建模交互，精度高，但**慢、不能预计算**。
- 所以两阶段：先用快的双塔**多召回**（top10），再用 cross-encoder **精排**取 top4。兼顾效果与成本。

### Q5: 为什么 MCP 而不是直接写 LangChain tool？
传统每个工具各自定义 schema，**N 个 Agent × M 个工具 = N×M 集成**。
MCP 把工具标准化成 Server 暴露的 tools/resources，**任何 MCP 客户端**（Claude Desktop / IDE / 别的 Agent 框架）都能即插即用。
本项目 `search_github_issues` 同时存在于 `builtin_tools`（直接函数）和 `mcp_server`（MCP 协议）——同一能力两种暴露，对照展示 MCP 的价值。

### Q6: 怎么防止 Multi-Agent 失控循环 / 成本爆炸？
- 硬上限：`MAX_ITER` 限制调查轮次。
- 软阈值：证据数 ≥ 3 即停止（够用就不浪费）。
- `recursion_limit=50` 兜底 LangGraph 步数。
- 每个工具调用都是确定的、可观测的日志。

---

## 可扩展点（重做/进阶方向）

- **流式输出**：UI 层接 LLM streaming，逐字返回。
- **持久化记忆**：把历史排障结论写回知识库，形成自学习闭环。
- **Human-in-the-loop**：LangGraph 的 interrupt，让 report 前人工确认。
- **真接基础设施**：把 mock 工具换成真 Prometheus / Loki / k8s client。
- **多 MCP 编排**：接更多 MCP Server（Notion / 数据库），示范更大工具生态。
