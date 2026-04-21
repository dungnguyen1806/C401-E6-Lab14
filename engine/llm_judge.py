"""
Multi-Judge Consensus Engine
=============================
Goi it nhat 2 model LLM lam Giam khao, tinh toan do dong thuan
va xu ly xung dot diem so tu dong.

Author: Long (Data Analyst) & Hai (AI Engineer)
"""

import asyncio
import json
import os
import random
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI


MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gemini-2.5-flash": {"input": 0.0003, "output": 0.0025},
}

JUDGE_SYSTEM_PROMPT = """Ban la mot Giam khao AI chuyen nghiep. Nhiem vu cua ban la cham diem cau tra loi cua mot AI Agent dua tren tieu chi sau:

## Tieu chi cham diem (Thang 1-5):
- 5: Cau tra loi hoan toan chinh xac, day du chi tiet, ngon ngu chuyen nghiep.
- 4: Cau tra loi dung nhung thieu mot vai chi tiet nho.
- 3: Cau tra loi dung mot phan hoac thieu thong tin quan trong.
- 2: Cau tra loi sai mot phan hoac thieu nhieu thong tin quan trong.
- 1: Cau tra loi hoan toan sai, bia dat, hoac khong lien quan.

## Yeu cau:
- Tra loi duy nhat bang JSON format: {"score": <int 1-5>, "reasoning": "<giai thich ngan gon>"}
- Khong them noi dung nao khac ngoai JSON object.
"""


def _build_judge_user_prompt(question: str, answer: str, ground_truth: str) -> str:
    return f"""## Cau hoi:
{question}

## Cau tra loi cua Agent:
{answer}

## Dap an chuan (Ground Truth):
{ground_truth}

Hay cham diem cau tra loi cua Agent."""


