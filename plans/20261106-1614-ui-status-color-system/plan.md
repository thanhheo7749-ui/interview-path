# UI: Màu sắc thể hiện trạng thái (interviewpath-demo)

## Vấn đề thật
1. `slate-950` (gần đen) bị dùng lặp lại cho nhiều vai trò khác nhau không liên quan status: active nav item, nút "Sign out", tab active, bong bóng chat "YOU" — tạo cảm giác "giao diện màu đen".
2. Các badge trạng thái thật (DRAFT/SUBMITTED/APPROVED/PUBLISHED trong JD Studio, "Ready for review" ở Documents, status job) đều dùng cùng 1 màu xám trung tính `bg-slate-200` — nhìn vào không biết đang ở bước nào. Chỉ có 1 chỗ (`awaiting-approval` ở Hiring requests) có màu amber, còn lại không nhất quán.

## Mục tiêu
Nhìn màu là biết trạng thái, dùng 1 bảng màu-trạng thái duy nhất, áp cho mọi nơi hiển thị status trong app. Tách riêng: màu "active/selected" (điều hướng, tab) khỏi màu "status" (dữ liệu đang ở bước nào).

## Bảng màu đề xuất (status)
| Trạng thái | Màu | Dùng ở đâu |
|---|---|---|
| Draft / chưa gửi | xám `slate-100 / slate-600` | JD draft, document trước khi xử lý |
| Đang xử lý / chờ ai đó | hổ phách `amber-100 / amber-900` | "Submitted/manager_review", "Ready for review", "Waiting for the manager's intake" |
| Đã duyệt / thành công | xanh lá `emerald-100 / emerald-800` | "Approved", "Published", job "Published" |
| Bị từ chối / chặn | đỏ `rose-100 / rose-800` | "Rejected", lint block, "Cancelled" |
| Gợi ý của AI (không phải quyết định) | tím `violet-100 / violet-700` | nhãn "[Demo AI]", "Hidden Gem" |

Màu active/selected (sidebar, tab, nút chính) giữ nguyên `blue-600` đã có — không thêm màu mới, không dùng `slate-950` nữa.

## Việc cần làm
1. Tạo 1 component dùng chung `StatusBadge` (vd `src/components/StatusBadge.jsx`) — nhận `status` + map nội bộ ra 1 trong 5 màu trên.
2. Thay 78 chỗ dùng `slate-950` (37 file) theo 2 nhóm:
   - Active/selected UI (sidebar active, tab active, nút Sign out) → `blue-600`.
   - Text màu đậm thường (tiêu đề, giá trị số) → giữ `slate-900`/`slate-950` nếu chỉ là màu chữ, KHÔNG phải nền trạng thái — không đổi những chỗ này để tránh phá layout không liên quan.
3. Thay badge trạng thái đang `bg-slate-200` (JD Studio, Documents, Jobs, Hiring requests) bằng `<StatusBadge>`.
4. Rà 1 lượt bằng mắt 5 trang chính: Jobs, Hiring requests, JD Studio, Documents, Board — xác nhận mỗi trạng thái hiển thị đúng màu theo bảng trên.

## Phạm vi
Chỉ `interviewpath/interviewpath-demo` (HR portal). Không đụng SpeakCV (candidate app) trừ khi được yêu cầu thêm.

## Việc chưa làm (cần xác nhận trước khi code)
- Danh sách đầy đủ tên trạng thái (status enum) của từng module (job draft, hiring request, document, job) chưa liệt kê hết — cần đọc kỹ `jd.status.*`, doc status trong `i18n/vi.json` trước khi code để map đủ, tránh sót trạng thái nào đó vẫn xám.
