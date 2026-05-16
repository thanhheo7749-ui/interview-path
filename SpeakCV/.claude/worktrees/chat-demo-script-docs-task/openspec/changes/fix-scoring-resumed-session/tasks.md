## 1. Thêm state `hasNewMessages`

- [x] 1.1 Thêm `const [hasNewMessages, setHasNewMessages] = useState(false)` vào `useInterviewActions.ts` (sau line 109)

## 2. Set flag khi có tin nhắn mới

- [x] 2.1 Trong `handleSend()`, thêm `setHasNewMessages(true)` ngay sau block clear `savedReport` (sau line 162)

## 3. Cập nhật `handleOpenReport` để kiểm tra flag

- [x] 3.1 Sửa điều kiện short-circuit trong `handleOpenReport`: thay `if (savedReport)` bằng `if (savedReport && !hasNewMessages)` (line 204)

## 4. Reset flag tại các session boundaries

- [x] 4.1 Thêm `setHasNewMessages(false)` vào `handleNewChat()` (cùng block reset, sau line 124)
- [x] 4.2 Thêm `setHasNewMessages(false)` vào `handleRetry()` (sau line 248)
- [x] 4.3 Thêm `setHasNewMessages(false)` vào `handleConfirmResume()` (đầu hàm, trước khi set các state khác)

## 5. Verification

- [x] 5.1 Build thành công: `npm run build` không lỗi
- [ ] 5.2 Test thủ công: Load session cũ → xem report cũ ngay → hiển thị nhanh report cũ ✅
- [ ] 5.3 Test thủ công: Load session cũ → gửi thêm 1-2 tin nhắn → bấm "Kết thúc" → report mới với chấm điểm lại ✅
