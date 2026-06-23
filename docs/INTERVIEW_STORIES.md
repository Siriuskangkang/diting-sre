# 面试故事（对标 JD 关键词）

> 每个故事练成 **30 秒口述**。结构：背景 → 我做了什么 → 关键技术决策 → 数据/结果 → 踩坑或重做。
> 文件定位帮你随时回查代码细节。

---

## 📌 RAG / 知识库

**问**：你做过 RAG 吗？整体怎么搭的？

**答**：做过。我用 LangChain 搭了一个运维排障 RAG：把 8 篇故障 runbook 切分、向量化存进 Chroma，检索后用 LLM 生成带引用溯源的答案。核心 pipeline 在 `rag/` 包：loader 加载并记录来源 metadata，chunker 切分，retriever 检索，chain 拼接 context 调 LLM。我没停在"能问答"，重点做了检索深度优化和量化评估。

**追问 - 引用溯源怎么做**：加载文档时就把文件名写进 metadata，检索到的 chunk 编号成 `[来源n]` 拼进 prompt，要求 LLM 在结论后标注。这样答案可信、可核查幻觉。

---

## 📌 混合检索（向量 + BM25）

**问**：检索准确率怎么保证？只用向量够吗？

**答**：不够。向量擅长语义匹配，但运维场景有很多专有名词和错误码（`CrashLoopBackOff`、`OOMKilled`、`503`），纯向量容易漏。所以我加了 BM25 关键词检索，两路各召回 top10，用 **RRF（Reciprocal Rank Fusion）** 融合，公式 `Σ 1/(k+rank)`，k 取 60。两路互补，召回率明显提高。代码在 `rag/retriever.py` 的 `reciprocal_rank_fusion`。

---

## 📌 Rerank（重排序）

**问**：rerank 是什么？为什么有用？

**答**：rerank 是检索的**第二阶段精排**。第一段用双塔 embedding 快速多召回（它把 query 和 doc 分别编码，快但没交互，精度有限）；第二段用 cross-encoder 把 `(query, doc)` 拼一起过一遍，能建模两者交互，精度高但慢。所以只对召回的 10 条做精排取 4 条喂给 LLM。我用的是 `cross-encoder/ms-marco-MiniLM-L-6-v2`，CPU 可跑。

**关键判断**：rerank 不是替代检索，是补充。两阶段 = 召回率 + 精确率 + 成本可控。

---

## 📌 RAG 评估（RAGAS）

**问**：怎么证明你的 RAG 优化有效？

**答**：我用 RAGAS 做量化评估，四项指标：faithfulness（忠实度，防幻觉）、answer_relevancy（答案相关性）、context_precision（检索精度）、context_recall（召回完整度）。我设计了 16 条评估集，做了**三组消融对比**：纯向量 → +BM25 → +BM25+rerank，跑下来 context_recall 和 faithfulness 都是递增的。数字具体是 X→Y（跑 `scripts/eval_rag.py` 能复现）。

**加分点**：评估集的问题是口语化真实问法，不是复述 runbook 标题——否则测不出真实检索质量。

---

## 📌 Function Calling / Tool Calling

**问**：Function Calling 原理是什么？你在项目里怎么用的？

**答**：原理是 LLM 输出**结构化的工具调用 JSON**（函数名 + 参数），由宿主代码执行后把结果回填给 LLM，LLM 再决定下一步——这就是 ReAct 循环。我在 `tools/builtin_tools.py` 用 `@tool` 装饰器定义了查询监控、日志、Pod 状态、GitHub issue 等工具，LangChain 自动把 docstring + 类型注解转成 function schema 暴露给 LLM。LLM 看 description 自己决定调哪个、传什么参数。

**全链路要处理**：schema 定义 → LLM 决策 → 参数校验 → 执行 → 错误处理 → 重试 → 结果回填。我每个工具都返回确定性结果，保证 demo 不翻车。

---

## 📌 MCP（Model Context Protocol）

**问**：你了解 MCP 吗？为什么要有它？

