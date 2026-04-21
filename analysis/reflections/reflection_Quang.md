# Reflection — Quách Ngọc Quang (DevOps Engineer)

**Lab:** Day 14 — AI Evaluation Factory (Team Edition)  
**Vai trò:** DevOps Engineer — Regression Testing & Release Gate  
**Ngày:** 2026-04-21  

---

## 1. Đóng góp kỹ thuật cụ thể (Engineering Contribution)

### Module chính phụ trách:
- **`engine/release_gate.py`** — Thiết kế và xây dựng bộ khung điều phối (Coordinator) để so sánh hiệu năng giữa phiên bản V1 (Base) và V2 (Optimized).

### Đóng góp vào code (Git commits):
- **`engine/release_gate.py`** — Triển khai logic quyết định tự động:
  - Phát triển class `ReleaseGate` với khả năng tùy chỉnh ngưỡng (Thresholds) linh hoạt.
  - Implement logic đa chỉ số: Không chỉ dựa vào Score mà còn kiểm soát cả Pass Rate, Hit Rate và Cost.
  - Xây dựng hệ thống báo cáo Terminal chuyên nghiệp, sử dụng mã màu ANSI để phân biệt trạng thái `APPROVE` và `ROLLBACK`.

- **`main.py`** — Tích hợp hệ thống và Fix lỗi tương thích:
  - Đồng bộ hóa dữ liệu từ `LLMJudge` và `PerformanceTracker` để nạp vào luồng Regression Analysis.
  - Giải quyết NameError và quản lý vòng đời (lifecycle) của các API Client để tránh lỗi loop.
  - Chuẩn hóa Unicode cho toàn bộ các thông báo in ra terminal để chạy mượt mà trên Windows console.

- **`reports/summary.json`** — Cấu trúc hóa output:
  - Đảm bảo kết quả phân tích hồi quy được nhúng trực tiếp vào báo cáo tổng hợp để phục vụ CI/CD.

---

## 2. Kiến thức chuyên sâu (Technical Depth)

### 2.1. Regression Testing trong AI

**Định nghĩa:** Khác với phần mềm truyền thống, kiểm tra hồi quy trong AI tập trung vào việc đảm bảo các thay đổi (prompting, model update) không làm sụt giảm chất lượng câu trả lời hoặc tăng chi phí bất thường.

**Tầm quan trọng:** Trong dự án này, nếu chất lượng giảm dù chỉ 0.01 điểm hoặc độ tin cậy của Judge thấp (Kappa < 0.2), hệ thống sẽ tự động kích hoạt chế độ **Rollback** để bảo vệ trải nghiệm người dùng cuối.

### 2.2. Cơ chế Release Gate đa chỉ số (Multi-metric)

Thay vì chỉ nhìn vào `avg_score`, tôi đã triển khai bộ quy tắc logic:
- **Quality Gate:** `v2_score >= v1_score` (Đảm bảo không tụt hậu chất lượng).
- **Reliability Gate:** `Cohen's Kappa > 0.4` (Đảm bảo kết quả đánh giá là đáng tin cậy).
- **Cost Gate:** `cost_v2 < 1.3 * cost_v1` (Kiểm soát lạm phát chi phí vận hành).
- **Success Gate:** `pass_rate_v2 >= pass_rate_v1` (Đảm bảo tính ổn định của hệ thống).

### 2.3. Tối ưu hóa chi phí với Gemini 2.5 Flash

Việc tích hợp mô hình Gemini 2.5 Flash vào hệ thống đánh giá cho thấy sức mạnh của DevOps trong việc tối ưu hóa tài nguyên:
- Giảm chi phí đánh giá từ mức Dollar xuống mức Cent (~$0.01 cho 100 cases).
- Tốc độ xử lý tăng cao nhờ đặc tính của mô hình Flash, cho phép chạy regression test nhanh hơn trong quy trình nộp bài.

---

## 3. Cách giải quyết vấn đề (Problem Solving)

### Vấn đề 1: Lỗi Unicode/Encoding trên terminal Windows

**Triệu chứng:** Khi chạy `python main.py`, terminal báo lỗi `UnicodeEncodeError` và dừng chương trình do chứa các ký tự emoji đặc biệt.

**Giải pháp:** 
- Tiến hành rà soát toàn bộ các câu lệnh `print` trong hệ thống.
- Chuyển đổi các biểu tượng cảm xúc (🚀, 📊) sang ký tự ASCII an toàn ( `[*]`, `[OK]` ).
- Cấu trúc lại cách format chuỗi để đảm bảo mã màu ANSI vẫn hiển thị đẹp nhưng không gây crash.

### Vấn đề 2: Xung đột cấu trúc dữ liệu khi ghép code (Merge Conflict)

**Triệu chứng:** Khi thực hiện `git pull`, file `llm_judge.py` bị xung đột và làm hỏng `get_total_cost_report`.

**Giải pháp:**
- Phân tích mã nguồn mới của đồng nghiệp (Hải) để hiểu kiến trúc Gemini 2.5 mới.
- Khéo léo khôi phục các phương thức `aclose()` và `get_total_cost_report()` đã mất.
- Chuẩn hóa lại các key dữ liệu (`agreement_rate`, `consensus_reached`) để code của Hải và Quang có thể hiểu nhau mà không cần sửa đổi quá nhiều.

---

## 4. Bài học rút ra

1. **Data-Driven Deployment:** Mọi quyết định triển khai Agent phải dựa trên dữ liệu định lượng, không dựa trên cảm tính.
2. **Clean Shutdown là cực kỳ quan trọng:** Việc quên đóng các API Client (httpx) có thể gây ra lỗi loop nghiêm trọng trong Python Async, ảnh hưởng đến độ ổn định của pipeline.
3. **Kỹ năng phối hợp (Collaboration):** Trong một team AI, DevOps đóng vai trò là "keo dán" kết nối dữ liệu từ Analyst sang Engineer và đưa nó ra báo cáo cuối cùng.
4. **Windows Compatibility:** Luôn phải cân nhắc môi trường chạy code (Windows/Linux) ngay từ khi bắt đầu xây dựng hệ thống Eval.
