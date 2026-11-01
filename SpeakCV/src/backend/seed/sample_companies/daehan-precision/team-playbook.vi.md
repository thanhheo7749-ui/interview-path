# Cẩm nang làm việc của nhóm Backend (Daehan Precision Vina, Mẫu)

Tài liệu mẫu hư cấu. Nhóm Backend thuộc khối Engineering và phụ trách hệ thống quản lý sản xuất dùng trong nhà máy.

## Họp đứng đầu ngày

Cuộc họp đứng diễn ra lúc 09:00 mỗi ngày làm việc và kéo dài tối đa 15 phút.
Mỗi người nêu việc đã làm, việc sắp làm và vướng mắc, theo thứ tự do trưởng nhóm gọi.
Trưởng nhóm ghi biên bản vào hệ thống phê duyệt trước 10:00 cùng ngày.

## Review mã nguồn

Mọi thay đổi phải qua pull request, và cần 2 người duyệt trước khi merge, trong đó có một người là trưởng nhóm.
Người viết mã không được tự merge thay đổi của mình.
Pull request phải gắn với một phiếu công việc đã được duyệt trong Jira.
Mô tả pull request nêu rõ phạm vi ảnh hưởng, cách kiểm thử và kế hoạch quay lui.

## Phát hành

Chỉ phát hành vào khung giờ thứ Ba và thứ Năm sau 18:00, khi dây chuyền sản xuất ít tải.
Mỗi lần phát hành cần phiếu yêu cầu thay đổi do trưởng bộ phận ký duyệt.
Sau phát hành, người phụ trách gửi báo cáo kết quả cho trưởng bộ phận.

## Xử lý sự cố

Khi có sự cố, người phát hiện báo ngay cho trưởng nhóm bằng điện thoại, sau đó lập báo cáo sự cố.
Báo cáo sự cố phải nộp cho trưởng bộ phận trong vòng 48 giờ kể từ lúc phát hiện.
Trưởng bộ phận chủ trì buổi phân tích nguyên nhân gốc và ký duyệt biện pháp phòng ngừa.
Không ai được tự ý sửa dữ liệu sản xuất trực tiếp trên môi trường thật khi chưa có chữ ký duyệt.

## Công cụ

Nhóm dùng Jira để quản lý công việc, Git nội bộ để lưu mã nguồn và Jenkins để chạy kiểm thử.
Cơ sở dữ liệu sản xuất là Oracle, các dịch vụ mới viết bằng Java và Spring Boot.
Tài liệu thiết kế được lưu trong wiki nội bộ theo mẫu của công ty.
