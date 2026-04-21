"""
Benchmark Runner — Async Pipeline with Cost Tracking
=====================================================
Chạy toàn bộ pipeline đánh giá song song bằng asyncio,
theo dõi token usage và chi phí cho mỗi lần Eval.

Author: Long (Data Analyst) & Thuận (Backend/Performance)
"""

import asyncio
import time
from typing import List, Dict, Any

# ── Pricing table (USD per 1K tokens) cho Agent ────────────────
AGENT_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


class BenchmarkRunner:
    """
    Async Benchmark Runner với:
    - asyncio.Semaphore để rate limiting
    - Cost tracking (token usage + $ cost) cho mỗi case
    - Timing chi tiết (total time, avg latency)
    """

    def __init__(self, agent, evaluator, judge, max_concurrent: int = 5):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.total_agent_cost = 0.0
        self.total_agent_input_tokens = 0
        self.total_agent_output_tokens = 0

    async def run_single_test(self, test_case: Dict) -> Dict[str, Any]:
        """
        Chạy 1 test case qua pipeline:
        1. Gọi Agent (RAG)
        2. Chạy Retrieval Eval (Hit Rate + MRR)
        3. Chạy Multi-Judge Consensus
        4. Track cost + latency
        """
        async with self.semaphore:
            start_time = time.perf_counter()

            # 1. Gọi Agent
            response = await self.agent.query(test_case["question"])
            agent_latency = time.perf_counter() - start_time

            # 2. Chạy Retrieval Eval (RAGAS metrics)
            ragas_scores = await self.evaluator.score(test_case, response)

            # 3. Chạy Multi-Judge
            ground_truth_answer = test_case.get(
                "ground_truth_answer", test_case.get("expected_answer", "")
            )
            judge_result = await self.judge.evaluate_multi_judge(
                test_case["question"],
                response["answer"],
                ground_truth_answer,
            )

            total_latency = time.perf_counter() - start_time

            # 4. Track Agent cost
            metadata = response.get("metadata", {})
            agent_tokens = metadata.get("tokens_used", 0)
            agent_model = metadata.get("model", "gpt-4o-mini")
            agent_cost = self._calc_agent_cost(agent_model, agent_tokens)
            self.total_agent_cost += agent_cost
            self.total_agent_input_tokens += agent_tokens
            self.total_agent_output_tokens += agent_tokens  # ước lượng

            return {
                "test_case": test_case["question"],
                "question_id": test_case.get("question_id", ""),
                "question_type": test_case.get("question_type", "unknown"),
                "complexity": test_case.get("complexity", "unknown"),
                "agent_response": response["answer"],
                "ground_truth": ground_truth_answer,
                "retrieved_ids": response.get("retrieved_ids", []),
                "expected_ids": test_case.get("ground_truth_chunk_ids", []),
                "latency": round(total_latency, 3),
                "agent_latency": round(agent_latency, 3),
                "ragas": ragas_scores,
                "judge": judge_result,
                "cost": {
                    "agent_usd": round(agent_cost, 6),
                    "judge_usd": judge_result.get("cost", {}).get("usd", 0),
                    "total_usd": round(
                        agent_cost + judge_result.get("cost", {}).get("usd", 0), 6
                    ),
                },
                "status": "fail" if judge_result["final_score"] < 3 else "pass",
            }

    async def run_all(
        self, dataset: List[Dict], batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Chạy song song bằng asyncio.gather với giới hạn Semaphore
        để không bị Rate Limit.

        Chia batch → mỗi batch chạy đồng thời 'batch_size' tasks.
        """
        results: List[Dict[str, Any]] = []
        total = len(dataset)
        start_all = time.perf_counter()

        for i in range(0, total, batch_size):
            batch = dataset[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            print(f"  📦 Batch {batch_num}/{total_batches} ({len(batch)} cases)...")

            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        elapsed = time.perf_counter() - start_all
        print(f"  ⏱️ Tổng thời gian: {elapsed:.1f}s | Trung bình: {elapsed/max(total,1):.2f}s/case")
        return results

    def _calc_agent_cost(self, model: str, tokens: int) -> float:
        pricing = AGENT_PRICING.get(model, AGENT_PRICING["gpt-4o-mini"])
        # Ước lượng: 60% input, 40% output
        input_t = int(tokens * 0.6)
        output_t = int(tokens * 0.4)
        return (input_t / 1000) * pricing["input"] + (output_t / 1000) * pricing["output"]

    def get_cost_summary(self) -> Dict[str, Any]:
        """Báo cáo tổng hợp chi phí Agent."""
        return {
            "agent_total_cost_usd": round(self.total_agent_cost, 4),
            "agent_total_input_tokens": self.total_agent_input_tokens,
            "agent_total_output_tokens": self.total_agent_output_tokens,
        }
