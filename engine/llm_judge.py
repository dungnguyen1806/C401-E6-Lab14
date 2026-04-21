import asyncio
import os
import json
from typing import Dict, Any
from openai import AsyncOpenAI

SYSTEM_PROMPT = """You are an expert AI evaluator.
You will be provided with a Question, and two answers (Answer A and Answer B).
One of these answers is the generated response, and the other is the Reference Ground Truth.
Your task is to compare them and evaluate the quality of both answers.

[Question]: {question}

[Answer A]: {answer_a}
[Answer B]: {answer_b}

Tasks:
1. Think step-by-step (Chain of Thought): Analyze the factual accuracy, completeness, and clarity of both answers.
2. Determine which answer is better ('A', 'B', or 'Tie').
3. Based on your analysis, assign a score from 1 to 5 for Answer A, and a score from 1 to 5 for Answer B.
   - 5: Excellent
   - 4: Good
   - 3: Acceptable
   - 2: Poor
   - 1: Completely incorrect

Output your response as a valid JSON object with the following format exactly:
{
    "chain_of_thought": "your step-by-step reasoning",
    "winner": "A" or "B" or "Tie",
    "score_a": <int>,
    "score_b": <int>
}
"""

class LLMJudge:
    def __init__(self):
        # Initialize 2 clients: OpenAI for gpt-4o, and OpenAI compatible endpoint for Gemini
        # as requested: "gemini api is from google ai studio and open api key is from open ai"
        self.openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.gemini_client = AsyncOpenAI(
            api_key=os.environ.get("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.models = {
            "gpt-4o": self.openai_client,
            "gemini-2.5-flash": self.gemini_client
        }

    async def _call_judge(self, client: AsyncOpenAI, model: str, question: str, answer_a: str, answer_b: str) -> dict:
        prompt = SYSTEM_PROMPT.format(question=question, answer_a=answer_a, answer_b=answer_b)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful and expert AI judge. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error calling {model}: {e}")
            return {"chain_of_thought": "Error", "winner": "Tie", "score_a": 3, "score_b": 3}

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """
        EXPERT TASK: Calls 2 models (gpt-4o and gemini-2.5-flash).
        Performs Pairwise evaluation, uses CoT, runs 2 times (swapping A and B) to avoid position bias.
        """
        # Run 1: A = Agent, B = Ground Truth
        # Run 2: A = Ground Truth, B = Agent
        
        tasks = []
        for model_name, client in self.models.items():
            # Run 1
            tasks.append(self._call_judge(client, model_name, question, answer, ground_truth))
            # Run 2 (Swapped)
            tasks.append(self._call_judge(client, model_name, question, ground_truth, answer))
            
        # Execute API calls concurrently
        results = await asyncio.gather(*tasks)
        
        # Parse results
        # tasks order: [gpt4o_run1, gpt4o_run2, gemini_run1, gemini_run2]
        gpt4o_r1, gpt4o_r2, gemini_r1, gemini_r2 = results
        
        # Extract Agent score
        # In Run 1, Agent is A so score is score_a
        # In Run 2, Agent is B so score is score_b
        gpt4o_agent_score_1 = gpt4o_r1.get("score_a", 3)
        gpt4o_agent_score_2 = gpt4o_r2.get("score_b", 3)
        gpt4o_avg = (gpt4o_agent_score_1 + gpt4o_agent_score_2) / 2
        
        gemini_agent_score_1 = gemini_r1.get("score_a", 3)
        gemini_agent_score_2 = gemini_r2.get("score_b", 3)
        gemini_avg = (gemini_agent_score_1 + gemini_agent_score_2) / 2
        
        final_score = (gpt4o_avg + gemini_avg) / 2
        
        # Calculate Consensus / Agreement Rate
        # Assume consensus if score difference is <= 1 point
        agreement_rate = 1.0 if abs(gpt4o_avg - gemini_avg) <= 1.0 else 0.5
        
        return {
            "final_score": final_score,
            "agreement_rate": agreement_rate,
            "individual_scores": {
                "gpt-4o": gpt4o_avg,
                "gemini-2.5-flash": gemini_avg
            },
            "details": {
                "gpt-4o_run1": gpt4o_r1,
                "gpt-4o_run2": gpt4o_r2,
                "gemini-2.5-flash_run1": gemini_r1,
                "gemini-2.5-flash_run2": gemini_r2
            }
        }