**答**：了解，我自己写了一个。MCP 是 Anthropic 提的工具层标准协议。传统每个 Agent 框架各自定义工具 schema，**N 个 Agent × M 个工具 = N×M 集成**，写一遍换一家就废。MCP 把工具标准化成 Server 暴露的 `tools`（可调用）/ `resources`（只读数据）/ `prompts`（提示模板），任何 MCP 客户端（Claude Desktop / IDE / 别的 Agent）都能即插即用——它是工具层的 "USB-C 接口"。

**项目落点**：我在 `tools/mcp_server.py` 用官方 FastMCP 封装了一个 GitHub Issues MCP Server，暴露 2 个 tool（search/get）和 1 个 resource（仓库 issue 概览）。`mcp dev` 能用 Inspector 可视化调试，`mcp install` 能装进 Claude Desktop。同一个 GitHub 能力我也写了普通函数版（`builtin_tools`），**对照展示 MCP 的标准化价值**。

---

## 📌 A2A（Agent-to-Agent）

**问**：A2A 是什么？和 MCP 什么关系？

**答**：MCP 是 **Agent ↔ 工具** 的协议；A2A 是 **Agent ↔ Agent** 的协议（Google 提出），解决多个独立 Agent 之间怎么发现、通信、协作。两者互补不冲突。我在项目里用的是 **Supervisor 模式**实现 Agent 间协作：一个调度 Agent 决定派活给哪个专职 Worker（triage/investigate/report），状态在节点间显式传递。这算是单进程内的 A2A 雏形；跨进程的标准化 A2A 需要额外协议层。AutoGen 的 GroupChat 是另一种多 Agent 通信范式（对话式）。

---

## 📌 Multi-Agent & LangGraph

**问**：为什么用多 Agent？什么时候该用多 Agent 而不是单 Agent？

**答**：这是关键 trade-off。**默认用单 Agent + 多工具**就够了，简单可控。**只有当**任务能拆成差异很大的子角色、且每个子角色需要不同 prompt/工具/上下文时，才上多 Agent。我的排障场景符合：分诊（判断类型）、调查（调工具取证）、报告（结构化总结）三步职责分明，用 Supervisor + Worker 拆开更清晰。

**为什么 LangGraph**：排障需要**循环**（证据不够回去再查）和**条件分支**，裸 Chain 是线性的做不到。LangGraph 用图建模，节点是 step、边是控制流、状态显式传递，**可观测可回放**。我加了 `MAX_ITER` 上限和证据阈值防止失控循环和成本爆炸。

---

## 📌 何时用微调（vs RAG vs Prompt）

**问**：什么场景该用微调？

**答**：我的判断框架：
- **加新知识** → RAG（便宜、可更新、可溯源，90% 场景够用）
- **改输出格式/风格** → Prompt Engineering 先试，不行再 SFT
- **模型基础能力不足** → 先换更大模型，仍不行才微调
- 微调成本高（数据 + GPU + 评估 + 部署 + 持续维护），ROI 要算清。

我在项目里 RAG + Prompt 就解决了知识注入，没碰微调——这正是工程判断。但 LoRA/QLoRA 的原理和 SFT 流程我懂，需要时能上手。

---

## 📌 踩坑 / 重做（展示成熟度）

**问**：项目里踩过什么坑？

**答（挑 2-3 个讲）**：
1. **chunking 影响巨大**：一开始用固定大小切，结果一个 chunk 混了"现象"和"修复方案"，检索噪声大。改成按 markdown 标题切（`现象/根因/排查步骤/修复方案` 各自成块），准确率明显上去。
2. **Multi-Agent 容易失控**：早期没设 iteration 上限，Agent 反复调同样工具打转。加了 `MAX_ITER` + 证据阈值后收敛。
3. **评估集不能复述标题**：第一版评估问题直接抄 runbook 标题，检索"作弊"通过，测不出真实质量。改成口语化真实问法（"线上服务 5xx 飙到 5% 怎么排查"）才反映真实水平。

**重做会怎么改**：上 LangSmith 做全链路 trace；report 前加 human-in-the-loop；把 mock 工具换成真基础设施做端到端验证。
