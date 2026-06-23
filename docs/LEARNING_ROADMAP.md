# 学习手册（L1–L5 执行清单）

> 配合本仓库代码，照着勾选推进。每层是一个可独立 demo 的里程碑，时间不够就停在能讲的那层。

- [ ] **环境就绪**：`pip install -r requirements.txt` + `cp .env.example .env` + 填 LLM key

---

## L1 · 基础 RAG 跑通（Day 1-2）

**目标**：搭一个能对 runbook 知识库问答的最小 RAG，建立 LangChain 心智模型。

- [ ] 读 `rag/loader.py` `rag/chunker.py` `rag/embeddings.py` `rag/vectorstore.py`
- [ ] 跑 `python scripts/ingest.py --reset` 入库
- [ ] 跑 `python scripts/demo_rag.py` 提问，确认有答案

**面试能讲**：RAG 数据流 · 为什么 chunk · embedding 干嘛用 · 向量检索 vs 全文检索

---

## L2 · RAG 深度优化 + 评估（Day 3-5）⭐ 深度点

**目标**：把准确率做上去，**用数据证明**。这是最值钱的"有数据的故事"。

- [ ] 读 `rag/retriever.py`：理解 RRF 融合、cross-encoder 精排、两阶段检索
- [ ] 跑 `python scripts/eval_rag.py`，拿到三组配置对比表
- [ ] 自己加一组实验（如换 chunking 策略 / 换 embedding 模型），记录数字

**必懂概念**：混合检索（向量+BM25 互补短板）· rerank 为何有效（召回 vs 精排两阶段）·
RRF 公式 `Σ 1/(k+rank)` · RAGAS 四指标（faithfulness / answer_relevancy / context_precision / context_recall）

**面试故事**：「我把 RAG 的 context_recall 从 X 提到 Y，靠的是加 BM25 + rerank」（拿评估数字说话）

---

## L3 · Tool Calling + 自研 MCP Server（Day 6-8）⭐ 职位一杀手锏

**目标**：让 Agent 能调工具；**自己封装一个 MCP Server**。

- [ ] 读 `tools/builtin_tools.py`：每个 `@tool` 怎么变成 function schema
- [ ] 读 `tools/github_client.py` + `tools/mcp_server.py`
- [ ] 跑 `mcp dev mcp/run_github_server.py` 用 Inspector 调试你的 MCP Server
- [ ] （进阶）装 `langchain-mcp-adapters`，用 `tools/mcp_adapter.py` 把 MCP 工具接进 Agent

**必懂概念**：Function Calling 全链路（schema→LLM 决策→执行→错误处理→重试）·
MCP 解决 N×M 集成爆炸（工具层 USB-C）· MCP tools vs resources vs prompts · A2A 概念

**面试故事**：「我自研了一个 GitHub MCP Server，Claude Desktop 和我的 Agent 都能即插即用」

---

## L4 · Multi-Agent 编排（Day 9-11）⭐

**目标**：用 LangGraph 把 RAG + 工具串成完整排障系统。

- [ ] 读 `agents/state.py` `agents/nodes.py` `agents/graph.py`
- [ ] 画出本项目的状态机图（triage → supervisor ⇄ investigate → report）
- [ ] 跑 `python scripts/demo_agent.py "..."`，观察多 Agent 协作
- [ ] 实验：调 `MAX_ITER`、关掉某个工具，看 Agent 行为变化

**必懂概念**：何时用 Multi-Agent vs 单 Agent+多工具（关键 trade-off）·
Supervisor 模式 · 用图建模 Agent 的好处（可观测/可回放/可控）· 失控循环防护

**面试故事**：「我用 LangGraph 状态机做排障 Agent，加了 iteration 上限和证据阈值防止失控循环」

---

## L5 · 打磨 + 面试故事（Day 12-14）

- [ ] 录一个端到端 demo 视频 / 截图
- [ ] 补全 `README.md` 的架构图和数据
- [ ] 精读 [INTERVIEW_STORIES.md](./INTERVIEW_STORIES.md)，把每个故事练成 1 分钟口述
- [ ] （可选）Docker 化部署，给一个可访问的 demo URL
- [ ] 半天补微调"能讲"：看 LoRA/QLoRA 原理 + 跑通一个 notebook

**微调的判断框架**（面试常问"何时用微调"）：
- 加新知识 → RAG（便宜、可更新、可溯源）
- 改输出格式/风格/特定领域能力 → Prompt Engineering 先试，不行再 SFT
- 模型基础能力不足 → 换更大模型，仍不行才微调
- 微调成本高（数据+GPU+评估+部署），90% 场景 RAG+Prompt 就够

---

## 📚 开源项目对照阅读

| 项目 | 读什么 | 对应层 |
|---|---|---|
| **LangChain-Chatchat** | RAG pipeline 源码（chunking→embedding→检索→rerank→生成） | L1/L2 |
| **Dify** | workflow 编排界面，看 RAG 配置项如何暴露 | L2/L4 |
| **AutoGen Studio** | 多 Agent 角色定义 / 对话流可视化 | L4 |
| **MCP Servers 官方仓 / awesome-mcp-servers** | 挑 1-2 个（如 GitHub MCP）当模板读 | L3 |
| **LangGraph 官方 multi-agent / supervisor 例子** | 直接参考编排结构 | L4 |
