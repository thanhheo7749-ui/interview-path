# Kịch Bản Thuyết Trình: InterviewPath

**Thời lượng dự kiến:** 5 - 7 phút
**Phong cách:** Tự tin, thấu cảm, chuyên nghiệp.

## 🟢 SLIDE 1: TITLE (Mở màn)

*(Bạn bước ra giữa sân khấu, phong thái tự tin. Slide 1 đang hiện trên màn hình).*

**🗣️ Lời thoại:**
"Xin chào Ban giám khảo và quý vị khán giả.
Trong hội trường ngày hôm nay, đã bao nhiêu người từng cảm thấy tim đập thình thịch, toát mồ hôi hột trước một buổi phỏng vấn quan trọng với công ty nước ngoài?
Và ở chiều ngược lại, có anh chị nhân sự nào từng kiệt sức vì phải đọc hàng ngàn chiếc CV chỉ để tìm ra vài ứng viên phù hợp?
Hôm nay, đội chúng em mang đến giải pháp giải quyết trọn vẹn cả hai nỗi đau này. Xin giới thiệu:  **InterviewPath - Phễu lọc tự động cho Nhân sự và Lò luyện thực chiến cho Ứng viên.** "

## 🟢 SLIDE 2: THE PROBLEM (Nêu vấn đề)

*(Click nửa phải màn hình chuyển sang Slide 2)*

**🗣️ Lời thoại:**
"Trong quy trình tuyển dụng hiện tại, chúng ta đang đối mặt với một 'nút thắt cổ chai' khổng lồ ở cả hai phía.
**Với phía HR:** Đó là sự quá tải. Hàng ngàn CV đổ về mỗi ngày. HR phải tốn hàng tuần lễ chỉ để lọc thủ công, dẫn đến quy trình chậm chạp và dễ đánh rơi nhân tài.
**Với phía Ứng viên:** Đó là sự lo âu. Đặc biệt là các bạn trẻ Việt Nam khi ứng tuyển vào các tập đoàn đa quốc gia như Hàn Quốc hay Mỹ. Rất nhiều bạn trượt phỏng vấn không phải vì thiếu kỹ năng chuyên môn (coding), mà vì rào cản ngoại ngữ, kỹ năng giao tiếp thiếu cấu trúc, và hoàn toàn 'mù mờ' về văn hóa doanh nghiệp."

## 🟢 SLIDE 3: THE KEY INSIGHT (Điểm chạm)

*(Click nửa phải màn hình chuyển sang Slide 3 - Dừng lại 1 nhịp, nói chậm và nhấn mạnh)*

**🗣️ Lời thoại:**
"Từ thực trạng đó, chúng em nhận ra một sự thật cốt lõi - một Insight mà nhiều công cụ nhân sự hiện nay đang bỏ qua:
Khoảng trống thực sự trong tuyển dụng **không chỉ nằm ở sự chênh lệch kỹ năng (Skill mismatch).**
**Nó nằm ở sự thiếu chuẩn bị cho vòng phỏng vấn (Interview Readiness mismatch).**
Việc đánh rớt một kỹ sư giỏi chỉ vì họ không biết cách trình bày khiêm tốn theo chuẩn văn hóa Hàn Quốc, hay không biết dùng tiếng Anh chuyên ngành... là một sự lãng phí tài năng vô cùng lớn cho chính doanh nghiệp."

## 🟢 SLIDE 4: THE SOLUTION CONCEPTS (Giải pháp cơ bản)

*(Click nửa phải màn hình chuyển sang Slide 4)*

**🗣️ Lời thoại:**
"Để giải quyết triệt để bài toán này, InterviewPath sử dụng sức mạnh của AI, đóng vai trò như một  **Đội ngũ Nhân sự Số** . Chúng em dùng hai công nghệ lõi:
Thứ nhất, **n8n - Đóng vai trò như một người điều phối giao thông.** Thay vì con người phải làm thủ công các bước tải CV, đọc, và gửi email, n8n tự động hóa toàn bộ luồng công việc này chỉ trong vài giây.
Thứ hai, **RAG - Đóng vai trò như một 'Bộ não được mở sách'.** Khác với ChatGPT thường hay trả lời chung chung, chúng em nạp thẳng 'sổ tay văn hóa', yêu cầu kỹ thuật của công ty vào RAG. Nhờ đó, AI của chúng em chỉ hỏi và huấn luyện những thứ mà công ty các anh chị thực sự cần."

## 🟢 SLIDE 5: SYSTEM ARCHITECTURE (Bức tranh tổng quan)

*(Click nửa phải màn hình chuyển sang Slide 5 - Chỉ tay lướt nhẹ từ trái qua phải, không giải thích các thuật ngữ khó hiểu)*

**🗣️ Lời thoại:**
"Và đây là cách hệ thống vận hành.
Nhìn từ bên trái, InterviewPath nhận 3 đầu vào cốt lõi: **CV ứng viên, Mô tả công việc (JD), và Văn hóa công ty.**
Tất cả dữ liệu này được đẩy vào trung tâm điều phối là hệ thống tự động hóa n8n. Tại đây, n8n kết hợp với cơ sở dữ liệu và sức mạnh của AI (LLM) để phân tích, đưa ra quyết định, và rẽ nhánh thành 2 đầu ra hoàn toàn khác biệt:
Một là **Dashboard báo cáo** độ phù hợp dành cho HR.
Hai là một **Nền tảng luyện tập** thực chiến dành riêng cho Ứng viên."

