from pydantic import BaseModel, Field
from typing import List

class GoldenCase(BaseModel):
    question_id: str = Field(..., description="ID duy nhất cho mỗi câu hỏi")
    question: str = Field(..., description="Nội dung câu hỏi kiểm thử")
    ground_truth_answer: str = Field(..., description="Câu trả lời đúng chuẩn (Reference)")
    ground_truth_context: str = Field(..., description="Đoạn văn bản gốc dùng để trả lời")
    ground_truth_chunk_ids: List[str] = Field(default_factory=list, description="Danh sách các ID của chunk chứa câu trả lời")
    question_type: str = Field(..., description="Loại câu hỏi: factual, reasoning, hoặc red_teaming")
    complexity: str = Field(default="simple", description="Độ khó: simple, medium, hard")

class GoldenDataset(BaseModel):
    items: List[GoldenCase]