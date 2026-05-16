## Context

Sau khi triển khai tính năng Camera Interview Mode bằng Modal full-screen (toàn màn hình), người dùng phản hồi rằng UI che lấp mất các ngữ cảnh quan trọng như khung chat, lịch sử chat và thanh trạng thái. Để cải thiện trải nghiệm, chúng ta sẽ chuyển thiết kế từ "Modal" sang "Inline Widget" gắn trực tiếp vào giao diện `InterviewLayout.tsx`.

## Goals / Non-Goals

**Goals:**
- Tích hợp camera và avatar vào `InterviewLayout.tsx` như một widget (không dùng full-screen overlay).
- Widget này sẽ chèn vào ngay trên component `<MicroButton />` và đẩy nút Mic cũng như khung Chat xuống dưới.
- Responsive layout: side-by-side trên desktop (max chiều cao) và dạng Picture-in-Picture thu gọn trên mobile.
- Dễ dàng bật/tắt (Toggle) từ Sidebar.
- Tái sử dụng `WebcamView`, `AvatarHR` và hooks hiện có.

**Non-Goals:**
- Không thay đổi logic xử lý âm thanh lip-sync (`useAudioAnalyser`).
- Không đụng vào Backend.

## Decisions

### 1. Vị trí chèn Widget
- **Chọn**: Chèn vào `InterviewLayout.tsx`, ngay trong vùng `<div className="relative group z-10 mt-10">` chứa `<MicroButton />`.
- **Lý do**: Giúp giữ vững luồng mắt của người dùng từ Avatar/Camera xuống nút Mic rồi xuống ChatBox.

### 2. Kích thước và Bố cục Widget (Desktop vs Mobile)
- **Chọn Desktop**: Thiết kế một khung viền cong (`rounded-3xl`), sử dụng `flex flex-row` để chia đều 2 nửa (Trái là Webcam, Phải là Avatar), chiều cao tối đa khoảng `250px` - `300px` để không đẩy khung chat xuống quá xa gây mất chữ trên màn hình nhỏ.
- **Chọn Mobile**: Thu nhỏ khung thành hình vuông hoặc dọc, Avatar hiển thị lớn, còn Webcam người dùng thu nhỏ góc phải (PiP).

### 3. State Management
- `isCameraModeOpen` boolean state được quản lý từ cấp trang `page.tsx` và truyền xuống `InterviewLayout` và `Sidebar`.
- Mở qua nút "Phỏng vấn Camera" trong Sidebar, tắt bằng nút (X) nhỏ ở góc Widget.

## Risks / Trade-offs

- **[Không gian hiển thị (Screen Real Estate)]** → Trên màn hình nhỏ (ví dụ laptop 13-inch), việc thêm widget có thể đẩy khung chat xuống khỏi màn hình (below the fold).
- **[Giải pháp (Mitigation)]**: Hạn chế chiều cao tối đa (`max-h-[300px]`) cho widget. Thêm tính năng tự động scroll-down hoặc giữ phần chat box luôn neo (sticky) ở dưới cùng.
