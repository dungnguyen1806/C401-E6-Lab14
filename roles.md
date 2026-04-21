### 📋 PHÂN CÔNG CÔNG VIỆC CHI TIẾT (7 THÀNH VIÊN)

#### 👥 Nhóm 1: Data & Retrieval (Giai đoạn 1)
**1. Dũng - Data Engineer (SDG & Golden Dataset)**
*   **Nhiệm vụ:** Viết script `data/synthetic_gen.py` tạo ra 50+ test cases. Bắt buộc phải sinh ra/lưu lại `Ground Truth IDs` (ID của đoạn văn bản/chunk chứa câu trả lời đúng).
*   **Chú ý:** File output phải là `data/golden_set.jsonl`. KHÔNG commit file này lên git, chỉ commit script tạo ra nó.
*   **Đầu ra:** Dữ liệu chuẩn cho cả team dùng.

**2. Huy - Retrieval Analyst (Hit Rate, MRR & Red Teaming)**
*   **Nhiệm vụ:** 
    * Viết hàm tính toán **Hit Rate** và **MRR** cho Vector DB.
    * Tạo một bộ dataset nhỏ "Red Teaming" (câu hỏi lắt léo, jailbreak, prompt injection) gộp chung vào bộ của Dũng để thử thách hệ thống.
*   **Chú ý:** Phải giải thích được bằng comment/markdown: *"Tại sao điểm Retrieval thấp lại dẫn đến Answer Quality thấp?"*. Đây là tiêu chí ăn điểm Expert (15%).

#### 👥 Nhóm 2: Core Engine (Giai đoạn 2)
**3. Hải - AI Engineer (Multi-Judge Consensus)**
*   **Nhiệm vụ:** Code class/hàm gọi ít nhất 2 model LLM làm Giám khảo (Ví dụ: GPT-4o-mini và Claude-3-haiku). Viết logic tính toán độ đồng thuận (Agreement Rate) và xử lý xung đột (VD: Nếu chênh lệch > 2 điểm thì prompt lại hoặc chia trung bình).
*   **Chú ý:** Tuyệt đối không dùng 1 model Judge. Output của phần này quyết định 20% điểm.

**4. Thuận - Backend/Performance (Async Runner & Cost Tracker)**
*   **Nhiệm vụ:** Bọc toàn bộ pipeline bằng `asyncio`. Đảm bảo hệ thống chạy 50 cases dưới 2 phút. Tính toán Token usage và $ Cost cho mỗi lần chạy Eval.
*   **Chú ý:** Báo cáo chi tiết Cost. Viết một đoạn ngắn đề xuất "Cách giảm 30% chi phí Eval mà không giảm chất lượng" (Ví dụ: dùng model nhỏ cho câu hỏi dễ, model to cho câu khó).

#### 👥 Nhóm 3: Testing & Analysis (Giai đoạn 3)
**5. Quang - DevOps (Regression Testing & Release Gate)**
*   **Nhiệm vụ:** Code logic so sánh V1 vs V2 (Agent cũ vs Agent mới). Viết hàm `Release Gate` (VD: `if MRR_v2 > MRR_v1 AND Cost_v2 < Threshold => Auto Approve`).
*   **Chú ý:** In ra terminal dòng chữ xanh/đỏ rõ ràng: 🟢 PASSED RELEASE GATE hoặc 🔴 ROLLBACK.

**6. Long - Data Analyst (Failure Analysis & 5 Whys)**
*   **Nhiệm vụ:** Phụ trách chính file `analysis/failure_analysis.md`. Gom nhóm các lỗi (Failure Clustering). Áp dụng phương pháp "5 Whys" để tìm ra Root Cause.
*   **Chú ý:** Không được viết chung chung "AI ngu". Phải chỉ đích danh: Lỗi do Ingestion? Do Chunking size quá nhỏ? Hay do Retrieval lấy sai Ground Truth?

