# Reflection — Hồ Hải Thuận (Backend/Performance)

**Lab:** Day 14 — AI Evaluation Factory (Team Edition)  
**Vai trò:** Backend/Performance — Async Runner & Cost Tracker  
**Ngày:** 2026-04-21  

---

## 1. Đóng góp kỹ thuật cụ thể (Engineering Contribution)

### Module chính phụ trách:
- **`engine/runner.py`** — Xây dựng khung chạy benchmark bất đồng bộ bằng `asyncio` cho toàn pipeline.
- **`engine/performance_tracker.py`** — Xây dựng module tổng hợp hiệu năng, token usage và chi phí eval.

### Công việc đã thực hiện:
- Thiết kế `BenchmarkRunner` để chạy nhiều test case theo batch thay vì chạy tuần tự.
- Đảm bảo pipeline có thể mở rộng cho 50 cases và hướng tới mục tiêu dưới 2 phút theo yêu cầu đề bài.
- Theo dõi `latency` cho từng case để phục vụ benchmark và regression analysis.
- Chuẩn hóa phần thu thập `token usage` và `cost` để có thể tái sử dụng khi tích hợp vào `main.py`.
- Viết `PerformanceTracker` để tổng hợp:
  - `avg_score`
  - `hit_rate`
  - `mrr`
  - `agreement_rate`
  - `total_tokens`
  - `avg_tokens_per_case`
  - `total_cost_usd`
  - `avg_cost_usd`
  - `throughput_cases_per_sec`
  - trạng thái đạt hay không đạt mục tiêu runtime
- Tách phần backend/performance thành module riêng để Team Lead có thể import khi tích hợp mà không phải sửa sâu vào code của các thành viên khác.

### Ý nghĩa phần đóng góp:
- `runner.py` là xương sống của benchmark pipeline vì mọi test case đều phải đi qua lớp này.
- `performance_tracker.py` là đầu ra định lượng cho phần đánh giá chi phí và hiệu năng, giúp nhóm đạt tiêu chí Expert về async và cost reporting.

---

## 2. Kiến thức chuyên sâu (Technical Depth)

### 2.1. Async Runner trong hệ thống đánh giá AI

Trong hệ thống evaluation, nếu chạy từng test case một cách tuần tự thì tổng thời gian sẽ tăng rất nhanh khi số lượng case lớn.  
Vì vậy tôi sử dụng mô hình chạy theo batch với `asyncio.gather()` để cho phép nhiều case được xử lý đồng thời.

Lợi ích:
- Giảm tổng thời gian benchmark.
- Tận dụng tốt thời gian chờ I/O khi gọi agent hoặc judge.
- Dễ gắn thêm giới hạn song song (`batch_size`, `max_concurrency`) để cân bằng giữa tốc độ và rate limit.

Trade-off:
- Nếu concurrency quá lớn thì dễ gặp rate limit hoặc lỗi API.
- Nếu concurrency quá nhỏ thì không đạt mục tiêu hiệu năng của bài.

### 2.2. Token Usage và Cost Tracking

Một hệ thống eval tốt không chỉ cần chính xác mà còn phải biết “mỗi lần chạy tốn bao nhiêu tiền”.

Tôi triển khai theo hướng:
- thu thập tổng token của từng case
- tổng hợp token toàn batch
- tính cost theo mô hình `input/output pricing`
- báo cáo tổng cost và cost trung bình trên mỗi case

Điểm quan trọng là cost tracking phải tách được khỏi logic tích hợp để khi model hoặc pricing đổi, nhóm chỉ cần cập nhật ở module backend thay vì sửa cả pipeline.

### 2.3. Throughput và Runtime Target

Ngoài latency từng case, tôi còn theo dõi thêm:
- `aggregate_wall_time_sec`
- `estimated_serial_runtime_sec`
- `throughput_cases_per_sec`
- `met_runtime_target`

Các chỉ số này giúp trả lời 2 câu hỏi thực tế:
- Nếu chạy tuần tự thì hệ thống sẽ chậm đến mức nào?
- Sau khi async hóa thì hệ thống có đạt mục tiêu dưới 2 phút cho 50 cases hay không?

### 2.4. Trade-off giữa Chi phí và Chất lượng
Tôi rút ra rằng chi phí eval tăng theo 3 yếu tố:
- số lượng test cases
- số lượng model tham gia chấm
- số token trung bình trên mỗi case

Một chiến lược tối ưu hợp lý là:
- dùng model nhỏ cho case dễ hoặc case có retrieval/judge đồng thuận cao
- chỉ escalte sang model lớn khi câu hỏi dài, retrieval yếu, hoặc judge bất đồng mạnh

Chiến lược này có thể giảm khoảng 30% chi phí eval mà vẫn giữ được chất lượng ở các case quan trọng.

---

## 3. Cách giải quyết vấn đề (Problem Solving)

### Vấn đề 1: Pipeline benchmark dễ chậm khi số case tăng

**Triệu chứng:** Nếu chạy 50 case theo kiểu tuần tự, tổng thời gian có thể vượt xa mức yêu cầu.

**Giải pháp:**
- Dùng `asyncio.gather()` để xử lý nhiều case cùng lúc.
- Tổ chức chạy theo batch để kiểm soát số lượng tác vụ đồng thời.
- Thiết kế runner theo hướng độc lập với `main.py`, giúp có thể test riêng module backend.

**Kết quả:** Backend đã sẵn sàng cho benchmark song song và có thể bàn giao cho bước tích hợp tiếp theo.

### Vấn đề 2: Cần báo cáo cost nhưng không được phụ thuộc chặt vào file tích hợp

**Triệu chứng:** Nếu logic cost nằm trực tiếp trong `main.py` thì khi Team Lead đổi flow tích hợp sẽ rất dễ vỡ.

**Giải pháp:**
- Tách riêng `PerformanceTracker` thành module backend độc lập.
- Cho phép Team Lead chỉ cần import module này để build summary.
- Gom toàn bộ cost/runtime/throughput vào một nơi để dễ kiểm thử và bảo trì.

**Kết quả:** Phần cost tracking của tôi có thể bàn giao độc lập cho Tuấn mà không làm ảnh hưởng phần việc của các thành viên khác.


## 4. Bài học rút ra

1. **Async không chỉ là tăng tốc**: Async chỉ thật sự có giá trị khi đi kèm với thiết kế batch, kiểm soát concurrency và đo lường runtime rõ ràng.

2. **Đo lường là một phần của sản phẩm**: Nếu không có cost report và performance report thì rất khó chứng minh hệ thống evaluation đủ tốt cho môi trường thực tế.

3. **Tách module giúp teamwork dễ hơn**: Khi runner và performance tracker được tách riêng, Team Lead có thể tích hợp dễ hơn và giảm nguy cơ conflict với phần việc của người khác.

4. **Chi phí eval là bài toán kỹ thuật thật sự**: Không thể chỉ tối ưu chất lượng mà bỏ qua chi phí, vì khi số case tăng thì tổng cost sẽ tăng rất nhanh.

5. **Ownership rõ ràng giúp làm việc nhóm hiệu quả**: Với vai trò backend/performance, tôi ưu tiên hoàn thành phần khung chạy và đo lường trước để các thành viên khác có thể cắm logic của họ vào sau.