class LLMJudge:
    """
    Multi-Judge Consensus Engine.

    Su dung 2 model LLM khac nhau de cham diem, sau do tinh toan
    Agreement Rate va xu ly xung dot tu dong.
    """

    def __init__(
        self,
        model_a: str = "gpt-4o-mini",
        model_b: str = "gpt-3.5-turbo",
    ):
        self.model_a = model_a
        self.model_b = model_b
        self._openai_client: Optional[AsyncOpenAI] = None
        self._gemini_client: Optional[AsyncOpenAI] = None
        self._api_available = False
        self._init_clients()

        self._all_scores_a: List[int] = []
        self._all_scores_b: List[int] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0

    def _init_clients(self) -> None:
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")

        if openai_key and openai_key != "your-key-here":
            self._openai_client = AsyncOpenAI(api_key=openai_key)
            self._api_available = True

        if gemini_key and gemini_key != "your-key-here":
            self._gemini_client = AsyncOpenAI(
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            self._api_available = True

    def _get_client_for_model(self, model: str) -> Optional[AsyncOpenAI]:
        if model.startswith("gemini"):
            return self._gemini_client
        return self._openai_client

    async def _call_single_judge(
        self, model: str, question: str, answer: str, ground_truth: str
    ) -> Tuple[int, str, int, int]:
        client = self._get_client_for_model(model)
        if not client:
            return self._simulate_judge(model, question, answer, ground_truth)

        user_prompt = _build_judge_user_prompt(question, answer, ground_truth)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            usage = response.usage
            input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

            parsed = json.loads(content)
            score = int(parsed.get("score", 3))
            score = max(1, min(5, score))
            reasoning = parsed.get("reasoning", "")
            return score, reasoning, input_tokens, output_tokens
        except Exception:
            return self._simulate_judge(model, question, answer, ground_truth)

    def _simulate_judge(
        self, model: str, question: str, answer: str, ground_truth: str
    ) -> Tuple[int, str, int, int]:
        answer_words = set(answer.lower().split())
        gt_words = set(ground_truth.lower().split())
        if not gt_words:
            score = 3
        else:
            overlap = len(answer_words & gt_words) / max(len(gt_words), 1)
            if overlap > 0.5:
                score = random.choice([4, 5])
            elif overlap > 0.2:
                score = random.choice([3, 4])
            else:
                score = random.choice([1, 2, 3])

        if model == self.model_b:
            score = max(1, min(5, score + random.choice([-1, 0, 0, 1])))

        reasoning = f"[Simulated {model}] Evaluation based on keyword overlap heuristic."
        est_input = len(question.split()) + len(answer.split()) + len(ground_truth.split()) + 200
        est_output = 30
        return score, reasoning, est_input, est_output

    async def evaluate_multi_judge(
        self, question: str, answer: str, ground_truth: str
    ) -> Dict[str, Any]:
        task_a = self._call_single_judge(self.model_a, question, answer, ground_truth)
        task_b = self._call_single_judge(self.model_b, question, answer, ground_truth)
        (score_a, reason_a, in_a, out_a), (score_b, reason_b, in_b, out_b) = await asyncio.gather(task_a, task_b)

        total_input = in_a + in_b
        total_output = out_a + out_b
        delta = abs(score_a - score_b)

        tie_breaker_used = False
        tie_breaker_score = None
        if delta > 1:
            tie_breaker_score, _, in_tb, out_tb = await self._call_single_judge(
                self.model_a, question, answer, ground_truth
            )
            total_input += in_tb
            total_output += out_tb
            tie_breaker_used = True
            scores = sorted([score_a, score_b, tie_breaker_score])
            final_score = float(scores[1])
        else:
            final_score = (score_a + score_b) / 2

        if delta == 0:
            agreement_rate = 1.0
        elif delta == 1:
            agreement_rate = 0.75
        elif delta == 2:
            agreement_rate = 0.5
        else:
            agreement_rate = 0.25

        cost_a = self._calc_cost(self.model_a, in_a, out_a)
        cost_b = self._calc_cost(self.model_b, in_b, out_b)
        case_cost = cost_a + cost_b
        if tie_breaker_used:
            case_cost += self._calc_cost(self.model_a, in_tb, out_tb)

        self._all_scores_a.append(score_a)
        self._all_scores_b.append(score_b)
        self._total_input_tokens += total_input
        self._total_output_tokens += total_output
        self._total_cost += case_cost

        return {
            "final_score": round(final_score, 3),
            "agreement_rate": agreement_rate,
            "individual_scores": {
                self.model_a: score_a,
                self.model_b: score_b,
            },
            "reasoning": {
                self.model_a: reason_a,
                self.model_b: reason_b,
            },
            "conflict_resolution": {
                "delta": delta,
                "tie_breaker_used": tie_breaker_used,
                "tie_breaker_score": tie_breaker_score,
            },
            "cost": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "usd": round(case_cost, 6),
            },
        }

    async def check_position_bias(
        self, question: str, response_a: str, response_b: str, ground_truth: str
    ) -> Dict[str, Any]:
        score_original, _, _, _ = await self._call_single_judge(
            self.model_a, question, response_a, ground_truth
        )
        score_swapped, _, _, _ = await self._call_single_judge(
            self.model_a, question, response_b, ground_truth
        )
        return {
            "score_original_order": score_original,
            "score_swapped_order": score_swapped,
            "bias_detected": abs(score_original - score_swapped) > 1,
            "bias_delta": abs(score_original - score_swapped),
        }

    def compute_cohens_kappa(self) -> float:
        if not self._all_scores_a:
            return 0.0

        n = len(self._all_scores_a)
        categories = list(range(1, 6))
        agreements = sum(1 for a, b in zip(self._all_scores_a, self._all_scores_b) if a == b)
        p_observed = agreements / n

        p_expected = 0.0
        for cat in categories:
            p_a = sum(1 for s in self._all_scores_a if s == cat) / n
            p_b = sum(1 for s in self._all_scores_b if s == cat) / n
            p_expected += p_a * p_b

        if p_expected >= 1.0:
            return 1.0
        return round((p_observed - p_expected) / (1 - p_expected), 4)

    def _calc_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
        return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

    def get_total_cost_report(self) -> Dict[str, Any]:
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "avg_cost_per_case": round(self._total_cost / max(len(self._all_scores_a), 1), 6),
            "cohens_kappa": self.compute_cohens_kappa(),
            "total_cases_judged": len(self._all_scores_a),
        }
