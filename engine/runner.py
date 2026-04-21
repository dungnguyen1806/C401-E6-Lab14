import asyncio
import time
from typing import Any, Dict, List, Optional


class BenchmarkRunner:
    DEFAULT_MODEL_PRICING = {
        "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.00060},
        "gpt-4o": {"input_per_1k": 0.00500, "output_per_1k": 0.01500},
        "claude-3-5": {"input_per_1k": 0.00300, "output_per_1k": 0.01500},
        "claude-3-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    }

    def __init__(
        self,
        agent,
        evaluator,
        judge,
        *,
        model_pricing: Optional[Dict[str, Dict[str, float]]] = None,
        max_concurrency: int = 5,
        case_timeout: float = 30.0,
    ):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.model_pricing = model_pricing or self.DEFAULT_MODEL_PRICING
        self.max_concurrency = max_concurrency
        self.case_timeout = case_timeout

    def _get_ground_truth_answer(self, test_case: Dict[str, Any]) -> str:
        return (
            test_case.get("ground_truth_answer")
            or test_case.get("expected_answer")
            or ""
        )

    def _get_ground_truth_chunk_ids(self, test_case: Dict[str, Any]) -> List[str]:
        return (
            test_case.get("ground_truth_chunk_ids")
            or test_case.get("expected_retrieval_ids")
            or []
        )

    def _normalize_usage(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        prompt_tokens = int(metadata.get("prompt_tokens", 0) or 0)
        completion_tokens = int(metadata.get("completion_tokens", 0) or 0)
        total_tokens = int(metadata.get("tokens_used", prompt_tokens + completion_tokens) or 0)

        if total_tokens and not (prompt_tokens or completion_tokens):
            prompt_tokens = total_tokens
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _estimate_cost_usd(self, model: str, usage: Dict[str, int]) -> float:
        pricing = self.model_pricing.get(model)
        if not pricing:
            return 0.0

        input_cost = (usage["prompt_tokens"] / 1000) * pricing["input_per_1k"]
        output_cost = (usage["completion_tokens"] / 1000) * pricing["output_per_1k"]
        return round(input_cost + output_cost, 6)

    async def _safe_score(self, test_case: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await self.evaluator.score(test_case, response)
        except Exception as exc:
            return {
                "faithfulness": 0.0,
                "relevancy": 0.0,
                "retrieval": {"hit_rate": 0.0, "mrr": 0.0},
                "error": f"evaluator_failed: {exc}",
            }

    async def _safe_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        try:
            return await self.judge.evaluate_multi_judge(question, answer, ground_truth)
        except Exception as exc:
            return {
                "final_score": 0.0,
                "agreement_rate": 0.0,
                "reasoning": f"judge_failed: {exc}",
                "error": f"judge_failed: {exc}",
            }

    async def _run_single_test_impl(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        started_at = time.perf_counter()
        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - started_at

        ragas_scores, judge_result = await asyncio.gather(
            self._safe_score(test_case, response),
            self._safe_judge(
                test_case["question"],
                response.get("answer", ""),
                self._get_ground_truth_answer(test_case),
            ),
        )

        metadata = response.get("metadata", {})
        usage = self._normalize_usage(metadata)
        model = metadata.get("model", "unknown")
        cost_usd = self._estimate_cost_usd(model, usage)

        return {
            "question_id": test_case.get("question_id"),
            "test_case": test_case["question"],
            "question_type": test_case.get("question_type", test_case.get("metadata", {}).get("type", "unknown")),
            "complexity": test_case.get("complexity", test_case.get("metadata", {}).get("difficulty", "unknown")),
            "agent_response": response.get("answer", ""),
            "latency": latency,
            "ragas": ragas_scores,
            "judge": judge_result,
            "status": "fail" if judge_result.get("final_score", 0) < 3 else "pass",
            "retrieved_ids": response.get("retrieved_ids", []),
            "ground_truth_chunk_ids": self._get_ground_truth_chunk_ids(test_case),
            "token_usage": usage,
            "cost_usd": cost_usd,
            "agent_metadata": {
                "model": model,
                "sources": metadata.get("sources", []),
                "contexts_returned": len(response.get("contexts", [])),
            },
        }

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                self._run_single_test_impl(test_case),
                timeout=self.case_timeout,
            )
            result["wall_time"] = time.perf_counter() - started_at
            return result
        except asyncio.TimeoutError:
            return {
                "test_case": test_case.get("question", ""),
                "agent_response": "",
                "latency": self.case_timeout,
                "wall_time": time.perf_counter() - started_at,
                "ragas": {
                    "faithfulness": 0.0,
                    "relevancy": 0.0,
                    "retrieval": {"hit_rate": 0.0, "mrr": 0.0},
                },
                "judge": {
                    "final_score": 0.0,
                    "agreement_rate": 0.0,
                    "reasoning": "runner_timeout",
                },
                "status": "error",
                "retrieved_ids": [],
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "cost_usd": 0.0,
                "agent_metadata": {"model": "unknown", "sources": [], "contexts_returned": 0},
                "error": "timeout",
            }
        except Exception as exc:
            return {
                "test_case": test_case.get("question", ""),
                "agent_response": "",
                "latency": 0.0,
                "wall_time": time.perf_counter() - started_at,
                "ragas": {
                    "faithfulness": 0.0,
                    "relevancy": 0.0,
                    "retrieval": {"hit_rate": 0.0, "mrr": 0.0},
                },
                "judge": {
                    "final_score": 0.0,
                    "agreement_rate": 0.0,
                    "reasoning": f"runner_failed: {exc}",
                },
                "status": "error",
                "retrieved_ids": [],
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "cost_usd": 0.0,
                "agent_metadata": {"model": "unknown", "sources": [], "contexts_returned": 0},
                "error": str(exc),
            }

    async def run_all(self, dataset: List[Dict[str, Any]], batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size để không bị rate limit.
        """
        effective_batch_size = batch_size or self.max_concurrency
        results = []
        for i in range(0, len(dataset), effective_batch_size):
            batch = dataset[i:i + effective_batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        return results
