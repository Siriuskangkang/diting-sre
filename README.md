# 🔔 谛听 DiTing · SRE 排障自动驾驶仪

> **听辨故障，自动驾驶排障。**

谛听是一个面向 SRE / DevOps 的 **AI 排障自动驾驶仪**——它不等你提问，而是**接收告警、主动介入**：多个 Agent 自主调监控 / 日志 / k8s / 知识库取证，输出根因与修复方案，把排障结论沉淀回知识库（越用越强），还能规划修复动作、人工审批后自动执行。

**一句话**：线上告警 → 主动自排查 → 根因 + 修复 → 知识自进化 → 经审批自动执行。

---

## 完整能力闭环

```
线上告警 ──▶ 自排查 Agent (MTTR ~56s) ──▶ 排查报告
                ├─▶ 🧬 知识自进化：沉淀 runbook 回写知识库（数据飞轮）
                ├─▶ 🔧 修复动作规划：LLM 提取可执行修复 + 风险分级
                └─▶ ⏸ 人工审批 ──▶ ✅ 执行修复（从"建议"到"行动"）
```

---

## 一、什么是「线上告警触发」

生产环境的监控系统 7×24 采集服务指标，一旦某指标异常超阈值就触发**告警**，通过 webhook 推给谛听——谛听被动接收、主动开干，**无需人手动提问**：

```
监控系统 (Prometheus / Grafana / 夜莺 / Datadog)
   ↓  指标超阈值（5xx率>1% / P99>500ms / Pod重启 / 磁盘满 / 连接池满 …）
   ↓  webhook 推送告警（Alertmanager 标准格式）
谛听 /api/alerts 接收 ──▶ 自动启动排障 Agent
```

> 谛听对接的是 **Alertmanager 标准 webhook**，主流监控系统都能直接接入，零改代码。

---

## 二、应用场景（8 个典型故障）

| 场景 | 触发指标 → 告警 | 谛听自主排查动作 | 典型根因 |
|---|---|---|---|
| **1. 5xx 错误率飙升** | HTTP 5xx 率 0.1%→5% | 查监控确认 + 查日志抓堆栈 + 查 Pod 状态 + 搜知识库 | 连接池耗尽 / 下游超时 |
| **2. 接口延迟突增** | P99 80ms→800ms | APM 链路定位耗时段 + 查慢 SQL + 查 GC | 慢查询 / 锁竞争 / Full GC |
| **3. Pod 崩溃重启** | Pod CrashLoopBackOff | describe pod（OOM/探针/退出码）+ 查启动日志 | 探针过严 / 资源不足 / 配置错 |
| **4. 数据库连接池耗尽** | 连接池 active 满 / getConnection 超时 | 查日志等连接 + 查 DB 慢会话 + 审查代码 | 连接泄漏 / 长事务 |
| **5. 容器 OOM** | Pod OOMKilled (exit 137) | 查内存曲线 + 抓 heap dump + 查缓存配置 | 内存泄漏 / 大对象 / 缓存无上限 |
| **6. 磁盘 / inode 耗尽** | 磁盘使用率 >90% 或 inode 满 | df -h / df -i + 定位大文件 / 小文件堆积 | 日志未轮转 / 临时文件堆积 |
| **7. Redis 内存满** | evicted_keys 激增 + 命中率掉 | INFO memory + --bigkeys + 查 TTL | 大 key / 缓存无 TTL |
| **8. TLS 证书过期** | 证书即将 / 已过期 | openssl 查有效期 + 查 cert-manager | 续期任务失败 / 时钟漂移 |

### 端到端示例（场景 1：5xx 飙升）

```
凌晨 3 点，Prometheus 检测到 order-service 5xx 率 0.1% → 5.6%
  → Alertmanager 触发 High5xxRate 告警 (severity=critical)
  → webhook 推送谛听 /api/alerts
  → 谛听 Agent 自动开干：
      • query_metrics : 确认 5xx 飙升 + CPU 88%
      • query_logs    : 抓到 NullPointerException + getConnection timeout
      • get_pod_status: 发现 Pod CrashLoopBackOff + OOMKilled
      • kb_search     : 命中知识库「5xx 排查 runbook」
  → 输出：根因 = 连接泄漏 → 内存涨 → OOM → 5xx；修复 = 归还连接 + 扩容
  → 🧬 把这次排障沉淀成新 runbook 回写知识库
  → 🔧 规划修复动作（回滚 / 重启 / kill 慢查询）→ 人工审批 → 执行
  → 推送飞书 / 钉钉群，on-call 起来时结论已经在了
```

**价值**：SRE 不用半夜从零排查，醒来时谛听已查清并给出根因 + 修复，甚至修复都已执行。

---

## 三、三个核心差异化

1. **主动介入，不是被动问答** —— 告警触发就开干，不用人去问
2. **执行，不止建议** —— 能真调工具取证，还能经审批执行修复（human-in-the-loop）
3. **知识自进化闭环** —— 排障结论自动沉淀，用得越多越强（数据飞轮 = 护城河）

---

## 🏗 架构

