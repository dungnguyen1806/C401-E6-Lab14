import asyncio
import time
from typing import Any, Dict, List, Optional


class BenchmarkRunner:
    DEFAULT_MODEL_PRICING = {
        "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.00060},
        "gpt-4o": {"input_per_1k": 0.00500, "output_per_1k": 0.01500},
        "claude-3-5": {"input_per_1k": 0.00300, "output_per_1k": 0.01500},
        "claude-3-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
        "gemini-2.5-flash": {"input_per_1k": 0.00030, "output_per_1k": 0.00250},
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
        return test_case.get("ground_truth_answer") or test_case.get("expected_answer") or ""

    def _get_ground_truth_chunk_ids(self, test_case: Dict[str, Any]) -> List[str]:
        return test_case.get("ground_truth_chunk_ids") or test_case.get("expected_retrieval_ids") or []

    def _normalize_single_usage(self, payload: Dict[str, Any]) -> Dict[str, int]:
        prompt_tokens = int(payload.get("prompt_tokens", 0) or 0)
        completion_tokens = int(payload.get("completion_tokens", 0) or 0)
        total_tokens = int(payload.get("tokens_used", prompt_tokens + completion_tokens) or 0)

        if total_tokens and not (prompt_tokens or completion_tokens):
            prompt_tokens = total_tokens
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _normalize_usage(self, metadata: Dict[str, Any], judge_result: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        agent_usage = self._normalize_single_usage(metadata)
        judge_usage = self._normalize_single_usage(judge_result.get("token_usage", {})) if judge_result else {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        return {
            "prompt_tokens": agent_usage["prompt_tokens"] + judge_usage["prompt_tokens"],
            "completion_tokens": agent_usage["completion_tokens"] + judge_usage["completion_tokens"],
            "total_tokens": agent_usage["total_tokens"] + judge_usage["total_tokens"],
            "agent_prompt_tokens": agent_usage["prompt_tokens"],
            "agent_completion_tokens": agent_usage["completion_tokens"],
            "agent_total_tokens": agent_usage["total_tokens"],
            "judge_prompt_tokens": judge_usage["prompt_tokens"],
            "judge_completion_tokens": judge_usage["completion_tokens"],
            "judge_total_tokens": judge_usage["total_tokens"],
        }

    def _estimate_cost_usd(
        self,
        model: str,
        usage: Dict[str, int],
        *,
        prompt_key: str = "prompt_tokens",
        completion_key: str = "completion_tokens",
    ) -> float:
        pricing = self.model_pricing.get(model)
        if not pricing:
            return 0.0
        input_cost = (usage[prompt_key] / 1000) * pricing["input_per_1k"]
        output_cost = (usage[completion_key] / 1000) * pricing["output_per_1k"]
        return round(input_cost + output_cost, 6)

    def _extract_judge_cost(self, judge_result: Dict[str, Any], usage: Dict[str, int]) -> float:
        direct_cost = judge_result.get("cost_usd")
        if direct_cost is not None:
            return round(float(direct_cost), 6)

        details = judge_result.get("details", {})
        total_cost = 0.0
        for model_name, item in details.items():
            model_usage = self._normalize_single_usage(item.get("token_usage", {}))
            total_cost += self._estimate_cost_usd(model_name, model_usage)
        if total_cost:
            return round(total_cost, 6)

        judge_model = judge_result.get("model")
        if not judge_model or usage["judge_total_tokens"] == 0:
            return 0.0
        return self._estimate_cost_usd(
            judge_model,
            usage,
            prompt_key="judge_prompt_tokens",
            completion_key="judge_completion_tokens",
        )

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
                "individual_scores": {},
                "details": {},
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "tokens_used": 0},
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
        usage = self._normalize_usage(metadata, judge_result)
        model = metadata.get("model", "unknown")
        agent_cost_usd = self._estimate_cost_usd(
            model,
            usage,
            prompt_key="agent_prompt_tokens",
            completion_key="agent_completion_tokens",
        )
        judge_cost_usd = self._extract_judge_cost(judge_result, usage)
        total_cost_usd = round(agent_cost_usd + judge_cost_usd, 6)

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
            "cost_usd": total_cost_usd,
            "cost_breakdown": {
                "agent_cost_usd": agent_cost_usd,
                "judge_cost_usd": judge_cost_usd,
            },
            "agent_metadata": {
                "model": model,
                "sources": metadata.get("sources", []),
                "contexts_returned": len(response.get("contexts", [])),
            },
        }

    def _error_result(self, test_case: Dict[str, Any], *, reason: str, latency: float, wall_time: float) -> Dict[str, Any]:
        return {
            "question_id": test_case.get("question_id"),
            "test_case": test_case.get("question", ""),
            "question_type": test_case.get("question_type", test_case.get("metadata", {}).get("type", "unknown")),
            "complexity": test_case.get("complexity", test_case.get("metadata", {}).get("difficulty", "unknown")),
            "agent_response": "",
            "latency": latency,
            "wall_time": wall_time,
            "ragas": {
                "faithfulness": 0.0,
                "relevancy": 0.0,
                "retrieval": {"hit_rate": 0.0, "mrr": 0.0},
            },
            "judge": {
                "final_score": 0.0,
                "agreement_rate": 0.0,
                "reasoning": reason,
                "individual_scores": {},
                "details": {},
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "tokens_used": 0},
            },
            "status": "error",
            "retrieved_ids": [],
            "ground_truth_chunk_ids": self._get_ground_truth_chunk_ids(test_case),
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "agent_prompt_tokens": 0,
                "agent_completion_tokens": 0,
                "agent_total_tokens": 0,
                "judge_prompt_tokens": 0,
                "judge_completion_tokens": 0,
                "judge_total_tokens": 0,
            },
            "cost_usd": 0.0,
            "cost_breakdown": {"agent_cost_usd": 0.0, "judge_cost_usd": 0.0},
            "agent_metadata": {"model": "unknown", "sources": [], "contexts_returned": 0},
            "error": reason,
        }

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = await asyncio.wait_for(self._run_single_test_impl(test_case), timeout=self.case_timeout)
            result["wall_time"] = time.perf_counter() - started_at
            return result
        except asyncio.TimeoutError:
            return self._error_result(
                test_case,
                reason="runner_timeout",
                latency=self.case_timeout,
                wall_time=time.perf_counter() - started_at,
            )
        except Exception as exc:
            return self._error_result(
                test_case,
                reason=f"runner_failed: {exc}",
                latency=0.0,
                wall_time=time.perf_counter() - started_at,
            )

    async def run_all(self, dataset: List[Dict[str, Any]], batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
        effective_batch_size = batch_size or self.max_concurrency
        results: List[Dict[str, Any]] = []
        for i in range(0, len(dataset), effective_batch_size):
            batch = dataset[i:i + effective_batch_size]
            batch_results = await asyncio.gather(*(self.run_single_test(case) for case in batch))
            results.extend(batch_results)
        return results
