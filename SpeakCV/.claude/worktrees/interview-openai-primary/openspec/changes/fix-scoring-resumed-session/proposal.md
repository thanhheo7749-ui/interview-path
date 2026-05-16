## Why

Khi người dùng load lại buổi phỏng vấn cũ để xem lịch sử, hệ thống set `savedReport` từ dữ liệu cũ. Sau đó nếu tiếp tục phỏng vấn (thêm câu hỏi & trả lời mới), khi bấm "Kết thúc", `handleOpenReport` vẫn có thể trả về report cũ thay vì gọi API chấm điểm lại toàn bộ. Cần một cơ chế đánh dấu "đã có tin nhắn mới" để invalidate `savedReport` khi cần thiết.

## What Changes

- Thêm state `hasNewMessages` (boolean) vào `useInterviewActions` để track khi có Q&A mới sau khi load session cũ
- Cập nhật `handleSend` để set `hasNewMessages = true` mỗi khi gửi tin nhắn mới
- Cập nhật `handleOpenReport` để bỏ qua `savedReport` khi `hasNewMessages === true`, luôn gọi `endInterview()` chấm điểm lại
- Reset `hasNewMessages = false` tại các điểm: `handleNewChat`, `handleRetry`, `handleConfirmResume`

## Capabilities

### New Capabilities
- `dirty-flag-scoring`: Cơ chế dirty flag (`hasNewMessages`) để invalidate cached report khi có hoạt động phỏng vấn mới sau khi resume session cũ

### Modified Capabilities
_(Không có capability hiện tại nào bị thay đổi ở mức spec)_

## Impact

- **Frontend**: `useInterviewActions.ts` — thêm state mới và sửa logic ở 4 hàm
- **Backend**: Không thay đổi — `end_interview` endpoint đã xử lý đúng (chấm điểm toàn bộ history)
- **Breaking changes**: Không có
