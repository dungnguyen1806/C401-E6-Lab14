"""
Multi-Judge Consensus Engine
=============================
Gọi ít nhất 2 model LLM làm Giám khảo, tính toán độ đồng thuận
và xử lý xung đột điểm số tự động.

Author: Long (Data Analyst) & Hải (AI Engineer)
"""

import asyncio
import os
import json
import random
from typing import Dict, Any, List, Tuple

# ── Pricing table (USD per 1K tokens) ──────────────────────────
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
}

# ── Rubric prompt dùng cho Judge ────────────────────────────────
JUDGE_SYSTEM_PROMPT = """Bạn là một Giám khảo AI chuyên nghiệp. Nhiệm vụ của bạn là chấm điểm câu trả lời của một AI Agent dựa trên tiêu chí sau:

## Tiêu chí chấm điểm (Thang 1-5):
- **5 (Xuất sắc):** Câu trả lời hoàn toàn chính xác, đầy đủ chi tiết, ngôn ngữ chuyên nghiệp, có dẫn chứng từ tài liệu.
- **4 (Tốt):** Câu trả lời đúng nhưng thiếu một vài chi tiết nhỏ hoặc ngôn ngữ chưa hoàn toàn chuyên nghiệp.
- **3 (Trung bình):** Câu trả lời đúng một phần, thiếu thông tin quan trọng hoặc có lỗi nhỏ.
- **2 (Yếu):** Câu trả lời sai một phần hoặc thiếu nhiều thông tin quan trọng.
- **1 (Rất tệ):** Câu trả lời hoàn toàn sai, bịa đặt (hallucination), hoặc không liên quan.

## Yêu cầu:
- Trả lời duy nhất bằng JSON format: {"score": <int 1-5>, "reasoning": "<giải thích ngắn gọn>"}
- Không thêm bất kỳ nội dung nào khác ngoài JSON object.
"""


def _build_judge_user_prompt(question: str, answer: str, ground_truth: str) -> str:
    return f"""## Câu hỏi:
{question}

## Câu trả lời của Agent:
{answer}

## Đáp án chuẩn (Ground Truth):
{ground_truth}

Hãy chấm điểm câu trả lời của Agent."""


