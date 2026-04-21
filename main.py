"""
AI Evaluation Factory — Main Pipeline
=======================================
Orchestrator chính: chạy benchmark V1 → V2, Regression Analysis,
Release Gate, và xuất báo cáo.

Author: Long (Data Analyst) & Tuấn (Team Lead)
"""

import asyncio
import json
import os
import time

from engine.runner import BenchmarkRunner
from engine.retrieval_eval import RetrievalEvaluator
from engine.llm_judge import LLMJudge
from engine.release_gate import ReleaseGate
from agent.main_agent import MainAgent

from dotenv import load_dotenv

load_dotenv()


# ── Expert Evaluator (Retrieval + RAGAS) ──────────────────────
class ExpertEvaluator:
    """Đánh giá Retrieval quality + RAGAS metrics cho mỗi case."""

    def __init__(self):
        self.retrieval_evaluator = RetrievalEvaluator(top_k=3)

    async def score(self, case, resp):
        retrieval = self.retrieval_evaluator.evaluate_case(
            case.get("ground_truth_chunk_ids", []),
            resp.get("retrieved_ids", []),
        )

        # Faithfulness heuristic: kiểm tra context coverage
        contexts = resp.get("contexts", [])
        gt_answer = case.get("ground_truth_answer", "")
        gt_keywords = set(gt_answer.lower().split())

        if contexts and gt_keywords:
            all_context = " ".join(contexts).lower()
            context_words = set(all_context.split())
            overlap = len(gt_keywords & context_words) / max(len(gt_keywords), 1)
            faithfulness = min(1.0, overlap * 1.2)
        else:
            faithfulness = 0.5

        # Relevancy heuristic: kiểm tra answer chứa info từ context
        answer = resp.get("answer", "")
        answer_words = set(answer.lower().split())
        if contexts:
            ctx_words = set(" ".join(contexts).lower().split())
            relevancy = min(1.0, len(answer_words & ctx_words) / max(len(answer_words), 1))
        else:
            relevancy = 0.5

        return {
            "faithfulness": round(faithfulness, 3),
            "relevancy": round(relevancy, 3),
            "retrieval": {
                "hit_rate": retrieval["hit_rate"],
                "mrr": retrieval["mrr"],
                "excluded_from_avg": retrieval["excluded_from_avg"],
            },
        }


# ── Build Summary ─────────────────────────────────────────────
def build_summary(results: list, version: str, judge: LLMJudge, runner: BenchmarkRunner) -> dict:
    """Tổng hợp metrics từ kết quả benchmark."""
    total = len(results)
    if total == 0:
        return {"metadata": {"version": version, "total": 0}, "metrics": {}}

    # Retrieval metrics (exclude out-of-context cases)
    retrieval_cases = [r for r in results if not r["ragas"]["retrieval"].get("excluded_from_avg", False)]
    included = len(retrieval_cases)
    out_of_context = total - included

    avg_hit_rate = sum(r["ragas"]["retrieval"]["hit_rate"] for r in retrieval_cases) / max(included, 1)
    avg_mrr = sum(r["ragas"]["retrieval"]["mrr"] for r in retrieval_cases) / max(included, 1)

    # Judge metrics
    avg_score = sum(r["judge"]["final_score"] for r in results) / total
    avg_agreement = sum(r["judge"]["agreement_rate"] for r in results) / total

    # RAGAS metrics
    avg_faithfulness = sum(r["ragas"]["faithfulness"] for r in results) / total
    avg_relevancy = sum(r["ragas"]["relevancy"] for r in results) / total

    # Pass/Fail
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = total - passed

    # Cost
    total_cost = sum(r["cost"]["total_usd"] for r in results)
    avg_latency = sum(r["latency"] for r in results) / total

    # Judge cost report
    judge_report = judge.get_total_cost_report()

    return {
        "metadata": {
            "version": version,
            "total": total,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {
            "avg_score": round(avg_score, 3),
            "hit_rate": round(avg_hit_rate, 3),
            "mrr": round(avg_mrr, 3),
            "agreement_rate": round(avg_agreement, 3),
            "faithfulness": round(avg_faithfulness, 3),
            "relevancy": round(avg_relevancy, 3),
        },
        "pass_fail": {
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1),
        },
        "retrieval_details": {
            "included_cases": included,
            "out_of_context_cases": out_of_context,
        },
        "performance": {
            "avg_latency_sec": round(avg_latency, 3),
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_case_usd": round(total_cost / total, 6),
        },
        "judge_reliability": judge_report,
        "cost_reduction_proposal": (
            "De xuat giam 30% chi phi Eval: "
            "(1) Dung model nho (gpt-3.5-turbo) cho cau hoi complexity=simple, "
            "model lon (gpt-4o-mini) cho cau kho. "
            "(2) Cache ket qua Judge cho cau hoi trung lap. "
            "(3) Giam max_tokens Judge xuong 100 cho cau don gian."
        ),
    }


