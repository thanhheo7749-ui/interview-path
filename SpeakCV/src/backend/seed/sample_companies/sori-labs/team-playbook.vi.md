# Cách nhóm Backend làm việc (Sori Labs, Mẫu)

Tài liệu mẫu hư cấu. Nhóm Backend thuộc khối Product Engineering, phụ trách API và dịch vụ xử lý giọng nói cho ứng dụng học tập.

## Họp đồng bộ

Nhóm không họp đứng hằng ngày. Mỗi sáng mọi người viết cập nhật ngắn vào kênh nhóm trước 10:30.
Cập nhật gồm ba dòng: hôm qua đã xong gì, hôm nay làm gì, đang vướng gì.
Họp video chỉ dùng khi cần thảo luận mà viết không đủ rõ, và luôn có người ghi chú.

## Review mã nguồn

Mỗi pull request cần 1 người duyệt, bất kỳ ai trong nhóm cũng có thể duyệt.
Pull request được review lần đầu trong vòng 1 ngày làm việc.
Người duyệt nêu rõ điều mình sẽ làm khác đi thay vì chỉ từ chối.
Người viết tự merge sau khi được duyệt và theo dõi dịch vụ sau khi triển khai.
Thay đổi lớn hơn hai ngày công cần một ghi chú thiết kế ngắn trước khi viết mã.

## Triển khai

Nhóm triển khai nhiều lần mỗi ngày, qua pipeline tự động, bất kỳ lúc nào trong giờ cốt lõi.
Có cờ tính năng cho mọi thay đổi có rủi ro, và luôn có cách quay lui bằng một lệnh.

## Xử lý sự cố

Người phát hiện sự cố là người phụ trách sự cố cho đến khi bàn giao rõ ràng bằng văn bản.
Mở một kênh sự cố riêng và ghi lại dòng thời gian khi sự cố đang diễn ra.
Trong vòng 3 ngày làm việc sau sự cố, người phụ trách viết bản đánh giá không đổ lỗi và đưa vào nhật ký quyết định.
Nhóm không cần xin phép ai để khắc phục sự cố trên môi trường thật.

## Làm việc từ xa

Nhóm Backend làm việc từ xa 2 ngày mỗi tuần và gặp nhau tại văn phòng 3 ngày.

## Công cụ

Nhóm dùng GitHub cho mã nguồn và review, Linear cho công việc, và Notion cho nhật ký quyết định.
Dịch vụ mới viết bằng Python và FastAPI, dữ liệu lưu trong PostgreSQL, hạ tầng chạy trên container.
