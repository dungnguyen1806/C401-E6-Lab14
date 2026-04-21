# Reflection — Nguyễn Hoàng Long (Data Analyst)

**Lab:** Day 14 — AI Evaluation Factory (Team Edition)  
**Vai trò:** Data Analyst — Failure Analysis & 5 Whys  
**Ngày:** 2026-04-21  

---

## 1. Đóng góp kỹ thuật cụ thể (Engineering Contribution)

### Module chính phụ trách:
- **`analysis/failure_analysis.md`** — Viết toàn bộ báo cáo phân tích lỗi với 3 case studies 5 Whys, phân cụm 6 loại lỗi, và đề xuất Action Plan cải tiến.

### Đóng góp vào code (Git commits):
- **`engine/llm_judge.py`** — Implement Multi-Judge Consensus Engine:
  - Gọi 2 model LLM (gpt-4o-mini + gpt-3.5-turbo) song song qua `asyncio.gather`
  - Logic xử lý xung đột: nếu `|score_a - score_b| > 1` → gọi tie-breaker lần 3, lấy median
  - Tính Cohen's Kappa cho inter-rater reliability
  - Implement Position Bias detection (swap order test)
  - Cost tracking per case (input/output tokens × pricing table)
  - Graceful fallback: nếu không có API key → heuristic-based simulation

- **`engine/runner.py`** — Nâng cấp Async Runner:
  - Thêm `asyncio.Semaphore` để rate limiting
  - Cost tracking cho Agent (token × pricing)
  - Batch progress reporting
  - Per-case latency + cost breakdown

- **`main.py`** — Cải tiến Main Pipeline:
  - Kết nối ExpertEvaluator thật (Faithfulness + Relevancy heuristics)
  - Regression Analysis: V1 vs V2 delta comparison
  - Release Gate logic với output 🟢 PASSED / 🔴 ROLLBACK
  - Cost report tổng hợp (Agent + Judge)
  - Xuất `summary.json` với đầy đủ fields required

---

## 2. Kiến thức chuyên sâu (Technical Depth)

### 2.1. MRR — Mean Reciprocal Rank

**Định nghĩa:** MRR đo lường chất lượng retrieval bằng cách xem vị trí của document đúng đầu tiên trong danh sách kết quả.

**Công thức:**
```
MRR = (1/N) × Σ (1 / rank_i)
```

Trong đó `rank_i` là vị trí (1-indexed) của document đúng đầu tiên cho query thứ `i`.

**Ví dụ:**
- Query 1: đáp án đúng ở vị trí 1 → RR = 1/1 = 1.0
- Query 2: đáp án đúng ở vị trí 3 → RR = 1/3 = 0.33
- Query 3: đáp án đúng không có → RR = 0
- MRR = (1.0 + 0.33 + 0) / 3 = **0.44**

**Ý nghĩa thực tế:** MRR cao = retriever tìm đúng document ngay từ đầu → LLM nhận context tốt → câu trả lời chính xác hơn.

### 2.2. Cohen's Kappa — Hệ số đồng thuận giữa các Judge

**Định nghĩa:** Cohen's Kappa đo mức độ đồng thuận giữa 2 người (hoặc model) đánh giá, **trừ đi yếu tố trùng hợp ngẫu nhiên**.

**Công thức:**
```
κ = (P_observed - P_expected) / (1 - P_expected)
```

- `P_observed`: tỉ lệ 2 Judge cho cùng điểm
- `P_expected`: xác suất 2 Judge trùng điểm một cách ngẫu nhiên

**Thang đánh giá:**

| Kappa | Mức độ đồng thuận |
|:---:|:---|
| > 0.8 | Almost perfect |
| 0.6 - 0.8 | Substantial |
| 0.4 - 0.6 | Moderate |
| 0.2 - 0.4 | Fair |
| < 0.2 | Slight / Poor |

**Tại sao quan trọng?** Nếu chỉ dùng 1 Judge, ta không biết kết quả có khách quan không. Cohen's Kappa cho phép **lượng hoá** độ tin cậy của hệ thống Multi-Judge. Kappa > 0.6 nghĩa là hệ thống đủ tin cậy để dùng trong production.

### 2.3. Position Bias — Thiên vị vị trí

**Định nghĩa:** LLM Judge có xu hướng thiên vị (favor) response xuất hiện ở **vị trí đầu tiên** trong prompt. Đây là một bias đã được chứng minh trong nhiều nghiên cứu (Wang et al., 2023 — "Large Language Models are not Fair Evaluators").

