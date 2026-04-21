# BÁO CÁO CÁ NHÂN (REFLECTION) - AI ENGINEER

**Họ và tên:** Lâm Hoàng Hải
**Mã sinh viên:** 2A202600090
**Ngày nộp:** 21/04/2026
**Vai trò:** AI Engineer (Multi-Judge Consensus Engine)

## 1. Engineering Contribution (Đóng góp kỹ thuật)

Trong dự án này, tôi tập trung hoàn toàn vào việc xây dựng module đánh giá cốt lõi:

- **Module Multi-Judge (`engine/llm_judge.py`)**: Thiết kế và triển khai class `LLMJudge` hỗ trợ đa model. Tôi đã tích hợp thành công **GPT-4o (OpenAI)** và **Gemini 2.5 Flash (Google AI Studio)** để tạo ra cơ chế đồng thuận (consensus), loại bỏ sự thiên kiến của một model duy nhất.
- **Triển khai Pairwise Logic**: Xây dựng logic gọi 2 model song song để so sánh cặp giữa câu trả lời của Agent và Ground Truth, giúp benchmark có tính định lượng rõ ràng thay vì chỉ chấm điểm cảm tính.
- **Minh chứng:** <https://github.com/dungnguyen1806/C401-E6-Lab14/pull/2>

## 2. Technical Depth (Chiều sâu kỹ thuật)

- **Position Bias**: Là hiện tượng mô hình ngôn ngữ (LLM) có xu hướng ưu tiên lựa chọn một câu trả lời dựa trên vị trí hiển thị của nó (thường là vị trí đầu tiên - Vị trí A) thay vì dựa trên nội dung thực tế.
- **MRR (Mean Reciprocal Rank)**: Là một độ đo trong lĩnh vực tìm kiếm thông tin, được tính bằng giá trị trung bình của các nghịch đảo thứ hạng của kết quả đúng đầu tiên được tìm thấy trong danh sách kết quả.
- **Cohen's Kappa**: Là một hệ số thống kê được sử dụng để đo lường mức độ đồng thuận giữa hai người đánh giá (raters) đối với cùng một tập dữ liệu, có tính đến khả năng sự đồng thuận xảy ra do ngẫu nhiên.
- **Trade-off Chi phí và Chất lượng**: Là quá trình cân nhắc và đưa ra quyết định giữa việc sử dụng các mô hình LLM tiên tiến (như GPT-4o) để đạt được độ chính xác cao nhất và việc sử dụng các mô hình nhỏ hơn để tối ưu hóa ngân sách vận hành.
- **Chain of Thought (CoT)**: Là kỹ thuật thúc đẩy mô hình ngôn ngữ thực hiện các bước suy luận trung gian trước khi đưa ra câu trả lời cuối cùng, giúp cải thiện khả năng giải quyết các vấn đề phức tạp.

### Ứng dụng thực tế trong dự án

- **Xử lý Position Bias**: Tôi đã trực tiếp lập trình logic chạy đánh giá 2 lần (Run 1: Agent-Reference, Run 2: Reference-Agent) để triệt tiêu sự thiên kiến vị trí của Judge.
- **Vận dụng CoT**: Trong cấu trúc prompt gửi cho GPT-4o và Gemini, tôi đã thiết lập yêu cầu `chain_of_thought` để các model bắt buộc phải giải trình trước khi chấm điểm.
- **Thực hiện Trade-off**: Tôi đã cấu hình hệ thống sử dụng đồng thời cả model cao cấp (GPT-4o) và model có chi phí tối ưu hơn (Gemini 2.5 Flash) để cân bằng giữa độ chính xác và chi phí vận hành benchmark.

## 3. Problem Solving (Giải quyết vấn đề)

- **Consistency with Business Rubrics**: Dựa trên yêu cầu từ dự án, tôi đã tinh chỉnh hệ thống Prompt để Judge bám sát bộ Rubric 3 mức độ (Điểm 1 - Mâu thuẫn, Điểm 3 - Thiếu ràng buộc, Điểm 5 - Hoàn hảo). Việc này giải quyết vấn đề LLM thường chấm điểm quá nới tay hoặc không bám sát ngữ cảnh tài liệu.

---
**Kết luận:** Module Multi-Judge đã hoàn thiện, cung cấp bộ chỉ số chất lượng Agent tin cậy cho cả nhóm.
