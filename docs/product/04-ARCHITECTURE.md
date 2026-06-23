# 技术架构

## 一、系统全景

```
  告警源                    谛听核心                               交付
┌──────────────┐      ┌───────────────────────────┐         ┌────────────┐
│ Prometheus   │─────▶│ ① 告警网关 (webhook 接入)   │         │ 飞书/Slack │
│ Alertmanager │      │ ② 编排引擎 (LangGraph 状态机)│─播报───▶│ /钉钉 IM   │
│ 夜莺/PagerDuty│      │   Triage→Investigate→Report │         └────────────┘
└──────────────┘      │ ③ 工具层 (MCP 协议)         │         ┌────────────┐
                      │   监控/日志/k8s/工单/GitHub │─查询───▶│ Web 控制台  │
┌──────────────┐      │ ④ 知识库 (RAG + 自进化)     │         │ (排障可视化│
│ 文档上传     │─────▶│   向量+BM25+rerank+引用溯源  │         │  知识库管理)│
│ PDF/Word/图片│      │ ⑤ LLM 层 (百炼, 可换)        │         └────────────┘
└──────────────┘      └───────────────────────────┘
                              │
                       排障结论 ──沉淀──▶ 知识库（自进化闭环）
```

## 二、技术栈（分层）

| 层 | 选型 | 选型理由 |
|---|---|---|
| LLM | 阿里云百炼：`qwen-plus` / `text-embedding-v3` / `gte-rerank-v2` / `qwen-vl-ocr` | 国产合规、中文强、OpenAI 兼容、对话/embedding/rerank/OCR 全覆盖 |
| Agent 编排 | **LangGraph**（状态机 + 条件边 + 循环 + interrupt）| 可观测、可控、支持 human-in-the-loop |
| 工具协议 | **MCP** | 工具标准化、即插即用、生态可扩展 |
| RAG | Chroma 向量库 + rank_bm25 + RRF 融合 + cross-encoder rerank | 混合检索精度高、引用溯源防幻觉 |
| 文档解析 | 百炼 `file-extract` + `qwen-vl-ocr` | 多格式（PDF/Word/图片）免本地解析库 |
| 后端 | Python + FastAPI | 异步、轻量、AI 生态最好 |
| 前端 | 原生 HTML/CSS/JS（OD 设计稿）| 轻量可控；后续可迁 React/Vue |
| IM | 飞书 / Slack / 钉钉 webhook | 用户在哪协作，告警就播到哪 |

## 三、Agent 编排（基于已验证原型）

谛听核心排障 = LangGraph 状态机（已在 OpsCopilot 端到端跑通）：

```
告警 → [Triage 分诊] → [Supervisor 调度] ──条件边──→ [Investigate 取证] ──→ 循环
                              │  证据够 / 到上限
                              ▼
                       [Report 报告] → IM 播报 + 沉淀知识库
```

- **Triage**：LLM 分析告警 → 故障类型 + 根因假设 + 待查项
- **Supervisor**：调度，条件边判断"证据够不够"（`route()`）
- **Investigate**（ReAct）：自主调工具 —— `query_metrics` / `query_logs` / `get_pod_status` / `search_github_issues` / `kb_search`（Agentic RAG）
- **Report**：综合证据生成「根因 + 修复 + 预防」，强制标注证据来源
- **失控防护**：`MAX_ITER` 上限 + 证据阈值 + `recursion_limit`（防循环爆炸、控成本）

> 进阶：Report 后接 LangGraph `interrupt`，进入「人工审批 → 自动执行修复」节点 = V2 的 Runbook 自动化。

## 四、数据流：一次排障的完整链路

```
1. Prometheus 告警 → webhook 推送 {服务, 指标, 严重度, 时间}
2. 谛听告警网关 → 去重 / 分级 → 启动排障 Agent
3. Agent 自主：查指标(确认异常) → 查日志(抓堆栈) → 查Pod(状态) → 查知识库(历史同类) → 查GitHub(已知issue)
4. Report 生成 → 推 IM 群（实时播报每步 + 最终结论 + 证据链）
5. 排障结论 → 自动总结成 runbook → 沉淀回知识库 ← 自进化
```

## 五、知识自进化闭环（核心壁垒）

```
排障 Report ──▶ (LLM 结构化总结) ──▶ 新 runbook ──▶ 入库(切分+向量化)
                                                     │
下次同类故障 ◀──检索复用─────────────────────────────┘
```

- 每次排障的「症状 → 根因 → 修复」自动结构化总结
- V1 经人工确认入库；V2 加可信度评分，高可信自动入库
- 知识库随使用持续增长 → 数据飞轮 → 客户迁移成本 = 长期壁垒

## 六、扩展性设计

- **工具可插拔**：MCP 协议，新数据源（Grafana / 工单 / 云 API）写个 MCP server 即接入，核心零改动
- **LLM 可换**：LLM 层抽象，百炼 ↔ OpenAI / DeepSeek / 本地模型可切换（全 OpenAI 兼容接口）
- **多云中立**：不绑定单一云，工具层适配多云，避免厂商锁定
- **水平扩展**：无状态编排服务可水平扩；向量库可从 Chroma 平滑换 Qdrant / Milvus

## 七、安全与合规（企业级）

- **私有化部署**：支持企业内网部署，数据不出域
- **脱敏**：日志 / 指标中的敏感信息（密钥 / PII）入 LLM 前自动脱敏
- **审计**：所有 Agent 决策 + 工具调用全链路日志，可逐节点回放
- **审批**：执行类操作（V2）走 human-in-the-loop，人不批不动手
- **权限**：RBAC，知识库按团队隔离

---

> 下一步看 [05 路线图与商业](./05-ROADMAP.md) 看什么时候做、怎么赚钱、风险在哪。