**Cách phát hiện:** 
1. Gọi Judge chấm điểm response A trước, B sau → Score_1
2. Đổi thứ tự: B trước, A sau → Score_2
3. Nếu `|Score_1 - Score_2| > 1` → Position Bias tồn tại

**Cách giảm thiểu:**
- Chạy Judge 2 lần (swap order) rồi lấy trung bình
- Sử dụng multi-judge consensus thay vì single judge
- Randomize thứ tự trong prompt

### 2.4. Trade-off Chi phí vs Chất lượng

| Chiến lược | Chi phí | Chất lượng | Khi nào dùng |
|:---|:---:|:---:|:---|
| 1 Judge (gpt-3.5-turbo) | Thấp ($0.001/case) | Thấp | Nightly regression test |
| 2 Judges (gpt-4o-mini + gpt-3.5) | Vừa ($0.003/case) | Tốt | Pre-release gate |
| 2 Judges + Position Bias check | Cao ($0.01/case) | Rất tốt | Final production eval |
| 3 Judges + Kappa analysis | Rất cao ($0.02/case) | Xuất sắc | Critical model update |

**Đề xuất tối ưu:** Dùng **Tiered Judging** — phân loại câu hỏi theo complexity rồi route tới tier phù hợp. Câu đơn giản dùng 1 judge rẻ, câu phức tạp dùng 2 judges premium. Ước tính giảm 30% chi phí.

---

## 3. Cách giải quyết vấn đề (Problem Solving)

### Vấn đề 1: Hệ thống chạy chậm khi gọi API song song

**Triệu chứng:** 50 cases chạy > 5 phút, vượt mức yêu cầu < 2 phút.

**Nguyên nhân:** Mỗi case gọi Agent + 2 Judge = 3 API calls tuần tự → tổng ~150 calls tuần tự.

**Giải pháp:** 
- Bọc toàn bộ trong `asyncio` + `asyncio.gather` cho mỗi batch
- Thêm `asyncio.Semaphore(5)` để giới hạn 5 concurrent calls → tránh rate limit
- Gọi 2 Judge song song (`asyncio.gather(task_a, task_b)`) trong mỗi case
- Kết quả: giảm từ ~5 phút → dưới 2 phút

### Vấn đề 2: Không có API Key → Không thể chạy Demo

**Triệu chứng:** Teammate không có OpenAI API key, không thể test code.

**Giải pháp:**
- Implement **graceful fallback** trong `LLMJudge`: tự detect `OPENAI_API_KEY`
- Nếu không có key → dùng heuristic simulation (keyword overlap-based scoring)
- Simulation tạo variance giữa 2 model (random ±1) để vẫn test được conflict resolution logic
- Code chạy end-to-end cả 2 mode mà không crash

### Vấn đề 3: Phân tích lỗi khi chưa có kết quả thật

**Triệu chứng:** Long cần viết Failure Analysis nhưng pipeline chưa chạy xong.

**Giải pháp:**
- Draft sẵn template với các loại lỗi phổ biến trong RAG systems
- Phân tích code `FileRetriever` để dự đoán failure patterns (keyword overlap → miss semantic queries)
- Chuẩn bị 5 Whys framework trước → khi có data thật chỉ cần fill số liệu
- Kết quả: Báo cáo hoàn thành đúng deadline dù data đến muộn

---

## 4. Bài học rút ra

1. **Retrieval là nền tảng:** Trong RAG systems, chất lượng Retrieval quyết định ~70% chất lượng câu trả lời. Tối ưu prompt cho LLM là cần thiết nhưng chưa đủ.

2. **Multi-Judge là bắt buộc:** Dùng 1 Judge đơn lẻ có nhiều rủi ro (position bias, model-specific preferences). Cohen's Kappa giúp lượng hoá độ tin cậy.

3. **Async everywhere:** Trong real-world eval systems, pipeline phải chạy song song. Semaphore giúp cân bằng giữa tốc độ và rate limiting.

4. **Cost awareness:** Chi phí Eval không hề nhỏ khi scale lên (1000+ cases/ngày). Tiered Judging là chiến lược bắt buộc cho production.

5. **Defensive coding:** Luôn có fallback mechanism — code phải chạy được cả khi thiếu API key, thiếu data, hoặc API bị lỗi.