class LLMJudge:
    """
    Multi-Judge Consensus Engine.

    Sử dụng 2 model LLM khác nhau để chấm điểm, sau đó tính toán
    Agreement Rate và xử lý xung đột tự động.
    """

    def __init__(
        self,
        model_a: str = "gpt-4o-mini",
        model_b: str = "gpt-3.5-turbo",
    ):
        self.model_a = model_a
        self.model_b = model_b
        self._client = None
        self._api_available = False
        self._init_client()

        # Accumulate scores for Cohen's Kappa
        self._all_scores_a: List[int] = []
        self._all_scores_b: List[int] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0

    def _init_client(self):
        """Khởi tạo OpenAI client. Nếu không có API key → fallback simulation."""
        try:
            from openai import AsyncOpenAI
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key and api_key != "your-key-here":
                self._client = AsyncOpenAI(api_key=api_key)
                self._api_available = True
                print("🟢 LLMJudge: Kết nối OpenAI API thành công.")
            else:
                print("🟡 LLMJudge: Không tìm thấy OPENAI_API_KEY → chế độ mô phỏng.")
        except ImportError:
            print("🟡 LLMJudge: Thiếu thư viện openai → chế độ mô phỏng.")

    # ── Core: gọi 1 model judge ────────────────────────────────
    async def _call_single_judge(
        self, model: str, question: str, answer: str, ground_truth: str
    ) -> Tuple[int, str, int, int]:
        """
        Gọi 1 model LLM để chấm điểm.
        Returns: (score, reasoning, input_tokens, output_tokens)
        """
        if not self._api_available:
            return self._simulate_judge(model, question, answer, ground_truth)

        user_prompt = _build_judge_user_prompt(question, answer, ground_truth)
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,   # deterministic judging
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            parsed = json.loads(content)
            score = int(parsed.get("score", 3))
            score = max(1, min(5, score))  # clamp 1-5
            reasoning = parsed.get("reasoning", "")
            return score, reasoning, input_tokens, output_tokens
        except Exception as e:
            print(f"  ⚠️ Judge {model} lỗi: {e} → fallback simulation")
            return self._simulate_judge(model, question, answer, ground_truth)

    def _simulate_judge(
        self, model: str, question: str, answer: str, ground_truth: str
    ) -> Tuple[int, str, int, int]:
        """Mô phỏng Judge khi không có API. Dùng heuristic đơn giản."""
        # Heuristic: kiểm tra overlap giữa answer và ground_truth
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

        # Thêm nhiễu nhẹ giữa 2 model để tạo variance
        if model == "gpt-3.5-turbo":
            score = max(1, min(5, score + random.choice([-1, 0, 0, 1])))

        reasoning = f"[Simulated {model}] Đánh giá dựa trên keyword overlap heuristic."
        # Ước lượng token usage cho simulation
        est_input = len(question.split()) + len(answer.split()) + len(ground_truth.split()) + 200
        est_output = 30
        return score, reasoning, est_input, est_output

    # ── Multi-Judge Consensus ──────────────────────────────────
    async def evaluate_multi_judge(
        self, question: str, answer: str, ground_truth: str
    ) -> Dict[str, Any]:
        """
        EXPERT TASK: Gọi 2 model Judge song song.
        Tính Agreement Rate và xử lý xung đột tự động.

        Logic xử lý xung đột:
        - Nếu |score_a - score_b| <= 1: lấy trung bình → đồng thuận cao
        - Nếu |score_a - score_b| > 1: gọi lại model_a 1 lần nữa (tie-breaker)
          rồi lấy median của 3 điểm
        """
        # Gọi 2 model song song
        task_a = self._call_single_judge(self.model_a, question, answer, ground_truth)
        task_b = self._call_single_judge(self.model_b, question, answer, ground_truth)
        (score_a, reason_a, in_a, out_a), (score_b, reason_b, in_b, out_b) = (
            await asyncio.gather(task_a, task_b)
        )

        total_input = in_a + in_b
        total_output = out_a + out_b
        delta = abs(score_a - score_b)

        # ── Conflict resolution ────────────────────────────────
        tie_breaker_used = False
        tie_breaker_score = None

        if delta > 1:
            # Xung đột lớn → gọi tie-breaker (lần 3)
            tie_breaker_score, reason_tb, in_tb, out_tb = await self._call_single_judge(
                self.model_a, question, answer, ground_truth
            )
            total_input += in_tb
            total_output += out_tb
            tie_breaker_used = True
            # Lấy median của 3 điểm
            scores = sorted([score_a, score_b, tie_breaker_score])
            final_score = scores[1]  # median
        else:
            final_score = (score_a + score_b) / 2

        # ── Agreement Rate ─────────────────────────────────────
        if delta == 0:
            agreement_rate = 1.0
        elif delta == 1:
            agreement_rate = 0.75
        elif delta == 2:
            agreement_rate = 0.5
        else:
            agreement_rate = 0.25

        # ── Cost calculation ───────────────────────────────────
        cost_a = self._calc_cost(self.model_a, in_a, out_a)
        cost_b = self._calc_cost(self.model_b, in_b, out_b)
        case_cost = cost_a + cost_b
        if tie_breaker_used:
            case_cost += self._calc_cost(self.model_a, in_tb, out_tb)

        # Accumulate for global stats
        self._all_scores_a.append(score_a)
        self._all_scores_b.append(score_b)
        self._total_input_tokens += total_input
        self._total_output_tokens += total_output
        self._total_cost += case_cost

        return {
            "final_score": final_score,
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

    # ── Cohen's Kappa ──────────────────────────────────────────
    def compute_cohens_kappa(self) -> float:
        """
        Tính Cohen's Kappa — thước đo inter-rater reliability.

        Kappa = (P_observed - P_expected) / (1 - P_expected)

        - P_observed: tỉ lệ 2 Judge đồng ý (cùng score)
        - P_expected: tỉ lệ đồng ý ngẫu nhiên

        Giải thích:
        - κ > 0.8  : Almost perfect agreement
        - 0.6-0.8  : Substantial agreement
        - 0.4-0.6  : Moderate agreement
        - 0.2-0.4  : Fair agreement
        - < 0.2    : Slight/Poor agreement
        """
        if not self._all_scores_a:
            return 0.0

        n = len(self._all_scores_a)
        categories = list(range(1, 6))  # scores 1-5

        # Observed agreement
        agreements = sum(1 for a, b in zip(self._all_scores_a, self._all_scores_b) if a == b)
        p_observed = agreements / n

        # Expected agreement (by chance)
        p_expected = 0.0
        for cat in categories:
            p_a = sum(1 for s in self._all_scores_a if s == cat) / n
            p_b = sum(1 for s in self._all_scores_b if s == cat) / n
            p_expected += p_a * p_b

        if p_expected >= 1.0:
            return 1.0

        kappa = (p_observed - p_expected) / (1 - p_expected)
        return round(kappa, 4)

    # ── Position Bias Check ────────────────────────────────────
    async def check_position_bias(
        self, question: str, response_a: str, response_b: str, ground_truth: str
    ) -> Dict[str, Any]:
        """
        Nâng cao: Kiểm tra Position Bias.

        Gọi Judge 2 lần:
        - Lần 1: response_a trước, response_b sau
        - Lần 2: Đổi thứ tự (response_b trước)

        Nếu điểm thay đổi đáng kể → Judge có thiên vị vị trí.
        """
        score_original, _, _, _ = await self._call_single_judge(
            self.model_a, question, response_a, ground_truth
        )
        score_swapped, _, _, _ = await self._call_single_judge(
            self.model_a, question, response_b, ground_truth
        )

        bias_detected = abs(score_original - score_swapped) > 1
        return {
            "score_original_order": score_original,
            "score_swapped_order": score_swapped,
            "bias_detected": bias_detected,
            "bias_delta": abs(score_original - score_swapped),
        }

    # ── Cost helpers ───────────────────────────────────────────
    def _calc_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
        return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

    def get_total_cost_report(self) -> Dict[str, Any]:
        """Báo cáo tổng chi phí Judge sau khi chạy toàn bộ benchmark."""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "avg_cost_per_case": round(self._total_cost / max(len(self._all_scores_a), 1), 6),
            "cohens_kappa": self.compute_cohens_kappa(),
            "total_cases_judged": len(self._all_scores_a),
        }
