import asyncio
import os
from typing import Dict
from openai import AsyncOpenAI
from engine.file_retriever import FileRetriever

class MainAgent:
    """Agent chính xử lý query."""
    def __init__(self, version: str = "Agent_V1_Base"):
        self.version = version
        self.name = version
        self.retriever = FileRetriever("data/knowledge_base.json")
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"

    async def query(self, question: str) -> Dict:
        top_chunks = self.retriever.retrieve(question, top_k=3)
        retrieved_ids = [chunk.get("chunk_id", "") for chunk in top_chunks if chunk.get("chunk_id")]
        contexts = [chunk.get("text", "") for chunk in top_chunks]

        # Calculate a rough overlap ratio for thresholding in V2
        q_tokens = set(self.retriever._tokenize(question))
        highest_ratio = 0.0
        if contexts and q_tokens:
            for text in contexts:
                chunk_tokens = set(self.retriever._tokenize(text))
                ratio = len(q_tokens.intersection(chunk_tokens)) / len(q_tokens)
                highest_ratio = max(highest_ratio, ratio)

        # Version-specific behavior
        if self.version == "Agent_V2_Optimized":
            # REFINEMENT: Remove hard threshold (highest_ratio < 0.2) because it suppressed correct retrievals
            # Instead, rely on the LLM to strictly evaluate the context.
            
            system_prompt = (
                "Bạn là một trợ lý ảo hỗ trợ thông tin nội bộ cực kỳ nghiêm túc và chính xác.\n"
                "NHIỆM VỤ: Trả lời câu hỏi dựa TRỰC TIẾP và DUY NHẤT vào Context được cung cấp.\n"
                "QUY TẮC BẮT BUỘC:\n"
                "1. Nếu context KHÔNG chứa thông tin để trả lời, bạn BẮT BUỘC nói: 'Tôi không tìm thấy thông tin này trong tài liệu.'\n"
                "2. KHÔNG ĐƯỢC thêm thắt, bịa đặt hoặc dùng kiến thức bên ngoài.\n"
                "3. Trình bày ngắn gọn, súc tích, chuyên nghiệp."
            )
        else:
            system_prompt = (
                "Bạn là một trợ lý ảo thân thiện. Hãy trả lời câu hỏi dựa trên context. "
                "Nếu không có trong tài liệu, bạn có thể tự suy luận linh hoạt để giúp đỡ người dùng."
            )

        context_str = "\n".join(contexts) if contexts else "[Không có tài liệu nào]"
        user_prompt = f"Dựa trên các đoạn văn bản sau để trả lời câu hỏi.\n\nContext:\n{context_str}\n\nCâu hỏi:\n{question}"

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        answer = response.choices[0].message.content.strip()

        return {
            "answer": answer,
            "retrieved_ids": retrieved_ids,
            "contexts": contexts,
            "metadata": {
                "model": self.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "sources": ["data/knowledge_base.json"]
            }
        }
