# Reflection — Nguyen Manh Dung (Data Engineer)

**Lab:** Day 14 — AI Evaluation Factory (Team Edition)  
**Vai trò:** Data Engineer — SDG & Golden Dataset  
**Ngày:** 2026-04-21  

---

## 1. Đóng góp kỹ thuật cụ thể (Engineering Contribution)

### Module chính phụ trách
- **`data/knowledge_base_gen.py`** — xây dựng script chuyển đổi `raw_data.txt` thành 17 chunks trong `knowledge_base.json` bằng `RecursiveCharacterTextSplitter`.
- **`data/synthetic_gen.py`** — triển khai Synthetic Data Generation (SDG) sử dụng GPT-4o để sinh 50+ test cases đa dạng (factual, adversarial, edge_case, multi_turn).
- **`data/schema.py`** — thiết kế Pydantic model để chuẩn hóa cấu trúc Golden Dataset, đảm bảo tính nhất quán dữ liệu cho toàn team.

### Công việc đã thực hiện
- Xây dựng quy trình Ingestion: Chunking dữ liệu từ sổ tay nhân sự FutureIT, gán ID duy nhất (`chunk_id`) để phục vụ đo lường Retrieval.
- Thiết kế hệ thống Prompt cho SDG:
  - Phân bổ tỉ lệ câu hỏi: 40% Factual, 20% Adversarial, 20% Edge Case, 20% Multi-turn.
  - Tích hợp logic lọc ID (`valid_ids`) để ngăn chặn tình trạng LLM bịa đặt (Hallucination) các Ground Truth IDs không tồn tại.
- Cung cấp dữ liệu chuẩn (`data/golden_set.jsonl`) làm đầu vào cho toàn bộ pipeline benchmark (Agent -> Retrieval Eval -> LLM Judge).
- Xây dựng hướng dẫn `data/HARD_CASES_GUIDE.md` để định hướng cho team về các trường hợp tấn công (Prompt Injection, Goal Hijacking) và các trường hợp biên (Out-of-Context).

### Kết quả đầu ra liên quan trực tiếp phần việc
- Knowledge Base hoàn chỉnh với 17 chunks bao phủ toàn bộ nội dung sổ tay nhân sự và bảo mật.
- Bộ Golden Set chất lượng cao gồm 50 cases:
  - `factual: 20`, `adversarial: 10`, `edge_case: 10`, `multi_turn: 10`.
- Toàn bộ test cases đều có `ground_truth_chunk_ids` chính xác, giúp Retrieval Analyst (Huy) có thể tính toán Hit Rate và MRR ngay lập tức.

---

## 2. Kiến thức chuyên sâu (Technical Depth)

### 2.1. Tầm quan trọng của Golden Dataset trong RAG Evaluation
Trong hệ thống RAG, Golden Dataset đóng vai trò là "la bàn". Nếu dữ liệu mẫu (Ground Truth) không đủ độ khó hoặc không bao phủ hết các tình huống thực tế, các chỉ số như Accuracy hay Judge Score sẽ bị ảo (overfitting). Việc tạo ra các câu hỏi yêu cầu kết hợp thông tin từ nhiều chunks (Multi-hop) giúp đánh giá khả năng tổng hợp của Agent.

### 2.2. Chiến lược Synthetic Data Generation (SDG)
Sử dụng LLM mạnh (GPT-4o) để sinh data giúp tiết kiệm 90% thời gian so với gán nhãn thủ công. Tuy nhiên, thách thức lớn nhất là "ID Hallucination". Tôi đã giải quyết bằng cách:
- Cung cấp danh sách ID hợp lệ cho Prompt.
- Hậu kiểm (Post-processing) kết quả từ LLM để loại bỏ các ID rác trước khi lưu file.

### 2.3. Phân loại câu hỏi để đo lường toàn diện
- **Adversarial**: Kiểm tra tính an toàn (Safety) của Agent trước các đòn tấn công.
- **Edge Case**: Kiểm tra độ trung thực (Honesty) - Agent có biết nói "Tôi không biết" khi dữ liệu không có không?
- **Multi-turn**: Kiểm tra khả năng duy trì ngữ cảnh (Memory).

---

## 3. Cách giải quyết vấn đề (Problem Solving)

### Vấn đề 1: LLM bịa đặt ID chunk khi sinh Golden Set
**Triệu triệu:** Khi yêu cầu GPT-4o sinh `ground_truth_chunk_ids`, nó thường tạo ra các ID trông giống thật nhưng không có trong KB.  
**Giải pháp:** Thêm danh sách `valid_ids` vào Prompt và viết code kiểm tra chéo (Cross-check) kết quả JSON trả về. Chỉ giữ lại những ID thực sự tồn tại trong `knowledge_base.json`.  
**Kết quả:** Bộ dữ liệu 100% khớp với KB, không gây lỗi khi chạy Eval.

### Vấn đề 2: Dữ liệu thô (`raw_data.txt`) quá rời rạc
**Triệu chứng:** Nếu chunking quá nhỏ, câu hỏi sẽ bị mất ngữ cảnh; nếu quá lớn, Retrieval sẽ mất độ chính xác.  
**Giải pháp:** Sử dụng `RecursiveCharacterTextSplitter` với `chunk_size=500` và `overlap=50`, ưu tiên ngắt ở đoạn (`\n\n`) và dòng (`\n`).  
**Kết quả:** Các chunk giữ được ý nghĩa trọn vẹn của các điều khoản trong sổ tay.

### Vấn đề 3: Đảm bảo độ khó cho bài Lab (Hard Cases)
**Triệu chứng:** Các câu hỏi factual quá đơn giản không làm lộ được điểm yếu của Agent.  
**Giải pháp:** Dựa trên `HARD_CASES_GUIDE.md`, tôi ép LLM sinh ra các câu hỏi lắt léo (Ambiguous) hoặc yêu cầu kết hợp thông tin (VD: Vừa thuộc SOC vừa thuộc dự án S thì có được làm remote không?).  
**Kết quả:** Tỉ lệ Pass Rate của Agent V1 chỉ đạt ~70%, tạo không gian cho team cải tiến lên V2.

---

## 4. Bài học rút ra

1. **Rác vào thì Rác ra (GIGO)**: Chất lượng của Benchmark phụ thuộc 100% vào chất lượng của Golden Set.
2. **Post-processing là bắt buộc khi dùng SDG**: Không bao giờ tin tưởng hoàn toàn vào output JSON của LLM, luôn cần validation schema (Pydantic).
3. **Chunking ảnh hưởng đến Retrieval**: Việc chọn đúng kích thước chunk và độ chồng lấp (overlap) quyết định khả năng "Hit" của hệ thống.
4. **Teamwork bắt đầu từ Schema**: Việc tôi chốt Schema sớm giúp Huy và Hải có thể code evaluator mà không cần chờ dữ liệu thật.
5. **Diversity > Quantity**: Thà có 50 câu hỏi đa dạng các loại (adversarial, multi-turn) còn hơn 500 câu hỏi factual đơn giản.