## 🟢 SLIDE 6: N8N FLOWCHART (Quy trình HR)

*(Click nửa phải màn hình chuyển sang Slide 6)*

**🗣️ Lời thoại:**
"Với quy trình của HR, tốc độ là ưu tiên số một.
Khi ứng viên vừa nộp CV, AI lập tức bóc tách kỹ năng, đối chiếu với JD.
Nếu độ phù hợp thấp, hệ thống tự động gửi thư từ chối lịch sự.
Nhưng nếu độ phù hợp cao, ứng viên sẽ ngay lập tức nhận được một email chứa 'vé vàng' – một đường link bảo mật mời tham gia nền tảng luyện phỏng vấn nội bộ. Trải nghiệm tức thời này giúp doanh nghiệp giữ chân nhân tài ngay lập tức trước các đối thủ."

## 🟢 SLIDE 7: CANDIDATE EXPERIENCE (Trải nghiệm ứng viên)

*(Click nửa phải màn hình chuyển sang Slide 7 - Nói với giọng điệu truyền cảm hứng)*

**🗣️ Lời thoại:**
"Nhưng điều làm nên sự khác biệt của InterviewPath nằm ở trải nghiệm của Ứng viên. Chúng em gọi đây là chu trình  **'Polish & Shadow' (Mài giũa và Tạo phản xạ)** .
Ngay khi ứng viên bấm vào link, AI sẽ đọc chính các dự án cũ trong CV của họ để đặt câu hỏi tình huống.
Khi ứng viên trả lời bằng tiếng Anh bập bõm hoặc chưa trôi chảy, AI sẽ không đánh rớt họ ngay. Nó đóng vai một người Mentor (người hướng dẫn), sửa lại ngữ pháp, viết lại câu trả lời sao cho chuyên nghiệp và chuẩn văn hóa công ty nhất. Sau đó, nó yêu cầu ứng viên đọc nhại lại (Shadowing) để luyện cơ miệng và sự tự tin."

## 🟢 SLIDE 8: DEMO SCENARIO (Mô phỏng thực tế)

*(Click nửa phải màn hình chuyển sang Slide 8 - Đổi giọng hơi giống người dẫn truyện)*

**🗣️ Lời thoại:**
"Hãy nhìn vào một ví dụ thực tế. Đây là một ứng viên thực tập sinh Backend ứng tuyển vào công ty Hàn Quốc.
AI đưa ra tình huống: *"Hãy kể về một lần bạn chịu áp lực deadline."*
Ứng viên trả lời rất thật thà nhưng thiếu chuyên nghiệp: *"Em cố gắng hết sức và khi khó quá thì em đi hỏi đồng đội."*
Ngay lập tức, AI phản hồi: *"Câu trả lời của em dễ hiểu, nhưng quá chung chung. Hãy dùng cấu trúc STAR."* Và bùm! AI cung cấp một câu trả lời đã được 'Polish': *"Trong dự án Đại học, team em có 3 ngày để sửa lỗi API... Em đã kiểm tra logic, làm việc với frontend... Cuối cùng lỗi được khắc phục đúng hạn."*
Đó chính là sự lột xác mà InterviewPath mang lại."

## 🟢 SLIDE 9: EXPECTED IMPACT (Tác động kỳ vọng)

*(Click nửa phải màn hình chuyển sang Slide 9)*

**🗣️ Lời thoại:**
"Và với giải pháp này, tác động mang lại là một chiến thắng kép (Win-Win).
**Đối với bộ phận Nhân sự:** Chúng ta loại bỏ hoàn toàn thời gian lọc CV thủ công, chốt danh sách ứng viên nhanh hơn, và quan trọng nhất là tìm được những người thực sự 'Fit' (phù hợp) với văn hóa.
**Đối với Ứng viên:** Họ được chuẩn bị kỹ lưỡng hơn, tự tin hơn, và có cái nhìn thiện cảm, chuyên nghiệp về thương hiệu tuyển dụng của công ty."

## 🟢 SLIDE 10: ENDING (Chốt sale & Q&A)

*(Click nửa phải màn hình chuyển sang Slide 10 - Tạm dừng 1 giây, nhìn thẳng vào BGK, nói với giọng điệu chắc chắn, mạnh mẽ)*

**🗣️ Lời thoại:**
"Kính thưa ban giám khảo. InterviewPath không phải là một con chatbot phỏng vấn chung chung nhan nhản trên mạng.
Nó là một **nền tảng chuẩn bị phỏng vấn đặc thù cho từng doanh nghiệp.**
InterviewPath: Chuẩn bị cho ứng viên tốt hơn trước giờ G. Giúp HR tìm đúng người nhanh hơn.

Em xin kết thúc phần trình bày của đội. Xin trân trọng kính mời những câu hỏi phản biện từ Ban giám khảo!"

*(Cúi chào)*
