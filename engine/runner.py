"""
Benchmark Runner — Async Pipeline with Cost Tracking
=====================================================
Chạy toàn bộ pipeline đánh giá song song bằng asyncio,
theo dõi token usage và chi phí cho mỗi lần Eval.

"""

import asyncio
import time
from typing import List, Dict, Any, Optional
AGENT_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge, max_concurrent: int = 5):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.max_concurrent = max_concurrent
        self.total_agent_cost = 0.0
        self.total_agent_input_tokens = 0
        self.total_agent_output_tokens = 0

    async def run_single_test(self, test_case: Dict) -> Dict:
        start_time = time.perf_counter()
        
        # 1. Gọi Agent
        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time
        
        # Track Agent Cost
        metadata = response.get("metadata", {})
        tokens = metadata.get("tokens_used", 0)
        cost = self._calc_agent_cost(metadata.get("model", "gpt-4o-mini"), tokens)
        self.total_agent_cost += cost
        self.total_agent_input_tokens += int(tokens * 0.6)
        self.total_agent_output_tokens += int(tokens * 0.4)
        
        # 2. Chạy RAGAS metrics
        ragas_scores = await self.evaluator.score(test_case, response)
        
        # 3. Chạy Multi-Judge
        ground_truth_answer = test_case.get("ground_truth_answer", test_case.get("expected_answer", ""))
        judge_result = await self.judge.evaluate_multi_judge(
            test_case["question"], 
            response["answer"], 
            ground_truth_answer
        )
        
        return {
            "test_case": test_case["question"],
            "agent_response": response["answer"],
            "retrieved_ids": response.get("retrieved_ids", []),
            "latency": latency,
            "ragas": ragas_scores,
            "judge": judge_result,
            "cost": {
                "total_usd": cost + judge_result["cost"]["total_usd"]
            },
            "status": "fail" if judge_result["final_score"] < 3 else "pass"
        }

    async def run_all(self, dataset: List[Dict]) -> List[Dict]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size để không bị Rate Limit.
        """
        results = []
        start_all = time.perf_counter()
        total = len(dataset)
        batch_size = self.max_concurrent

        for i in range(0, total, batch_size):
            batch = dataset[i:i + batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            # Nếu đang dùng Gemini Free tier (5 RPM), cần sleep sau mỗi batch
            if i + batch_size < total:
                await asyncio.sleep(20) # Chờ 20s để không bị 429 quá nhiều

        elapsed = time.perf_counter() - start_all
        print(f"  Tong thoi gian: {elapsed:.1f}s | Trung binh: {elapsed/max(total,1):.2f}s/case")
        return results

    def _calc_agent_cost(self, model: str, tokens: int) -> float:
        pricing = AGENT_PRICING.get(model, AGENT_PRICING["gpt-4o-mini"])
        # Ước lượng: 60% input, 40% output
        input_t = int(tokens * 0.6)
        output_t = int(tokens * 0.4)
        return (input_t / 1_000_000 * pricing["input"]) + (output_t / 1_000_000 * pricing["output"])

    def get_cost_summary(self) -> Dict[str, Any]:
        """Báo cáo tổng hợp chi phí Agent."""
        return {
            "agent_total_cost_usd": round(self.total_agent_cost, 4),
            "agent_total_input_tokens": self.total_agent_input_tokens,
            "agent_total_output_tokens": self.total_agent_output_tokens,
        }
