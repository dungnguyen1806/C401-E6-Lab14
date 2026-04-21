"""
Multi-Judge Consensus Engine (Optimized for Gemini 2.5 Flash)
===========================================================
Hệ thống sử dụng Gemini 2.5 Flash làm giám khảo chính kết hợp với 
GPT-4o-mini để tạo ra sự đồng thuận (Consensus) trong đánh giá AI.

Author: Long & Hai (Refined by Gemini)
"""

import asyncio
import json
import os
import random
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.10, "output": 0.40}, 
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
}

JUDGE_SYSTEM_PROMPT = """Bạn là một Giám khảo AI chuyên nghiệp, có tư duy phản biện cao. 
Nhiệm vụ: Chấm điểm câu trả lời của AI Agent dựa trên Ground Truth (Đáp án chuẩn).

## Tiêu chí chấm điểm (Thang 1-5):
- 5 (Excellent): Hoàn hảo, chính xác tuyệt đối, hành văn chuyên nghiệp.
- 4 (Good): Đúng trọng tâm, thấu đáo nhưng có thể thiếu một chi tiết cực nhỏ không đáng kể.
- 3 (Fair): Đúng ý chính nhưng thiếu thông tin quan trọng hoặc cách diễn đạt chưa tối ưu.
- 2 (Poor): Có sai sót về kiến thức hoặc thiếu hụt phần lớn nội dung cần thiết.
- 1 (Fail): Sai hoàn toàn, bịa đặt (hallucination) hoặc không liên quan.

## Quy định định dạng:
Chỉ phản hồi duy nhất một JSON object với cấu trúc:
{"score": <int>, "reasoning": "<giải thích súc tích bằng tiếng Việt trong 2 câu>"}
"""

def _build_judge_user_prompt(question: str, answer: str, ground_truth: str) -> str:
    return f"""## Bối cảnh:
- Câu hỏi: {question}
- Đáp án chuẩn: {ground_truth}

## Câu trả lời cần chấm điểm:
{answer}

Hãy phân tích và đưa ra điểm số."""

class LLMJudge:
    """
    Multi-Judge Consensus Engine.
    Sử dụng Gemini 2.5 Flash làm Judge chủ lực để tối ưu chi phí và tốc độ.
    """

    def __init__(
        self,
        model_a: str = "gemini-2.5-flash", # Ưu tiên Gemini 2.5 Flash
        model_b: str = "gpt-4o-mini",      # Cross-check với OpenAI
    ):
        self.model_a = model_a
        self.model_b = model_b
        
        self._openai_client: Optional[AsyncOpenAI] = None
        self._gemini_client: Optional[AsyncOpenAI] = None
        self._init_clients()

        # Metrics Tracking
        self._all_scores_a: List[int] = []
        self._all_scores_b: List[int] = []
        self._total_stats = {"input": 0, "output": 0, "cost": 0.0}

    def _init_clients(self) -> None:
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")

        if openai_key:
            self._openai_client = AsyncOpenAI(api_key=openai_key)
        
        if gemini_key:
            # Endpoint chuẩn cho Gemini qua giao thức OpenAI
            self._gemini_client = AsyncOpenAI(
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )

    def _get_client_for_model(self, model: str) -> Optional[AsyncOpenAI]:
        return self._gemini_client if "gemini" in model else self._openai_client

    async def _call_single_judge(
        self, model: str, question: str, answer: str, ground_truth: str, temp: float = 0.0
    ) -> Tuple[int, str, int, int]:
        client = self._get_client_for_model(model)
        if not client:
            return self._simulate_fallback(model)

        user_content = _build_judge_user_prompt(question, answer, ground_truth)
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=temp,
                response_format={"type": "json_object"} if "gemini" not in model else None, # Gemini tự hiểu JSON tốt
                max_tokens=300
            )
            
            raw_content = response.choices[0].message.content
            # Cleanup Markdown code blocks nếu có
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(raw_content)
            score = max(1, min(5, int(data.get("score", 3))))
            
            usage = response.usage
            return (
                score, 
                data.get("reasoning", ""), 
                usage.prompt_tokens, 
                usage.completion_tokens
            )
        except Exception as e:
            print(f"Error calling {model}: {e}")
            return self._simulate_fallback(model)

    def _simulate_fallback(self, model: str) -> Tuple[int, str, int, int]:
        """Dùng làm phương án dự phòng khi API lỗi"""
        return (3, f"Fallback: API {model} gặp sự cố.", 0, 0)

    async def evaluate_multi_judge(
        self, question: str, answer: str, ground_truth: str
    ) -> Dict[str, Any]:
        # Chạy song song 2 giám khảo
        task_a = self._call_single_judge(self.model_a, question, answer, ground_truth)
        task_b = self._call_single_judge(self.model_b, question, answer, ground_truth)
        
        res_a, res_b = await asyncio.gather(task_a, task_b)
        score_a, reason_a, in_a, out_a = res_a
        score_b, reason_b, in_b, out_b = res_b

        delta = abs(score_a - score_b)
        final_score = (score_a + score_b) / 2
        tie_breaker_used = False
        
        # Nếu 2 model lệch nhau quá nhiều (>1 điểm), dùng Tie-Breaker
        if delta > 1:
            tie_breaker_used = True
            # Dùng lại model A (Gemini 2.5 Flash) nhưng với temperature cao hơn để check lại
            tb_score, tb_reason, in_tb, out_tb = await self._call_single_judge(
                self.model_a, question, answer, ground_truth, temp=0.7
            )
            scores = sorted([score_a, score_b, tb_score])
            final_score = float(scores[1]) # Lấy trung vị (Median)
            
            in_a += in_tb
            out_a += out_tb

        # Tính toán chi phí
        cost = self._calc_cost(self.model_a, in_a, out_a) + self._calc_cost(self.model_b, in_b, out_b)
        
        # Lưu stats
        self._all_scores_a.append(score_a)
        self._all_scores_b.append(score_b)
        self._total_stats["input"] += (in_a + in_b)
        self._total_stats["output"] += (out_a + out_b)
        self._total_stats["cost"] += cost

        return {
            "final_score": round(final_score, 2),
            "consensus_reached": delta <= 1,
            "individual_judgments": {
                "judge_primary": {"model": self.model_a, "score": score_a, "reason": reason_a},
                "judge_secondary": {"model": self.model_b, "score": score_b, "reason": reason_b}
            },
            "metrics": {
                "delta": delta,
                "cost_usd": round(cost, 6),
                "tie_breaker_active": tie_breaker_used
            }
        }

    def _calc_cost(self, model: str, in_t: int, out_t: int) -> float:
        p = MODEL_PRICING.get(model, MODEL_PRICING["gemini-2.5-flash"])
        return (in_t / 1_000_000 * p["input"]) + (out_t / 1_000_000 * p["output"])

    def get_summary_report(self) -> Dict[str, Any]:
        n = len(self._all_scores_a)
        return {
            "total_cases": n,
            "total_cost_usd": round(self._total_stats["cost"], 4),
            "avg_score": round(sum(self._all_scores_a) / max(n, 1), 2),
            "model_consistency_rate": self._calculate_agreement()
        }

    def _calculate_agreement(self) -> str:
        if not self._all_scores_a: return "0%"
        matches = sum(1 for a, b in zip(self._all_scores_a, self._all_scores_b) if abs(a-b) <= 1)
        return f"{(matches / len(self._all_scores_a)) * 100:.1f}%"