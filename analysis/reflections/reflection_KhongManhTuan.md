# Reflection — Khổng Mạnh Tuấn (Team Lead / System Integrator)

**Lab:** Day 14 — AI Evaluation Factory (Team Edition)  
**Vai trò:** Team Lead / System Integrator  
**Ngày:** 2026-04-21  

---

## 1. Đóng góp kỹ thuật cụ thể (Engineering Contribution)

### Module chính phụ trách:
- **`main.py`** — Tích hợp toàn bộ module từ 6 thành viên khác để tạo pipeline hoàn chỉnh.
- **`agent/main_agent.py`** — Thực hiện nâng cấp từ Mock Agent sang RAG Agent thực tế và tối ưu hóa phiên bản V2.
- **`engine/llm_judge.py`** — Tinh chỉnh logic Multi-Judge và xử lý Rate Limit.

### Công việc đã thực hiện:
- **Tích hợp hệ thống:** Kết nối `BenchmarkRunner` (Thuận), `RetrievalEvaluator` (Huy/Dũng), `LLMJudge` (Hải), và `ReleaseGate` (Quang) vào flow `main.py`.
- **Tối ưu hóa Agent (V1 vs V2):**
  - Chuyển đổi Agent từ trả lời "mock" sang sử dụng `AsyncOpenAI`.
  - Triển khai chiến lược cho V2: Sử dụng System Prompt nghiêm ngặt ("Strict Prompting") để yêu cầu Agent chỉ trả lời dựa trên context, giúp giảm thiểu hallucination đáng kể.
- **Quản lý Judge (Gemini & OpenAI):** 
  - Chuyển đổi cặp Judge sang **Gemini 2.5 Flash** (Primary) và **GPT-4o** (Secondary) theo yêu cầu nâng cao.
  - Xử lý vấn đề Rate Limit (5 RPM) của Gemini Free Tier bằng cách triển khai cơ chế **Retries with Exponential Backoff** trong Judge và tích hợp **Batch Delay** trong Runner.
- **Kiểm định & Đóng gói:**
  - Chạy `python check_lab.py` để verify định dạng bài nộp.
  - Quản lý `.env` và `.gitignore` để bảo mật API Key của cả nhóm.

### Ý nghĩa phần đóng góp:
- Đảm bảo code của các thành viên không bị xung đột khi gộp lại.
- Giải quyết bài toán thực tế về Rate Limit khi sử dụng các model đời mới (Gemini-era) trong pipeline evaluation.
- Kết quả benchmark chứng minh được giá trị của việc tối ưu Agent (V2 cải thiện độ tin cậy so với V1).

---

## 2. Kiến thức chuyên sâu (Technical Depth)

### 2.1. System Integration trong AI Pipeline
Tích hợp không chỉ là copy-paste code. Thử thách lớn nhất là sự bất đồng bộ giữa các module. Ví dụ: `RetrievalEvaluator` cần IDs từ Agent, trong khi `ReleaseGate` lại cần summary metrics từ Runner. Tôi đã phải chuẩn hóa cấu trúc JSON đầu ra của Agent để đảm bảo toàn bộ pipeline downstream đều nhận được dữ liệu đúng format.

### 2.2. Chiến lược "Strict Prompting" vs "Thresholding"
Ban đầu tôi định dùng threshold cứng (overlap ratio < 0.2) để lọc context cho V2. Tuy nhiên, qua benchmark, tôi nhận thấy Keyword Retriever (`FileRetriever`) có Hit Rate cao nhưng đôi khi overlap ratio thấp do sự khác biệt về từ vựng. 
Tôi đã thay đổi chiến lược: Bỏ threshold cứng và chuyển sang sử dụng **Strict System Prompt**. Kết quả là Agent vẫn có đủ dữ liệu để trả lời nhưng không còn "tự ý bịa đặt" khi context không liên quan.

### 2.3. Vượt qua Rate Limit (Resource Exhaustion)
Khi sử dụng Gemini 2.5 Flash (Free Tier) với giới hạn 5 RPM, việc chạy benchmark 60 cases song song là bất khả thi. Tôi đã giải quyết bằng cách:
1. Giảm `max_concurrent` xuống 2.
2. Thêm `asyncio.sleep(20)` sau mỗi batch (Batch Delay).
3. Triển khai `max_retries=3` trong lớp Judge.
Đây là bài học quan trọng về việc điều phối (Orchestration) trong môi trường tài nguyên hạn chế.

---

## 3. Cách giải quyết vấn đề (Problem Solving)

### Vấn đề 1: Regression Analysis cho thấy V2 tệ hơn V1 ở lần chạy đầu
**Triệu chứng:** Điểm Judge của V2 sụt giảm (~3.0 so với 3.8 của V1) mặc dù logic có vẻ tốt hơn.
**Nguyên nhân:** Ngưỡng lọc context (Threshold 0.2) quá cao khiến V2 vứt bỏ cả những context đúng do keyword overlap thấp.
**Giải pháp:** Loại bỏ threshold cứng, tin tưởng vào khả năng phân loại của LLM thông qua Prompting.
**Kết quả:** Điểm số và độ tin cậy của V2 đã được cải thiện rõ rệt.

### Vấn đề 2: Lỗi API 429 khi dùng Judge mới
**Triệu chứng:** Pipeline bị crash hoặc trả về kết quả Fallback (score 3) khi gọi Gemini.
**Giải pháp:** Viết wrapper cho `chat.completions.create` với logic retry. Tăng batch delay trong runner để giãn cách các request.
**Kết quả:** Pipeline chạy ổn định và đạt kết quả đánh giá trung thực từ model cao cấp.

---

## 4. Bài học rút ra

1. **Team Lead là người gác cổng cuối cùng**: Phải hiểu sâu code của tất cả các thành viên để khi tích hợp gặp lỗi (như syntax error hay lỗi logic metric) có thể fix ngay lập tức.
2. **Prompt Engineering là công cụ mạnh mẽ hơn logic cứng**: Trong RAG, việc dạy LLM cách từ chối thông tin thông qua System Prompt mang lại hiệu quả cao hơn và linh hoạt hơn việc viết các hàm lọc heuristic.
3. **Quản trị rủi ro API**: Luôn phải dự phòng phương án Rate Limit và Fallback khi làm việc với các model LLM lớn.
4. **Validation là bắt buộc**: Việc chạy `check_lab.py` giúp phát hiện những lỗi ngớ ngẩn (như thiếu file summary) trước khi nộp, đảm bảo công sức của cả nhóm không bị mất điểm oan.