```
  告警源                    谛听核心                               交付
┌──────────────┐      ┌───────────────────────────┐         ┌────────────┐
│ Prometheus   │─────▶│ 告警网关 (Alertmanager webhook)│      │ 飞书/Slack │
│ Alertmanager │      │ 编排引擎 (LangGraph 状态机)   │─播报──▶│ /钉钉 IM   │
│ 夜莺/PagerDuty│      │  Triage→Investigate→Report   │       └────────────┘
└──────────────┘      │ 工具层 (MCP / 配置驱动适配器) │       ┌────────────┐
                      │  监控/日志/k8s/工单/GitHub   │─查询──▶│ Web 控制台 │
┌──────────────┐      │ 知识库 (混合检索 RAG + 自进化)│       │ (看板/排障 │
│ 文档上传     │─────▶│  向量+BM25+RRF+rerank+溯源   │       │  /知识库)  │
│ PDF/Word/图片│      │ LLM 层 (阿里云百炼, 可换)     │       └────────────┘
└──────────────┘      └───────────────────────────┘
                              │  排障结论
                       🧬 沉淀回知识库（自进化）
                              │  修复动作
                       🔧 规划 → ⏸ 审批 → ✅ 执行
```

---

## 🚀 快速开始

```bash
# 1. 环境
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填阿里云百炼 key（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）

# 2. 入库知识库（首次必做）
python scripts/ingest.py --reset

# 3. 启动服务
python -m opscopilot.api      # → http://127.0.0.1:8000

# 4. 触发一次告警，体验完整闭环
python scripts/trigger_alert.py 5xx        # 或 oom / latency / dbpool
curl http://127.0.0.1:8000/api/incidents   # 看排障结果

# 5. 其他
python scripts/eval_rag.py                  # RAG 评估对比
pytest                                       # 单元测试
python mcp/run_github_server.py             # 自研 MCP Server
```

浏览器打开 **http://127.0.0.1:8000** → 「告警排障」Tab 点「🔔 模拟告警」即可看谛听自动排查 + 🧬 知识沉淀 + 🔧 修复动作审批。

> 接真实监控：`.env` 配 `PROMETHEUS_URL` / `LOKI_URL` / `K8S_IN_CLUSTER=true`，并把 Alertmanager webhook 指向 `http://<谛听>/api/alerts`，即真触发。配 `FEISHU_WEBHOOK` 等则结果自动推 IM。

---

## 🧱 技术栈

| 层 | 选型 |
|---|---|
| LLM | 阿里云百炼 `qwen-plus` / `text-embedding-v3` / `gte-rerank-v2` / `qwen-vl-ocr` |
| Agent 编排 | LangGraph（状态机 + 条件边 + 循环 + interrupt）|
| 工具协议 | MCP（自研 GitHub MCP Server + 适配器）|
| RAG | Chroma + BM25 + RRF + cross-encoder rerank + 引用溯源 |
| 文档解析 | 百炼 file-extract + qwen-vl-ocr（PDF/Word/图片 OCR）|
| 后端 / 前端 | Python FastAPI / 原生 HTML+CSS+JS（深色控制台）|

---

## 📁 项目结构

```
opscopilot/
├── src/opscopilot/
│   ├── rag/          # 混合检索 RAG：loader/chunker/embeddings/vectorstore/retriever/chain
│   │   └── file_parser.py  # 百炼多格式解析（PDF/Word/图片 OCR）
│   ├── tools/        # 工具调用：builtin_tools + GitHub MCP Server + adapters(Prom/Loki/k8s)
│   ├── agents/       # LangGraph 多 Agent 排障（Supervisor + Workers + ReAct）
│   ├── alerts/       # 告警网关：Alertmanager webhook → 去重 → 排障 → 存历史
│   ├── notify/       # IM 播报：飞书/钉钉/Slack（配置驱动，降级日志）
│   ├── evolution/    # 🧬 知识自进化：排障结论 LLM 提炼 runbook 回写知识库
│   ├── execution/    # 🔧 V2 修复执行：planner 规划动作 + executor 执行 + 人工审批
│   ├── web/          # 前端（Mission Control 深色控制台）
│   ├── api.py        # FastAPI（REST API + 静态托管）
│   ├── config.py / llm.py
├── data/runbooks/    # 运维排障知识库（8 篇）+ eval 数据集
├── docs/product/     # 📗 谛听产品方案（6 篇：总览/定位/市场/功能/架构/路线图）
├── scripts/          # ingest / trigger_alert / eval_rag / demo_*
├── mcp/              # MCP Server 入口
└── tests/
```

---

## 📈 能力演进（已完成）

| 阶段 | 能力 | 状态 |
|---|---|---|
| **MVP** | 告警 webhook → 多 Agent 自排查 → IM 播报 → 存历史 | ✅ |
| **V1** | 🧬 知识自进化闭环（排障结论回写知识库，数据飞轮）| ✅ |
| **V1** | 评估看板（MTTR / 成功率 / 知识自增长）| ✅ |
| **V2** | 🔧 修复动作规划 + 人工审批 + 执行（从建议到行动）| ✅（执行 mock）|
| V2+ | 真实 k8s/云 API 执行、多租户/SSO、根因知识图谱 | ⏳ |

---

## 📖 文档

**产品方案**（`docs/product/`）：
- [00 总览](docs/product/00-OVERVIEW.md) · [01 定位](docs/product/01-POSITIONING.md) · [02 市场](docs/product/02-MARKET.md)
- [03 功能](docs/product/03-FEATURES.md) · [04 架构](docs/product/04-ARCHITECTURE.md) · [05 路线图与商业](docs/product/05-ROADMAP.md)

**技术文档**（`docs/`）：[架构详解](docs/ARCHITECTURE.md) · [面试故事](docs/INTERVIEW_STORIES.md) · [学习手册](docs/LEARNING_ROADMAP.md)

---

## License

MIT — runbook 内容为虚构示例，仅供演示。