#### 👥 Nhóm 4: Quản lý & Tích hợp (Giai đoạn 4)
**7. Tuấn - Team Lead / System Integrator**
*   **Nhiệm vụ:** 
    *   Tích hợp code của 6 người lại thành file `main.py` hoàn chỉnh.
    *   Tạo file `reports/summary.json` và `reports/benchmark_results.json`.
    *   Chạy script `python check_lab.py` để verify định dạng.
    *   Tinh chỉnh Prompt/Thông số của Agent (Tối ưu Agent) dựa trên phân tích của Long để điểm số V2 cao hơn V1.
*   **Chú ý:** Quản lý file `.env` (Đảm bảo đưa vào `.gitignore`), tránh lỗi thủ tục bị trừ 5 điểm. Hối thúc timeline.

---

### 🔗 SỰ PHỤ THUỘC LẪN NHAU (DEPENDENCY MAP)

Để tránh tình trạng "ngồi chờ nhau", các bạn cần làm việc theo luồng sau và mock (giả lập) data khi cần thiết:

*   **[Dũng]** là người khởi đầu. Dũng phải chốt Schema (cấu trúc JSON) của test case trong **30 phút đầu** và gửi cho cả team. Sau đó Dũng cứ làm script thật, còn team dùng file JSON mẫu (Mock data) của Dũng để code tiếp.
*   **[Huy]** phụ thuộc vào Ground Truth IDs của **[Dũng]**.
*   **[Hải]** và **[Thuận]** làm việc song song cực kỳ chặt chẽ. Thuận xây bộ khung Async, Hải nhét logic gọi API Multi-Judge vào khung của Thuận.
*   **[Quang]** phụ thuộc vào output metrics của **[Huy]** (Hit Rate/MRR) và **[Hải]** (Judge Score) để viết điều kiện Release Gate. (Có thể code sẵn logic if/else với data giả).
*   **[Long]** phụ thuộc vào việc hệ thống chạy ra lỗi. Trong lúc chờ Thuận và Hải code xong `main.py`, Long nên draft sẵn format cho báo cáo `failure_analysis.md` và viết sẵn lý thuyết 5 Whys.
*   **[Tuấn]** là nút thắt cuối cùng. Toàn bộ code phải merge về cho Tuấn trước **deadline 45 phút** để Tuấn chạy test, fix bug tích hợp và chạy `check_lab.py`.

---

### ⚠️ CHECKLIST CẢ NHÓM KHÔNG ĐƯỢC QUÊN
1. **(CÁ NHÂN):** CẢ 7 NGƯỜI đều phải tự tạo và điền file reflection cá nhân của mình tại `analysis/reflections/reflection_[Tên_SV].md`. Thiếu file của ai người đó mất điểm.
2. **(CHẠY TRƯỚC):** File `data/golden_set.jsonl` KHÔNG có sẵn. Lời nhắc trong README rất rõ: Git clone về xong phải chạy `python data/synthetic_gen.py` trước tiên.
3. **(BẢO MẬT):** Đứa nào push file `.env` chứa API Key lên GitHub là cả đám chịu hậu quả. Tuấn phải check kỹ `.gitignore`.
4. **(ĐỊNH DẠNG):** Không được sửa tên file, tên thư mục chuẩn mà đề bài yêu cầu.

*Gợi ý timeline cho 4 tiếng:*
*   **T+0h - T+0.5h:** Dũng & Huy chốt JSON Schema test case. Cả team setup repo.
*   **T+0.5h - T+2.0h:** Dũng & Huy hoàn thiện sinh Data. Hải & Thuận code xong Async + Eval logic. Quang setup xong Release gate.
*   **T+2.0h - T+2.5h:** Tuấn ghép code. Chạy `main.py` lần 1.
*   **T+2.5h - T+3.5h:** Có kết quả lần 1 -> Long làm 5 Whys. Tuấn sửa Agent (V2). Quang chạy so sánh V1 vs V2.
*   **T+3.5h - T+4.0h:** 7 người viết reflection cá nhân. Tuấn chạy `check_lab.py` và nộp bài.