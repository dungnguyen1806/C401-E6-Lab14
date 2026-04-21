import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI


SYSTEM_PROMPT = """You are an expert AI evaluator.
You will compare a generated answer against a reference answer for the same question.
Evaluate factual accuracy, completeness, safety, and clarity.

Return a valid JSON object with exactly these keys:
{
  "reasoning": "short explanation",
  "winner": "A" or "B" or "Tie",
  "score_a": <integer 1-5>,
  "score_b": <integer 1-5>
}
"""


class LLMJudge:
    """
    Hai's scope:
    - call at least 2 judge models
    - reduce position bias by swapping answer order
    - compute agreement rate
    - expose enough metadata for Thuan's runner/cost tracker
    """

    def __init__(
        self,
        *,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",
        gemini_model: str = "gemini-2.5-flash",
    ):
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        self.openai_model = openai_model
        self.gemini_model = gemini_model
        self.judges = self._build_judges()

    def _build_judges(self) -> List[Dict[str, Any]]:
        judges: List[Dict[str, Any]] = []
        if self.openai_api_key:
            judges.append(
                {
                    "model": self.openai_model,
                    "client": AsyncOpenAI(api_key=self.openai_api_key),
                }
            )
        if self.gemini_api_key:
            judges.append(
                {
                    "model": self.gemini_model,
                    "client": AsyncOpenAI(
                        api_key=self.gemini_api_key,
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    ),
                }
            )
        return judges

    def _build_user_prompt(self, question: str, answer_a: str, answer_b: str) -> str:
        return (
            f"[Question]\n{question}\n\n"
            f"[Answer A]\n{answer_a}\n\n"
            f"[Answer B]\n{answer_b}\n\n"
            "Task:\n"
            "1. Compare the two answers.\n"
            "2. Decide which answer is better.\n"
            "3. Score both answers from 1 to 5.\n"
            "4. Keep reasoning concise.\n"
        )

    def _normalize_usage(self, usage: Any) -> Dict[str, int]:
        if not usage:
            return {"prompt_tokens": 0, "completion_tokens": 0, "tokens_used": 0}

        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "tokens_used": total_tokens,
        }

    def _fallback_result(self, reason: str) -> Dict[str, Any]:
        return {
            "reasoning": reason,
            "winner": "Tie",
            "score_a": 3,
            "score_b": 3,
        }

    async def _call_judge(
        self,
        client: AsyncOpenAI,
        model: str,
        question: str,
        answer_a: str,
        answer_b: str,
    ) -> Dict[str, Any]:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_user_prompt(question, answer_a, answer_b)},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            parsed = json.loads(response.choices[0].message.content)
            usage = self._normalize_usage(response.usage)
            return {
                "model": model,
                "payload": parsed,
                "token_usage": usage,
            }
        except Exception as exc:
            return {
                "model": model,
                "payload": self._fallback_result(f"{model}_error: {exc}"),
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "tokens_used": 0},
                "error": str(exc),
            }

    def _extract_agent_score(self, run_payload: Dict[str, Any], agent_is_a: bool) -> float:
        key = "score_a" if agent_is_a else "score_b"
        try:
            return float(run_payload["payload"].get(key, 3))
        except (TypeError, ValueError):
            return 3.0

    def _aggregate_usage(self, run_a: Dict[str, Any], run_b: Dict[str, Any]) -> Dict[str, int]:
        return {
            "prompt_tokens": run_a["token_usage"]["prompt_tokens"] + run_b["token_usage"]["prompt_tokens"],
            "completion_tokens": run_a["token_usage"]["completion_tokens"] + run_b["token_usage"]["completion_tokens"],
            "tokens_used": run_a["token_usage"]["tokens_used"] + run_b["token_usage"]["tokens_used"],
        }

    def _build_model_result(self, model: str, run_a: Dict[str, Any], run_b: Dict[str, Any]) -> Dict[str, Any]:
        score_1 = self._extract_agent_score(run_a, agent_is_a=True)
        score_2 = self._extract_agent_score(run_b, agent_is_a=False)
        average_score = round((score_1 + score_2) / 2, 3)
        score_delta = abs(score_1 - score_2)
        swapped_consistent = score_delta <= 1.0

        return {
            "model": model,
            "score": average_score,
            "swapped_consistent": swapped_consistent,
            "position_bias_delta": round(score_delta, 3),
            "token_usage": self._aggregate_usage(run_a, run_b),
            "runs": {
                "agent_as_a": run_a["payload"],
                "agent_as_b": run_b["payload"],
            },
            "errors": [item for item in [run_a.get("error"), run_b.get("error")] if item],
        }

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        if len(self.judges) < 2:
            fallback_reason = "Need at least 2 configured judge models"
            return {
                "final_score": 0.0,
                "agreement_rate": 0.0,
                "reasoning": fallback_reason,
                "individual_scores": {},
                "details": {},
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "tokens_used": 0},
                "model": "multi-judge",
                "error": fallback_reason,
            }

        tasks: List[Tuple[str, asyncio.Task, asyncio.Task]] = []
        for judge in self.judges:
            model = judge["model"]
            client = judge["client"]
            run_agent_first = asyncio.create_task(self._call_judge(client, model, question, answer, ground_truth))
            run_reference_first = asyncio.create_task(self._call_judge(client, model, question, ground_truth, answer))
            tasks.append((model, run_agent_first, run_reference_first))

        model_results: List[Dict[str, Any]] = []
        for model, run_1_task, run_2_task in tasks:
            run_1, run_2 = await asyncio.gather(run_1_task, run_2_task)
            model_results.append(self._build_model_result(model, run_1, run_2))

        individual_scores = {item["model"]: item["score"] for item in model_results}
        scores = list(individual_scores.values())
        final_score = round(sum(scores) / len(scores), 3) if scores else 0.0
        max_gap = max(scores) - min(scores) if len(scores) > 1 else 0.0
        agreement_rate = 1.0 if max_gap <= 1.0 else 0.5

        total_usage = {
            "prompt_tokens": sum(item["token_usage"]["prompt_tokens"] for item in model_results),
            "completion_tokens": sum(item["token_usage"]["completion_tokens"] for item in model_results),
            "tokens_used": sum(item["token_usage"]["tokens_used"] for item in model_results),
        }

        reasoning = (
            f"Judged by {len(model_results)} models. "
            f"Avg score={final_score}, max score gap={round(max_gap, 3)}."
        )

        if max_gap > 2.0:
            reasoning += " Strong disagreement detected; manual review or re-prompt recommended."

        return {
            "final_score": final_score,
            "agreement_rate": agreement_rate,
            "reasoning": reasoning,
            "individual_scores": individual_scores,
            "details": {item["model"]: item for item in model_results},
            "token_usage": total_usage,
            "model": "multi-judge",
        }
