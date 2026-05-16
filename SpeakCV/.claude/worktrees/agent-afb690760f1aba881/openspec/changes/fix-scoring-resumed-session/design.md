## Context

Hệ thống phỏng vấn AI của SpeakCV cho phép người dùng load lại buổi phỏng vấn cũ để tiếp tục. Khi load session cũ, `handleConfirmResume` trong `useInterviewActions.ts`:
1. Gọi `loadSession()` để khôi phục history chat
2. Set `savedReport` từ dữ liệu cũ (score, feedback, details)

Khi bấm "Kết thúc", `handleOpenReport` kiểm tra `if (savedReport)` → nếu có thì return report cũ ngay mà không gọi backend.

`handleSend` có clear `savedReport` khi gửi tin nhắn mới (line 160-162), nhưng cơ chế này không đủ tin cậy — nếu vì bất kỳ lý do nào `savedReport` không bị clear đúng lúc, report cũ sẽ hiển thị thay vì chấm điểm mới.

## Goals / Non-Goals

**Goals:**
- Đảm bảo khi có câu hỏi/trả lời mới sau khi resume session, hệ thống LUÔN gọi `endInterview()` để chấm điểm lại toàn bộ
- Giữ nguyên tốc độ hiển thị lịch sử cũ (không thay đổi `loadSession` flow)
- Giải pháp đơn giản, ít thay đổi code

**Non-Goals:**
- Không thay đổi backend scoring logic
- Không thêm incremental scoring (chỉ chấm câu mới) — backend đã xử lý bằng cách chấm toàn bộ history
- Không thay đổi UI hiển thị report

## Decisions

### Decision 1: Dirty flag `hasNewMessages` thay vì tách biệt savedReport logic

**Chọn**: Thêm boolean state `hasNewMessages`

**Lý do**: 
- Đơn giản nhất — chỉ thêm 1 state variable
- Không phá vỡ flow hiện tại (savedReport vẫn được dùng cho trường hợp xem report cũ mà không phỏng vấn thêm)
- Dễ debug — chỉ cần check `hasNewMessages` flag

**Alternatives đã xem xét**:
- **Option B (Clear savedReport khi loadSession)**: Sẽ mất khả năng xem nhanh report cũ mà không cần gọi API
- **Option C (Background re-score)**: Quá phức tạp cho vấn đề đơn giản

### Decision 2: Set flag tại `handleSend` thay vì `sendMessage`

**Chọn**: Set `hasNewMessages = true` trong `handleSend()`

**Lý do**: `handleSend` là entry point duy nhất cho user action, đảm bảo flag được set chính xác mỗi khi user tương tác mới.

## Risks / Trade-offs

- **[Risk] Flag không được reset đúng** → Mitigation: Reset tại mọi điểm khởi tạo session: `handleNewChat`, `handleRetry`, `handleConfirmResume`
- **[Trade-off] Gọi API chấm điểm lại toàn bộ history** → Backend phải xử lý lại từ đầu, nhưng flow này đã hoạt động đúng. Chỉ tốn thêm 1 API call so với hiện tại (thay vì dùng cache).
