## Why

Giao diện "Phỏng vấn Camera" hiện tại đang sử dụng Modal full-screen (toàn màn hình), khiến người dùng bị mất bối cảnh phỏng vấn hiện tại (lịch sử chat, các nút công cụ, thanh trạng thái). Người dùng mong muốn một trải nghiệm liền mạch hơn, nơi camera và AI Avatar được tích hợp trực tiếp (inline) vào giao diện phỏng vấn dưới dạng một widget nhỏ thay vì chuyển sang một màn hình mới, mang lại cảm giác mượt mà và tập trung hơn.

## What Changes

- **Loại bỏ**: Xóa hoặc vô hiệu hóa `CameraInterviewModal.tsx` cũ (dạng full-screen).
- **Thêm mới**: Tạo `InlineCameraWidget.tsx` để hiển thị Webcam của người dùng và AI Avatar theo dạng side-by-side (desktop) hoặc Picture-in-Picture (mobile) với kích thước nhỏ gọn.
- **Tích hợp**: Nhúng `InlineCameraWidget.tsx` vào `InterviewLayout.tsx` ngay phía trên khu vực chứa `MicroButton`.
- **Cập nhật Layout**: Tự động đẩy khu vực nút Mic và khung Chat xuống dưới khi Widget Camera được mở. Bố cục phải đáp ứng (responsive) linh hoạt mà không phá vỡ giao diện chat hiện tại.

## Capabilities

### New Capabilities
- `inline-camera-ui`: Khả năng hiển thị camera và AI Avatar dưới dạng widget nhúng trực tiếp vào Interview Layout, có tính năng mở/đóng mượt mà và đẩy các thành phần UI khác xuống dưới.

### Modified Capabilities
- `ai-hr-avatar`: Yêu cầu giữ nguyên logic phân tích âm thanh (Audio Analysis) và lip-sync từ phiên bản trước nhưng thay đổi container hiển thị để phù hợp với kích thước widget nhỏ hơn.

## Impact

- **Affected Code**: `src/frontend/components/Interview/InterviewLayout.tsx`, `src/frontend/app/interview/page.tsx`.
- **Dependencies**: Tái sử dụng các hooks đã viết (`useAudioAnalyser`), thành phần UI (`WebcamView`, `AvatarHR`). Không làm ảnh hưởng đến backend APIs (`/api/transcribe`, `/api/chat`).
