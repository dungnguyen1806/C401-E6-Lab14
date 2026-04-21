"""
Benchmark Runner - Async Pipeline with Cost Tracking
====================================================
Chay toan bo pipeline danh gia song song bang asyncio,
theo doi token usage va chi phi cho moi lan Eval.

Author: Long (Data Analyst) & Thuan (Backend/Performance)
"""

import asyncio
import time
from typing import Any, Dict, List


AGENT_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge, batch_size: int = 5, max_concurrent: int | None = None):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.batch_size = max_concurrent or batch_size
        self.total_agent_cost = 0.0
        self.total_agent_input_tokens = 0
        self.total_agent_output_tokens = 0

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.perf_counter()

        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time

        ragas_scores = await self.evaluator.score(test_case, response)

        ground_truth_answer = test_case.get("ground_truth_answer", test_case.get("expected_answer", ""))
        judge_result = await self.judge.evaluate_multi_judge(
            test_case["question"],
            response["answer"],
            ground_truth_answer,
        )

        metadata = response.get("metadata", {})
        model = metadata.get("model", "gpt-4o-mini")
        total_tokens = int(metadata.get("tokens_used", 0) or 0)
        input_tokens = int(total_tokens * 0.6)
        output_tokens = total_tokens - input_tokens
        agent_cost = self._calc_agent_cost(model, input_tokens, output_tokens)

        self.total_agent_input_tokens += input_tokens
        self.total_agent_output_tokens += output_tokens
        self.total_agent_cost += agent_cost

        judge_cost = float(judge_result.get("cost", {}).get("usd", 0.0) or 0.0)

        return {
            "test_case": test_case["question"],
            "agent_response": response["answer"],
            "retrieved_ids": response.get("retrieved_ids", []),
            "latency": latency,
            "ragas": ragas_scores,
            "judge": judge_result,
            "status": "fail" if judge_result["final_score"] < 3 else "pass",
            "cost": {
                "agent_model": model,
                "agent_input_tokens": input_tokens,
                "agent_output_tokens": output_tokens,
                "agent_usd": round(agent_cost, 6),
                "judge_usd": round(judge_cost, 6),
                "total_usd": round(agent_cost + judge_cost, 6),
            },
        }

    async def run_all(self, dataset: List[Dict[str, Any]], batch_size: int | None = None) -> List[Dict[str, Any]]:
        effective_batch_size = batch_size or self.batch_size
        results: List[Dict[str, Any]] = []
        start_all = time.perf_counter()
        total = len(dataset)

        for i in range(0, total, effective_batch_size):
            batch = dataset[i:i + effective_batch_size]
            batch_results = await asyncio.gather(*(self.run_single_test(case) for case in batch))
            results.extend(batch_results)

        elapsed = time.perf_counter() - start_all
        print(f"  Tong thoi gian: {elapsed:.1f}s | Trung binh: {elapsed / max(total, 1):.2f}s/case")
        return results

    def _calc_agent_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = AGENT_PRICING.get(model, AGENT_PRICING["gpt-4o-mini"])
        return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

    def get_cost_summary(self) -> Dict[str, Any]:
        return {
            "agent_total_cost_usd": round(self.total_agent_cost, 4),
            "agent_total_input_tokens": self.total_agent_input_tokens,
            "agent_total_output_tokens": self.total_agent_output_tokens,
        }
