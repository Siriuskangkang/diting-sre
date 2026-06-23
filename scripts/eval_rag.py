"""RAG 管道评估 (L2 核心)：用 RAGAS 对比三种检索配置。

配置：
  - baseline_vector     仅向量检索
  - hybrid_bm25         向量 + BM25 混合
  - hybrid_bm25_rerank  混合 + 重排序（完整版）

产出：data/eval/results/{report_<config>.json} + summary.json + 控制台对比表。
这就是面试里"我把 RAG 准确率从 X 提到 Y"的数据来源。

运行: python scripts/eval_rag.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# 允许脚本独立运行（无需 pip install -e .）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from datasets import Dataset  # noqa: E402

from opscopilot.config import EVAL_DATASET_PATH, EVAL_RESULTS_DIR  # noqa: E402
from opscopilot.rag.chain import build_rag_chain  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eval")

# 三组对照（消融实验）
CONFIGS: list[tuple[str, dict[str, bool]]] = [
    ("baseline_vector", {"use_bm25": False, "use_rerank": False}),
    ("hybrid_bm25", {"use_bm25": True, "use_rerank": False}),
    ("hybrid_bm25_rerank", {"use_bm25": True, "use_rerank": True}),
]


def load_samples() -> list[dict[str, Any]]:
    data = json.loads(EVAL_DATASET_PATH.read_text(encoding="utf-8"))
    return data["samples"]


def run_pipeline(samples: list[dict[str, Any]], **build_kwargs: Any) -> list[dict[str, Any]]:
    chain = build_rag_chain(**build_kwargs)
    rows: list[dict[str, Any]] = []
    for i, s in enumerate(samples, 1):
        logger.info("[%d/%d] %s", i, len(samples), s["question"][:40])
        res = chain.ask(s["question"])
        rows.append(
            {
                "question": s["question"],
                "ground_truth": s["ground_truth"],
                "answer": res["answer"],
                "contexts": res["contexts"],
            }
        )
    return rows


def evaluate_with_ragas(rows: list[dict[str, Any]]) -> dict[str, float]:
    """跑 RAGAS 四项指标，返回 {metric: avg_score}。"""
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    ds = Dataset.from_list(rows)
    kwargs: dict[str, Any] = {}
    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper

        from opscopilot.llm import get_llm
        from opscopilot.rag.embeddings import get_embeddings

        kwargs["llm"] = LangchainLLMWrapper(get_llm(temperature=0.0))
        kwargs["embeddings"] = LangchainEmbeddingsWrapper(get_embeddings())
    except ImportError:
        logger.warning("RAGAS wrapper 不可用，回退默认 evaluator（需 OPENAI_API_KEY）")

    result = evaluate(
        dataset=ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        **kwargs,
    )
    return {k: float(v) for k, v in dict(result).items()}


def main() -> None:
    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    samples = load_samples()
    print(f"评估集: {len(samples)} 条\n")

    summary: dict[str, dict[str, float]] = {}
    for name, kwargs in CONFIGS:
        print(f"=== 跑配置: {name}  {kwargs} ===")
        rows = run_pipeline(samples, **kwargs)
        scores = evaluate_with_ragas(rows)
        summary[name] = scores
        (EVAL_RESULTS_DIR / f"report_{name}.json").write_text(
            json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  -> {scores}\n")

    # 对比表
    print("\n==================== RAG 配置对比 ====================")
    headers = list(next(iter(summary.values())).keys())
    print(f"{'配置':<24}" + "".join(f"{h:>20}" for h in headers))
    for name, scores in summary.items():
        print(f"{name:<24}" + "".join(f"{scores.get(h, 0):>20.4f}" for h in headers))
    print("=" * 52)

    (EVAL_RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n结果已写入: {EVAL_RESULTS_DIR}")


if __name__ == "__main__":
    main()
