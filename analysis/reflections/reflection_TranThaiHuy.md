# Reflection — Tran Thai Huy (Retrieval Analyst)

**Lab:** Day 14 — AI Evaluation Factory (Team Edition)  
**Vai trò:** Retrieval Analyst — Hit Rate, MRR & Red Teaming  
**Ngày:** 2026-04-21  

---

## 1. Đóng góp kỹ thuật cụ thể (Engineering Contribution)

### Module chính phụ trách
- **`engine/file_retriever.py`** — xây retriever chạy trực tiếp trên `data/knowledge_base.json` (không dùng VectorDB), trả về top-k `chunk_id`.
- **`engine/retrieval_eval.py`** — triển khai logic tính `Hit@K`, `MRR`, đánh giá theo từng case và tổng hợp batch.
- **`agent/main_agent.py`** — nối retrieval vào output của agent bằng trường `retrieved_ids` để benchmark có thể chấm Retrieval Quality.

### Công việc đã thực hiện
- Thiết kế retriever file-based bằng keyword overlap để xếp hạng các chunk trong KB theo mức liên quan với câu hỏi.
- Chuẩn hóa contract retrieval:
  - Ground truth: `ground_truth_chunk_ids` trong `data/golden_set.jsonl`.
  - Output hệ thống: `retrieved_ids` từ agent.
- Cài đặt evaluator cho retrieval:
  - `calculate_hit_rate(expected_ids, retrieved_ids, top_k=3)`
  - `calculate_mrr(expected_ids, retrieved_ids)`
  - `evaluate_case(...)` và `evaluate_batch(...)`.
- Xử lý edge case Out-of-Context bằng cơ chế `excluded_from_avg=True` để không làm sai lệch chỉ số retrieval trung bình.
- Mở rộng bộ red-team bằng cách bổ sung **10 câu adversarial** (từ `q_051` đến `q_060`), nâng tổng dataset lên **60 cases**.

### Kết quả đầu ra liên quan trực tiếp phần việc
- Phân phối dataset sau cập nhật:
  - `factual: 20`, `adversarial: 20`, `edge_case: 10`, `multi_turn: 10`.
- Báo cáo benchmark (`reports/summary.json`) có đầy đủ retrieval metrics:
  - `hit_rate = 0.891`
  - `mrr = 0.852`
  - `retrieval_details.included_cases = 55`
  - `retrieval_details.out_of_context_cases = 5`

---

## 2. Kiến thức chuyên sâu (Technical Depth)

### 2.1. Vì sao Retrieval Quality ảnh hưởng trực tiếp Answer Quality
Trong kiến trúc RAG, mô hình chỉ có thể trả lời tốt nếu context đầu vào đúng.  
Khi retrieval sai (hit thấp), LLM thiếu bằng chứng và dễ:
- trả lời sai sự kiện/số liệu,
- trả lời thiếu ý,
- hoặc hallucination do suy diễn ngoài tài liệu.

Ngược lại, khi retrieval đúng và được xếp hạng cao (MRR cao), model có khả năng bám sát tài liệu tốt hơn, làm tăng chất lượng câu trả lời và độ tin cậy khi chấm bởi Judge.

### 2.2. Ý nghĩa của Hit@K và MRR
- **Hit@K**: đo khả năng “lấy trúng” tài liệu đúng trong top-k.
- **MRR**: đo tài liệu đúng xuất hiện sớm hay muộn trong ranking.

Hai chỉ số kết hợp cho phép phân biệt:
- Retriever không tìm được tài liệu đúng (Hit thấp),
- hoặc tìm được nhưng xếp hạng chưa tốt (Hit ổn nhưng MRR thấp).

### 2.3. Lý do dùng file-based retriever
Nhóm không dùng VectorDB, nên tôi chọn retrieval trực tiếp trên JSON KB để:
- giữ kiến trúc đơn giản, dễ tái hiện trong lab,
- vẫn tạo được `retrieved_ids` phục vụ eval chuẩn,
- đảm bảo không chặn tiến độ của pipeline benchmark.

---

## 3. Cách giải quyết vấn đề (Problem Solving)

### Vấn đề 1: Không dùng VectorDB nhưng vẫn phải chấm Retrieval
**Triệu chứng:** Không có vector index để trả kết quả retrieval mặc định.  
**Giải pháp:** Xây `FileRetriever` đọc `knowledge_base.json`, rank chunk bằng keyword overlap, trả top-k `chunk_id`.  
**Kết quả:** Pipeline vẫn đo được Hit/MRR đúng yêu cầu rubric dù không dùng VectorDB.

### Vấn đề 2: Lệch schema giữa dataset và pipeline
**Triệu chứng:** Dataset dùng `ground_truth_chunk_ids`/`ground_truth_answer`, trong khi một số chỗ pipeline dùng tên cũ.  
**Giải pháp:** Chuẩn hóa theo schema mới ở phần retrieval và đảm bảo runner lấy ground truth theo field hiện tại.  
**Kết quả:** Dữ liệu đi qua benchmark ổn định, report xuất được retrieval metrics.

### Vấn đề 3: Khó nhận diện red-team trong dataset
**Triệu chứng:** Red-team đã có nhưng khó nhìn nhanh số lượng và phạm vi.  
**Giải pháp:** Dựa theo `question_type="adversarial"` để lọc/đếm và bổ sung thêm 10 câu adversarial có nhãn rõ.  
**Kết quả:** Bộ test hiện có 20 câu adversarial, tăng độ bao phủ kiểm thử hành vi tấn công/prompt injection.

---

## 4. Bài học rút ra

1. **Retrieval phải được đo độc lập trước generation**: nếu không sẽ rất khó xác định root cause khi chất lượng câu trả lời giảm.
2. **Schema ổn định quyết định tốc độ teamwork**: chỉ cần lệch tên field là pipeline eval dễ vỡ.
3. **Không cần công nghệ phức tạp mới làm được eval đúng**: với lab này, file-based retriever vẫn đủ để đo Hit/MRR minh bạch.
4. **Red-team data giúp lộ điểm yếu thật**: thêm adversarial cases làm rõ giới hạn an toàn của agent trong benchmark.
5. **Số liệu quan trọng hơn cảm giác**: các chỉ số `hit_rate`, `mrr`, `pass_rate` giúp nhóm ra quyết định cải tiến có cơ sở hơn.