# ── Main Pipeline ─────────────────────────────────────────────
async def run_benchmark_with_results(agent_version: str):
    """Chạy benchmark đầy đủ cho 1 phiên bản Agent."""
    print(f"\n[*] Khoi dong Benchmark cho {agent_version}...")

    if not os.path.exists("data/golden_set.jsonl"):
        print("[!] Thieu data/golden_set.jsonl. Hay chay 'python data/synthetic_gen.py' truoc.")
        return None, None, None, None

    with open("data/golden_set.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("[!] File data/golden_set.jsonl rong.")
        return None, None, None, None

    print(f"[*] Da tai {len(dataset)} test cases.")

    # Init components
    agent = MainAgent()
    evaluator = ExpertEvaluator()
    judge = LLMJudge(model_a="gpt-4o-mini", model_b="gpt-3.5-turbo")
    runner = BenchmarkRunner(agent, evaluator, judge, max_concurrent=5)

    # Run
    results = await runner.run_all(dataset)
    summary = build_summary(results, agent_version, judge, runner)

    return results, summary, judge, runner


async def main():
    """Pipeline chính: V1 -> V2 -> Regression -> Release Gate."""
    print("=" * 60)
    print("AI EVALUATION FACTORY - EXPERT BENCHMARK")
    print("=" * 60)

    # ── V1 Benchmark ───────────────────────────────────────────
    v1_results, v1_summary, v1_judge, _ = await run_benchmark_with_results("Agent_V1_Base")

    if not v1_summary:
        print("[!] Khong the chay Benchmark V1. Kiem tra data/golden_set.jsonl.")
        return

    # ── V2 Benchmark ───────────────────────────────────────────
    v2_results, v2_summary, v2_judge, v2_runner = await run_benchmark_with_results(
        "Agent_V2_Optimized"
    )

    if not v2_summary:
        print("[!] Khong the chay Benchmark V2.")
        return

    # ── Regression Analysis & Release Gate (Quang) ──────────────
    gate = ReleaseGate()
    regression = gate.check(v1_summary, v2_summary)

    # Merge regression into V2 summary
    v2_summary["regression"] = regression

    # ── Print Results ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("KET QUA BENCHMARK")
    print("=" * 60)

    for label, summary in [("V1 (Base)", v1_summary), ("V2 (Optimized)", v2_summary)]:
        m = summary["metrics"]
        pf = summary["pass_fail"]
        print(f"\n  [{label}]")
        print(f"    Avg Score: {m['avg_score']:.2f}/5.0 | Pass Rate: {pf['pass_rate']:.1f}%")
        print(f"    Hit Rate: {m['hit_rate']*100:.1f}% | MRR: {m['mrr']:.3f}")
        print(f"    Agreement Rate: {m['agreement_rate']*100:.1f}%")
        print(f"    Faithfulness: {m['faithfulness']:.3f} | Relevancy: {m['relevancy']:.3f}")

    # Report chi tiet tu Release Gate của Quang
    gate.report(regression)

    # ── Cost Report ────────────────────────────────────────────
    print("-" * 60)
    print("COST REPORT")
    print("-" * 60)
    perf = v2_summary["performance"]
    jr = v2_summary["judge_reliability"]
    print(f"  Total Eval Cost: ${perf['total_cost_usd']:.4f}")
    print(f"  Avg Cost/Case:   ${perf['avg_cost_per_case_usd']:.6f}")
    print(f"  Avg Latency:     {perf['avg_latency_sec']:.2f}s/case")
    print(f"  Cohen's Kappa:   {jr['cohens_kappa']:.4f}")
    print(f"  {v2_summary.get('cost_reduction_proposal', '')}")

    # ── Save Reports ───────────────────────────────────────────
    os.makedirs("reports", exist_ok=True)

    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v2_summary, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Saved: reports/summary.json")

    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(v2_results, f, ensure_ascii=False, indent=2)
    print("[OK] Saved: reports/benchmark_results.json")

    # Clean up (Acquire and close)
    if v1_judge: await v1_judge.aclose()
    if v2_judge: await v2_judge.aclose()

    print("\nBENCHMARK HOAN TAT!")


if __name__ == "__main__":
    asyncio.run(main())
