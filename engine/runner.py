"""
Benchmark Runner — Async Pipeline with Cost Tracking
=====================================================
Chạy toàn bộ pipeline đánh giá song song bằng asyncio,
theo dõi token usage và chi phí cho mỗi lần Eval.

"""

import asyncio
import time
from typing import List, Dict
# Import other components...

class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge

    async def run_single_test(self, test_case: Dict) -> Dict:
        start_time = time.perf_counter()
        
        # 1. Gọi Agent
        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time
        
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
            "status": "fail" if judge_result["final_score"] < 3 else "pass"
        }

    async def run_all(self, dataset: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size để không bị Rate Limit.
        """
        results = []
        for i in range(0, len(dataset), batch_size):
            batch = dataset[i:i + batch_size]
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
