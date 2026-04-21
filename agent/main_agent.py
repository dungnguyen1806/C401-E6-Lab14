import asyncio
from typing import Dict
from engine.file_retriever import FileRetriever

class MainAgent:
    """
    Đây là Agent mẫu sử dụng kiến trúc RAG đơn giản.
    Sinh viên nên thay thế phần này bằng Agent thực tế đã phát triển ở các buổi trước.
    """
    def __init__(self):
        self.name = "SupportAgent-v1"
        self.retriever = FileRetriever("data/knowledge_base.json")

    async def query(self, question: str) -> Dict:
        """
        Mô phỏng quy trình RAG:
        1. Retrieval: Tìm kiếm context liên quan.
        2. Generation: Gọi LLM để sinh câu trả lời.
        """
        # Giả lập độ trễ mạng/LLM
        await asyncio.sleep(0.5) 
        
        top_chunks = self.retriever.retrieve(question, top_k=3)
        retrieved_ids = [chunk.get("chunk_id", "") for chunk in top_chunks if chunk.get("chunk_id")]
        contexts = [chunk.get("text", "") for chunk in top_chunks]

        # Giả lập dữ liệu trả về, nhưng dùng context đã retrieve từ knowledge_base.json
        return {
            "answer": f"Dựa trên tài liệu hệ thống, tôi xin trả lời câu hỏi '{question}' như sau: [Câu trả lời mẫu].",
            "retrieved_ids": retrieved_ids,
            "contexts": contexts,
            "metadata": {
                "model": "gpt-4o-mini",
                "tokens_used": 150,
                "sources": ["data/knowledge_base.json"]
            }
        }

if __name__ == "__main__":
    agent = MainAgent()
    async def test():
        resp = await agent.query("Làm thế nào để đổi mật khẩu?")
        print(resp)
    asyncio.run(test())
